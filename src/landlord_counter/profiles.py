"""游戏视觉适配包（Game Profile）——「通用 GUI 托管」的核心抽象。

每个游戏(=厂商 App)的界面都不一样：手牌/牌桌/按钮的布局、牌面的画法、重叠程度都不同。
本模块把「一个游戏怎么被看懂」收敛成一份声明式配置，识别管线本身与游戏无关：

    capture → 按 profile 定位手牌行 → 按 profile 放大/裁切 → 按 profile 的提示词送 VLM → 统一解析成点数

新增一个游戏 = 在 PROFILES 里加一份配置（+ 相应 GameRules），不改管线代码。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 统一的手牌点数字符集（视觉层输出 → 记牌逻辑层）
TOKEN_MAP = {
    "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    "10": "10", "J": "J", "j": "J", "Q": "Q", "q": "Q", "K": "K", "k": "K",
    "A": "A", "a": "A", "2": "2",
    "小": "BJ", "小王": "BJ", "JOKER_B": "BJ",
    "大": "RJ", "大王": "RJ", "JOKER_R": "RJ",
}


def parse_rank_tokens(text: str) -> list[str]:
    """把 VLM 返回的自由文本解析成点数列表（容忍逗号/空格/中英混杂）。"""
    tokens = []
    for chunk in text.replace("，", ",").replace("、", ",").split(","):
        for tok in chunk.split():
            tok = tok.strip()
            # 整段优先匹配（10 / 小王 等双字符）
            if tok in TOKEN_MAP:
                tokens.append(TOKEN_MAP[tok])
            elif tok.lower() in TOKEN_MAP:
                tokens.append(TOKEN_MAP[tok.lower()])
    return tokens


@dataclass
class GameProfile:
    """一个游戏的视觉适配配置。"""

    name: str                       # 如 doudizhu_wishday
    display: str                    # 展示名，如「斗地主(wishday)」
    rules_name: str = "doudizhu"    # 对应 logic/rules.py 注册表里的规则
    # --- 手牌行定位 ---
    locate_mode: str = "bright_band_bottom"  # 亮色行带、取最底部一条
    band_min_ratio: float = 0.40    # 行带判定阈值(相对该图最亮行)
    crop_pad: int = 8               # 行带外扩像素
    upscale: float = 2.0            # 送 VLM 前放大倍数
    # --- 识别 ---
    vlm_first: bool = True          # 跳过模板匹配、直接 VLM（模板匹配对重度重叠无效）
    vlm_prompt: str = field(default="")
    expected_cards: int = 0         # 0=未知(让 VLM 数)；17/20 可提示模型输出数量
    # --- 动作(托管阶段用, 先占位) ---
    actions_roi: dict = field(default_factory=dict)  # 叫分/出牌按钮区域(归一化坐标)


_PROMPT_BASE = (
    "这是安卓游戏《斗地主》截图里玩家手牌的一行（画面底部亮色条带），"
    "牌呈扇形严重重叠，每张牌角：上方小花色符号、下方大点数数字"
    "(3-10为数字，另有 J,Q,K,A,2，小王/大王为特殊图案)。"
    "请逐张分辨这一排【每一张牌】的点数：重复的点数(对子/三条/四张)绝不能合并去重；"
    "每张露出的牌都要算一次，看不清的猜最可能的点数补上，"
    "输出数量 = 可见牌数。只输出点数列表，从左到右，逗号分隔，不要任何解释。"
)


def _build_prompt(expected: int, display: str) -> str:
    head = f"这是「{display}」游戏中玩家手牌的一行截图"
    body = (
        "牌呈扇形严重重叠，每张牌角上方是小花色符号、下方是大点数数字"
        "(3-10/J/Q/K/A/2，小王大王特殊图案)。"
        "请逐张输出【每一张】牌的点数：对子/三条等重复点数绝不能合并，"
        "看不清的猜最可能点数补上，数量=手牌总数。"
    )
    tail = (
        f"（你应输出 {expected} 个点数）" if expected > 0 else ""
    ) + "只输出点数列表，从左到右，逗号分隔，不要解释。"
    return head + body + tail


PROFILES: dict[str, GameProfile] = {
    "doudizhu_wishday": GameProfile(
        name="doudizhu_wishday",
        display="斗地主(wishday)",
        rules_name="doudizhu",
        locate_mode="bright_band_bottom",
        band_min_ratio=0.40,
        crop_pad=8,
        upscale=2.0,
        vlm_first=True,
        vlm_prompt=_PROMPT_BASE,
        expected_cards=17,
    ),
}


def get_profile(name: str | None) -> GameProfile:
    if not name or name not in PROFILES:
        return PROFILES["doudizhu_wishday"]
    return PROFILES[name]
