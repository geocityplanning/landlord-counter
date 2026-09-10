"""识别层：模板匹配为主链路，VLM 视觉大模型降级兜底。

双链路设计（对齐 AgentOS 思想）:
    1. 模板匹配（OpenCV）：快、免费、本地，识别标准牌面
    2. VLM 兜底（可选）：当模板匹配置信度不足时调用视觉大模型
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import httpx

from ..config import VisionConfig
from ..logic.tracker import ALL_RANKS

# 牌面字符 → 编码
RANK_MAP = {
    "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8",
    "9": "9", "10": "10", "J": "J", "Q": "Q", "K": "K", "A": "A",
    "2": "2", "小王": "BJ", "大王": "RJ",
}


class CardRecognizer:
    """牌面识别器"""

    def __init__(self, config: VisionConfig):
        self.cfg = config
        self.templates: dict[str, np.ndarray] = self._load_templates()
        self._masks: dict[str, np.ndarray] = self._build_masks()
        # 游戏视觉适配包（doudizhu_wishday 等）：决定怎么"看懂"当前 App 的画面
        from ..profiles import get_profile

        self.profile = get_profile(config.profile_name)

    # ---------- VLM 直读主链路（模板对重度重叠画面失效时的正解） ----------

    def locate_hand_band(self, img: np.ndarray) -> Optional[tuple[int, int, int, int]]:
        """定位手牌行亮色条带 (x0,y0,x1,y1)。策略: 找白色(卡面)行带, 取最底部一条。

        适配 wishday 等横屏斗地主：手牌是屏幕底部一行白色扇形。
        """
        if img is None or img.size == 0:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        # 每行亮像素计数
        rows = []
        for y in range(0, h, 2):
            c = int(np.sum(gray[y : y + 2, ::4] > 225))
            rows.append((y, c))
        mx = max((c for _, c in rows), default=0)
        if mx <= 0:
            return None
        # 聚合行带
        bands = []
        for y, c in rows:
            if c > mx * self.profile.band_min_ratio:
                if bands and y - bands[-1][1] <= 6:
                    bands[-1][1] = y
                else:
                    bands.append([y, y])
        if not bands:
            return None
        band = bands[-1]  # 最底部 = 自己手牌
        y0, y1 = max(0, band[0] - self.profile.crop_pad), min(h, band[1] + self.profile.crop_pad)
        # 横向范围: 带内亮列
        strip = gray[y0:y1, :]
        cols = np.where(np.sum(strip > 225, axis=0) > 0)[0]
        if cols.size == 0:
            return None
        x0, x1 = max(0, int(cols.min()) - self.profile.crop_pad), min(w, int(cols.max()) + self.profile.crop_pad)
        return (x0, y0, x1, y1)

    def read_hand_vlm(self, img_full: np.ndarray, expected: int = 0) -> list[str]:
        """按 profile 从整屏截图直读手牌: 定位亮带 → 裁剪放大 → VLM → 解析点数。"""
        if not self.cfg.vlm_available():
            return []
        band = self.locate_hand_band(img_full)
        if band is None:
            return []
        x0, y0, x1, y1 = band
        roi = img_full[y0:y1, x0:x1]
        if roi.size == 0:
            return []
        scale = self.profile.upscale
        if scale != 1.0:
            roi = cv2.resize(roi, (int(roi.shape[1] * scale), int(roi.shape[0] * scale)), interpolation=cv2.INTER_LANCZOS4)
        n_expect = expected or self.profile.expected_cards
        # profile 提示词里嵌入期望张数（构造专用提示）
        prompt = self._band_prompt(n_expect)
        text = self.recognize_with_vlm(roi, prompt)
        if not text:
            return []
        from ..profiles import parse_rank_tokens

        ranks = parse_rank_tokens(text)
        return ranks[: max(n_expect, 24)] if ranks else []

    def _band_prompt(self, expected: int) -> str:
        from ..profiles import _build_prompt

        return _build_prompt(expected, self.profile.display) if self.profile.vlm_prompt == "" else (
            self.profile.vlm_prompt
            + (f" 你应该输出 {expected} 个点数。" if expected > 0 else "")
            + " 只输出点数列表，从左到右，逗号分隔。"
        )


    def _load_templates(self) -> dict[str, np.ndarray]:
        """加载模板图片（assets/card_templates/<rank>.png）"""
        templates = {}
        td = self.cfg.template_dir
        if not td.exists():
            return templates
        for png in td.glob("*.png"):
            rank = png.stem
            if rank in ALL_RANKS:
                img = cv2.imread(str(png))
                if img is not None:
                    templates[rank] = img
        return templates

    def _build_masks(self) -> dict[str, np.ndarray]:
        """构建掩码：非白色区域为1（只匹配文字/图案，忽略白底）"""
        masks = {}
        for rank, tpl in self.templates.items():
            gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            # 白色(>=230)为背景=0，文字为1
            mask = np.where(gray < 230, 255, 0).astype(np.uint8)
            masks[rank] = mask
        return masks

    def template_available(self) -> bool:
        return len(self.templates) > 0

    def recognize_hand(self, roi_img: np.ndarray) -> list[str]:
        """识别手牌区域中的牌：掩码匹配 + 多尺度 + 位置聚类去重"""
        if not self.template_available():
            return []
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        # 收集所有候选: (conf, rank, x_center, scale)
        candidates: list[tuple[float, str, float]] = []
        for rank, tpl in self.templates.items():
            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            mask = self._masks[rank]
            th, tw = tpl_gray.shape[:2]
            for scale in [1.0, 0.95, 0.9, 0.85, 1.05, 1.1]:
                tw2, th2 = max(10, int(tw * scale)), max(10, int(th * scale))
                if tw2 > w or th2 > h:
                    continue
                resized = cv2.resize(tpl_gray, (tw2, th2))
                mask_resized = cv2.resize(mask, (tw2, th2))
                res = cv2.matchTemplate(
                    gray, resized, cv2.TM_CCORR_NORMED, mask=mask_resized
                )
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= self.cfg.match_threshold:
                    candidates.append((max_val, rank, max_loc[0] + tw2 / 2))

        if not candidates:
            return []

        # 按置信度降序，贪心聚类：x 距离 < 牌宽的 60% 视为同一张牌
        candidates.sort(key=lambda t: t[0], reverse=True)
        card_w = next(iter(self.templates.values())).shape[1]
        cluster_eps = card_w * 0.6
        chosen: list[tuple[float, str, float]] = []
        for conf, rank, xc in candidates:
            if all(abs(xc - cx) > cluster_eps for _, _, cx in chosen):
                chosen.append((conf, rank, xc))
                if len(chosen) >= 20:  # 手牌最多20张
                    break

        # 按 x 位置排序输出
        chosen.sort(key=lambda t: t[2])
        return [rank for _, rank, _ in chosen]

    def recognize_with_vlm(self, roi_img: np.ndarray, prompt: str) -> Optional[str]:
        """VLM 兜底识别（需配置 API）"""
        if not (self.cfg.vlm_api_key and self.cfg.vlm_api_base):
            return None
        _, buf = cv2.imencode(".png", roi_img)
        b64 = base64.b64encode(buf.tobytes()).decode()
        payload = {
            "model": self.cfg.vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": int(os.getenv("VLM_MAX_TOKENS", "8192")),  # 推理型VLM(deepseek-vision)推理段可变且长(实测3.5k±), 预留要足
        }
        _effort = os.getenv("VLM_REASONING_EFFORT", "low")  # 低推理档: 实测 1.8s vs 29.5s, 读数一致
        if _effort:
            payload["reasoning_effort"] = _effort
        try:
            resp = httpx.post(
                f"{self.cfg.vlm_api_base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.cfg.vlm_api_key}"},
                timeout=120,  # 推理型VLM单次可达30-60s
            )
            if resp.status_code == 400 and _effort:  # 不支持该参数的家: 去掉重试
                payload.pop("reasoning_effort", None)
                resp = httpx.post(
                    f"{self.cfg.vlm_api_base}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.cfg.vlm_api_key}"},
                    timeout=120,
                )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    def recognize_hand_best(self, roi_img: np.ndarray) -> list[str]:
        """主链路 + 兜底"""
        cards = self.recognize_hand(roi_img)
        if cards:
            return cards
        text = self.recognize_with_vlm(
            roi_img, "识别图中所有扑克牌点数，输出逗号分隔列表，例如: 3,5,K,A,2"
        )
        if text:
            return self._parse_vlm_text(text)
        return []

    def _parse_vlm_text(self, text: str) -> list[str]:
        """解析 VLM 返回文本为牌列表"""
        cards = []
        for token in text.replace("，", ",").split(","):
            token = token.strip()
            if token in RANK_MAP:
                cards.append(RANK_MAP[token])
            elif token.lower() in RANK_MAP:
                cards.append(RANK_MAP[token.lower()])
        return cards
