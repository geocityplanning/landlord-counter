#!/usr/bin/env python3
"""**演示对局报告**: 逐手列出「谁出了什么」「我们决策了什么」「这一手准不准」✓

用户 2026-09-18 要求: "并记录出了什么牌，每一手的准确性，各家出什么牌"

两个数据源(互补, 都不靠猜):
  · 游戏真值 `plays`  —— 谁(seat)、出了什么点数(zhi)、几张(n)  ⇒ 零读误差 ✓
  · 运行日志         —— 我们的决策(单张：♠5 / 不出) + 这一步的结果(ok=True/False) ✓

输出:
  ① 逐手表: 序号 | 座位 | 出的牌 | 我方决策 | 准确? | 备注
  ② 各家统计: 每人出了几手、共几张
  ③ 我方操作准确率: **成功打出 / 尝试打出**(只算我们自己点出去的牌 ✓)

用法: python3 tools/demo_report.py /tmp/demo_run.log
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.platform.cdp import CDP    # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {"♠": "♠", "♥": "♥", "♣": "♣", "♦": "♦"}
SEAT = {0: "我", 1: "西", 2: "北(队友)", 3: "东"}


def nm(v) -> str:
    return NAME.get(int(v), str(int(v)))


def parse_log(path: str) -> list:
    """从运行日志里抽出**每一次尝试**: (我们想要的, 结果, 备注) ✓"""
    out = []
    want = None
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return out
    for ln in lines:
        m = re.search(r"\[rl\] 手牌\d+ 候选\d+\(可映射\d+\) → (.+?) \| value=", ln)
        if m:
            want = m.group(1).strip()          # 例如 "单张：♠5" 或 "不出"
            continue
        m = re.search(r"\[动作\] (\w+) → ok=(\w+)(?: retries=(\d+))?(?: (\S+))?(?: · (.*))?", ln)
        if m:
            kind, ok, retries, tag, why = m.groups()
            out.append({
                "want": want or kind,
                "ok": ok == "True",
                "why": (why or tag or "").strip(),
                "retries": int(retries or 0),
            })
            want = None
    return out


def main() -> int:
    log = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_run.log"
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    plays = [p for p in (t.get("plays") or []) if int(p.get("n") or 0) > 0]
    acts = parse_log(log)

    print(f"== 模式: 见日志开头 | 真值里记录的手数: {len(plays)} | 日志里的动作: {len(acts)} ==\n")
    print(f"{'#':>3} | {'座位':<8} | {'出的牌':<18} | {'我方决策':<16} | 准确")
    print("-" * 74)
    ai = 0
    for i, p in enumerate(plays, 1):
        seat = int(p.get("seat", 0))
        cards = " ".join(nm(v) for v in (p.get("zhi") or []))
        if seat == 0:
            a = acts[ai] if ai < len(acts) else None
            ai += 1
            want = (a["want"] if a else "?")
            acc = "✓" if (a and a["ok"]) else "✗"
            note = (a["why"] if a else "")
            print(f"{i:>3} | {SEAT.get(seat, seat):<8} | {cards:<18} | {want:<16} | {acc} {note}")
        else:
            print(f"{i:>3} | {SEAT.get(seat, seat):<8} | {cards:<18} | {'—':<16} | —")

    print("\n== 各家统计 ==")
    for s in (0, 1, 2, 3):
        mine = [p for p in plays if int(p.get("seat", 0)) == s]
        tot = sum(int(p.get("n") or 0) for p in mine)
        print(f"  {SEAT.get(s, s):<8}: {len(mine):>2} 手, 共 {tot:>2} 张")

    ours = [a for a in acts]
    okn = sum(1 for a in ours if a["ok"])
    print("\n== 我方操作准确率(只算我们自己点出去的牌) ==")
    print(f"  成功 {okn} / 尝试 {len(ours)} = {okn / max(1, len(ours)) * 100:.1f}%")
    fail = [a for a in ours if not a["ok"]]
    if fail:
        print("  失败明细:")
        for a in fail:
            print(f"    ✗ 想打 {a['want']} → {a['why'] or '(无原因)'}")
    print("\n(提示: '不出' 也是合法动作 ✓; 真值里的座位 0=我 1=西 2=北(队友) 3=东)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
