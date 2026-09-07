"""AI 推理层：调用大模型分析对手牌型、给出出牌建议（可选功能）。"""
from __future__ import annotations

import httpx

from ..config import LLMConfig
from ..logic.tracker import GameState

SYSTEM_PROMPT = """你是斗地主记牌分析助手。根据记牌器提供的剩余牌和对手出牌记录，
分析对手可能持有的牌型，给出简明结论。只输出分析结果，不要客套。"""


class LandlordAnalyzer:
    """斗地主大模型分析器"""

    def __init__(self, config: LLMConfig):
        self.cfg = config

    @property
    def available(self) -> bool:
        return self.cfg.enabled and bool(self.cfg.api_key)

    def analyze(self, state: GameState) -> str:
        """分析当前局面，返回建议文本"""
        if not self.available:
            return ""
        user_prompt = (
            state.summary()
            + "\n\n请分析：1) 外面最大的牌是什么 2) 对手可能的炸弹 3) 出牌建议"
        )
        try:
            resp = httpx.post(
                f"{self.cfg.api_base}/chat/completions",
                json={
                    "model": self.cfg.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.cfg.temperature,
                    "max_tokens": 512,
                },
                headers={"Authorization": f"Bearer {self.cfg.api_key}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"[AI分析失败: {e}]"
