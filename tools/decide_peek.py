#!/usr/bin/env python3
"""决策端视角 —— 一条命令看清"决策器在想什么" ✓

用法(仓库根目录下):
    PYTHONPATH=src python3 tools/decide_peek.py              # 现场看一眼
    PYTHONPATH=src python3 tools/decide_peek.py --top 40     # 最多列 40 个候选
    PYTHONPATH=src python3 tools/decide_peek.py --json       # 机器可读

为什么要它(用户 2026-09-21 要的 ✓):
    · 日志只能看到"**它选了 X**" ✗
    · 看不到"**它是从哪些选项里挑的、挑得对不对**" ✓ ← 这个工具补的就是这块
    · 还能**预演代价过滤**(看那手会不会被拦、会被换成什么 ✓)

只读不写 ✗: 本工具不点牌、不发指令、不改任何状态 ✓ (纯"看" ✓)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from landlord_counter.guandan import rules as R           # noqa: E402
from landlord_counter.guandan.rl_policy import RLPolicy   # noqa: E402
from landlord_counter.platform.cdp import CDP             # noqa: E402

Z = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
S = {0: "♠", 1: "♥", 2: "♣", 3: "♦", 4: ""}


def cn(c) -> str:
    """一张牌的显示名(花色可能没有 —— 万能占位牌不带花色 ✓)"""
    h = getattr(c, "hua", None)
    z = int(getattr(c, "zhi", 0) or 0)
    return f"{S[h] if h in S else ''}{Z.get(z, z)}"


def _cards(raw: list | None) -> list:
    return [R.Card(zhi=int(x["zhi"]), hua=int(x["hua"]), id=int(x.get("id", -1)))
            for x in (raw or [])]


def _bomb_xing() -> tuple:
    return (R.PAI_XING["ZHA_DAN"], R.PAI_XING["TONG_HUA_SHUN"], R.PAI_XING["TIAN_WANG_ZHA"])


def cost_preview(choice, cands, need_beat: bool):
    """预演"代价过滤"会怎么判 —— 和 adapter 里那段**同一条规则** ✓

    返回 (会不会拦, 换成什么, 说明)
    """
    if choice is None or not cands:
        return False, None, "没选/没候选"
    bomb = _bomb_xing()
    if need_beat:
        expensive = choice.xing in bomb or getattr(choice, "wild_used", 0) > 0
        cheap = [g for g in cands if g.xing not in bomb and not getattr(g, "wild_used", 0)]
        if expensive and cheap:
            alt = min(cheap, key=lambda g: (g.chang_du, g.zhu_zhi))
            return True, alt, "该压时: 能不用炸弹/万能压过 ⇒ 不许动它们 ✓"
        return False, None, "放过(本来就只有炸弹/万能能用 ✓)"
    if getattr(choice, "wild_used", 0) > 0:
        same = [g for g in cands if g.xing == choice.xing and not getattr(g, "wild_used", 0)]
        if same:
            alt = min(same, key=lambda g: (g.chang_du, g.zhu_zhi))
            return True, alt, "领出时: 同牌型有不用万能的 ⇒ 别拿万能凑小牌 ✓"
    return False, None, "放过 ✓"


def main() -> int:
    ap = argparse.ArgumentParser(description="决策端视角(只读 ✓)")
    ap.add_argument("--top", type=int, default=30, help="最多列几个候选(默认 30)")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    os.environ.setdefault("GUANDAN_ALLOW_WILD", "1")

    cdp = CDP()
    if not cdp.find_truth():
        print("✗ 连不上页面(CDP 9222 / 真值探针) —— 先在服务器上跑 tools/guandan_prep.py ✓")
        return 2
    t = cdp.truth() or {}
    jp = t.get("jiPaiModule") or t.get("jiPai")
    hand = _cards((t.get("handsFull") or {}).get("0"))
    last_cards = _cards(t.get("shangJia"))
    need_beat = bool(t.get("needBeat"))
    last = R.identify(last_cards, jp) if last_cards else None

    if not hand:
        print("✗ 现在手里没牌(不在对局中?) ✓")
        return 3
    if int(t.get("current", -1)) != 0:
        print(f"ℹ 现在不是我方回合(轮到 {t.get('current')}) —— 以下是**我方视角**的推演 ✓")

    cands = R.find_all_plays(hand, last, jp)
    rl = RLPolicy()
    choice, info = (None, {"value": 0.0, "n_cand": len(cands), "mapped": len(cands)})
    if cands:
        choice, info = rl.choose(cands, hand, [], [len(hand)] * 4, (0, last), 0)
    blocked, alt, why = cost_preview(choice, cands, need_beat)

    if args.json:
        print(json.dumps({
            "ji_pai": jp, "hand": [cn(x) for x in hand], "need_beat": need_beat,
            "table": R.group_to_str(last) if last else None,
            "candidates": [{"cards": R.group_to_str(g), "xing": R.PAI_XING_NAME[g.xing],
                            "zhu_zhi": g.zhu_zhi, "wild_used": getattr(g, "wild_used", 0)}
                           for g in cands],
            "rl_choice": R.group_to_str(choice) if choice else None,
            "rl_value": info.get("value"),
            "cost_filter": {"blocked": blocked,
                            "alt": R.group_to_str(alt) if alt else None, "why": why},
            "model": os.path.basename(getattr(rl, "path", "") or ""),
        }, ensure_ascii=False, indent=1))
        return 0

    bar = "═" * 64
    print(bar)
    print(f"决策端视角   级牌={jp}({Z.get(jp, jp)})   手牌={len(hand)} 张   "
          f"该不该压={'压' if need_beat else '领出'}")
    print(f"  桌上 = {R.group_to_str(last) if last else '无(我领出)'}")
    print(f"  手牌 = {' '.join(cn(x) for x in hand)}")
    print("─" * 64)
    if not cands:
        print("  合法候选: **0 个** ⇒ 只能'不出' ✓" + ("(压不过 ✓)" if need_beat else ""))
    else:
        print(f"  合法候选 {len(cands)} 个(全列出来, 最多 {args.top} 个):")
        for i, g in enumerate(cands[:args.top]):
            w = f"  万能×{g.wild_used}" if getattr(g, "wild_used", 0) else ""
            print(f"    {i + 1:2d}. {R.group_to_str(g):34s} 型={R.PAI_XING_NAME[g.xing]:4s}"
                  f" 主值={g.zhu_zhi}{w}")
        if len(cands) > args.top:
            print(f"    …(还有 {len(cands) - args.top} 个)")
    print("─" * 64)
    if cands:
        print(f"  RL 模型: {os.path.basename(getattr(rl, 'path', '') or '?')}")
        print(f"  RL 选了: {R.group_to_str(choice) if choice else '不出'}"
              f"   value={float(info.get('value') or 0):.4f}")
        if blocked:
            print(f"  ⚠ 代价过滤会**拦住**它 ✓ → 改用 {R.group_to_str(alt)}")
            print(f"     理由: {why}")
        else:
            print(f"  代价过滤: 放过 ✓ ({why})")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
