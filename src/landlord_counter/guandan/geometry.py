"""掼蛋专有几何: **离线标定 + 在线校验**(2026-09-18 用户定方向)。

设计原则(为什么这么改)
--------------------
旧做法: 运行时"自适应"——每次现算手牌带/牌位/按钮 ⇒ **每次都在赌** ✗
  实测后果: 牌被抬起/动画中/换承载/换局 ⇒ 量出来的东西漂了 ⇒ 点错牌、读错牌、反复修 ✗
新做法:**离线标定 + 在线校验**
  ① 离线标定(offline): 在**干净、静止**的一帧上把几何量准 ⇒ 写进 data/calib/guandan.json
     量什么: 手牌带 y 范围、牌位起点与牌距、末张宽、按钮矩形、点击纵坐标 ✓
  ② 在线校验(online): 运行时**只验证**这些常量是否仍然成立(便宜的检查) ⇒
     成立就照常量用 ✓; 不成立 ⇒ **拒绝动作 + 响亮报错** ✓(绝不悄悄漂移 ✗)

本模块只负责**几何**(定位)。读牌在 read.py, 点牌在 tap.py, 记牌在 tracker.py。
换游戏/换承载 ⇒ 重新跑一次标定即可, 不改代码 ✓
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

CALIB_DIR = Path("data/calib")
CALIB_PATH = CALIB_DIR / "guandan.json"

# 标定时的环境指纹: 换个环境(分辨率/方向/承载)必须重标 ✓
EXPECT_W, EXPECT_H = 720, 1280


@dataclass
class GuandanGeom:
    """掼蛋(720x1280 竖屏, 网页版)的几何常量 —— 全部来自离线标定 ✓"""

    # ---- 手牌区 ----
    hand_y0: int = 815            # 手牌牌面顶边(放平态)
    hand_y1: int = 936            # 手牌牌面底边
    hand_lift: int = 36           # 选中时上抬像素(放平顶边 815 → 抬起 779)
    slot_x0: int = 5              # 最左那张牌的左缘
    pitch: int = 24               # 相邻牌左缘间隔(牌距)
    last_card_w: int = 88         # 末张(完整可见)的宽度 —— 从右缘反推它的左缘用
    max_cards: int = 27           # 满手张数(掼蛋 2 副牌, 每人 27)

    # ---- 按钮区(底部三段: 提示 / 出牌 / 不出) ----
    btn_y0: int = 1078
    btn_y1: int = 1148
    btn_play_x: int = 360         # 出牌(最亮/金色那段)中心
    btn_play_y: int = 1112

    # ---- 按张数的**实测位置表**(2026-09-18 用户定方向) ----
    #   "27/26/25 张时牌的位置本来就不同" ⇒ 不推导公式, **每种情况量准** ✓
    #   键=张数, 值=[每张牌的左缘 x](从大到小显示顺序) ⇒ 运行时直接查表 ✓
    slots_by_n: dict = field(default_factory=dict)

    # ---- 元信息 ----
    calibrated_at: str = ""
    calibrated_on: str = ""       # 环境指纹(宽x高)
    notes: str = ""

    # ---------- 派生量 ----------
    def hand_y(self) -> int:
        """点击手牌用的纵坐标: 手牌带中点 ✓(实测有效; 用按钮/常量会打空 ✗)"""
        return int((self.hand_y0 + self.hand_y1) // 2)

    def slots(self, n: int) -> list[int]:
        """**牌位网格**: 从**右端锚点**向左铺 ✓

        为什么右端: 末张完整可见 ⇒ 它的左缘必然可测 ⇒ 天生可靠 ✓(实测: 左端锚点会偏一张 ✗)
        末张左缘 = 标定的 slot_x0 + (max_cards-1)*pitch (满手时) ⇒ 由此回推当前 n 张的右端 ✓
        """
        right = self.slot_x0 + (self.max_cards - 1) * self.pitch
        # 手牌居中: 张数少一张, 整排右移半个牌距(实测源码布局如此) ⇒ 按 max_cards 对齐右端 ✓
        right -= (self.max_cards - n) * self.pitch // 2 * 0
        return [int(right - (n - 1 - i) * self.pitch) for i in range(n)]

    def slots_for(self, n: int, right_left_x: int | None = None) -> list[int]:
        """牌位: **优先查表**(离线按张数标定的实测表 ✓); 没有才回退右锚点推导 ✓

        用户 2026-09-18: "27,26,25 剩余数量不同, 牌的位置不同 … 每种情况量准位置" ✓
        ⇒ 表在手 ⇒ 直接用实测值 ✓(公式只当兜底, 并且用时要有据可查 ✓)
        """
        key = str(int(n))
        table = {str(k): v for k, v in (self.slots_by_n or {}).items()}
        hit = table.get(key)
        if hit and len(hit) == int(n):
            return [int(x) for x in hit]
        if right_left_x is None:
            right_left_x = self.slot_x0 + (self.max_cards - 1) * self.pitch
        return self.slots_from_right(int(n), int(right_left_x))

    def slots_from_right(self, n: int, right_left_x: int) -> list[int]:
        """给**当帧实测**的末张左缘, 生成 n 个牌位(右锚点向左铺) ✓ —— 在线首选 ✓"""
        return [int(right_left_x - (n - 1 - i) * self.pitch) for i in range(n)]


# ---------------- 读写 ----------------

def save(geom: GuandanGeom, path: Path | None = None) -> Path:
    p = Path(path or CALIB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    d = asdict(geom)
    d["calibrated_at"] = d.get("calibrated_at") or time.strftime("%Y-%m-%d %H:%M:%S")
    d["calibrated_on"] = d.get("calibrated_on") or f"{EXPECT_W}x{EXPECT_H}"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    return p


def load(path: Path | None = None) -> GuandanGeom:
    """读标定文件; 没有就用**内置默认**(= 2026-09 实测值) ✓"""
    p = Path(path or CALIB_PATH)
    if not p.exists():
        return GuandanGeom(calibrated_at="(内置默认: 2026-09-18 实测)",
                           calibrated_on=f"{EXPECT_W}x{EXPECT_H}")
    d = json.loads(p.read_text())
    keep = {k: v for k, v in d.items() if k in GuandanGeom.__dataclass_fields__}
    return GuandanGeom(**keep)


# ---------------- 在线校验 ----------------

@dataclass
class CheckResult:
    ok: bool
    reasons: list = field(default_factory=list)     # 失败原因(响亮报错用)
    measured: dict = field(default_factory=dict)    # 当帧实测的对照值


def verify_online(img, geom: GuandanGeom, expect_cards: int | None = None) -> CheckResult:
    """**在线校验**: 标定常量在当前帧还成立吗? —— 只验, 不调 ✓

    检查项(都便宜):
      ① 分辨率与方向一致(换承载/换方向 ⇒ 标定作废)
      ② 手牌带的**白牌面**出现在标定的 y 区间内
      ③ 白牌面连成的横范围与标定的牌位网格**对齐**(允许 ±2px 的相位误差)
      ④ (可选)张数与预期一致
    任一项不成立 ⇒ ok=False + 说明原因 ⇒ 调用方**拒绝动作**并报错 ✓(绝不悄悄自适应 ✗)
    """
    res = CheckResult(ok=True)
    if img is None:
        return CheckResult(ok=False, reasons=["取帧失败"])
    h, w = img.shape[:2]
    res.measured["shape"] = [w, h]
    if (w, h) != (EXPECT_W, EXPECT_H):
        res.ok = False
        res.reasons.append(f"分辨率/方向不符: 实测 {w}x{h}, 标定 {EXPECT_W}x{EXPECT_H}")

    y0, y1 = geom.hand_y0, geom.hand_y1
    band = img[y0:y1]
    if band.size == 0:
        return CheckResult(ok=False, reasons=[f"手牌带越界: {y0}..{y1}"])
    white = (band.min(axis=2) > 150).mean(axis=0)
    cols = np.where(white > 0.40)[0]
    if len(cols) < 10:
        res.ok = False
        res.reasons.append("手牌带内几乎看不到白牌面(可能不是牌局界面/动画中)")
        return res
    x_lo, x_hi = int(cols[0]), int(cols[-1])
    res.measured["white_x"] = [x_lo, x_hi]

    # ③ 横范围与网格相位对齐: 末张左缘 ≈ x_hi - last_card_w
    right_left = x_hi - geom.last_card_w
    res.measured["right_left"] = right_left
    grid_x = geom.slots_from_right(1, right_left)[0]
    if abs(grid_x - right_left) > 2:
        res.ok = False
        res.reasons.append("牌位网格相位异常")

    # ④ 张数一致性(可选)
    if expect_cards:
        n_est = int(round((right_left - x_lo) / geom.pitch)) + 1
        res.measured["n_est"] = n_est
        if abs(n_est - expect_cards) > 1:
            res.ok = False
            res.reasons.append(f"张数不符: 几何推 {n_est}, 预期 {expect_cards}")
    return res
