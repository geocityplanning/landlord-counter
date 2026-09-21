#!/usr/bin/env python3
"""夜跑战报 —— **只读 sqlite**(data/companion.db) 出 A/B 对比 ✓

用户(2026-09-21): "结束之后报告直接看sqlite，而不是自己搞json在后台记录"
用法: python3 tools/night_report.py [--hours 9]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.getenv("COMPANION_DB", os.path.join(ROOT, "data", "companion.db"))
ARMS = (("gameai-", "A 游戏AI 打南(=自己打自己)"), ("gd-", "B RL 打南"))


def grab(db: sqlite3.Connection, prefix: str, since: float) -> list[dict]:
    out = []
    for gid, jp, rj in db.execute(
            "SELECT gid, ji_pai, result_json FROM deal WHERE gid LIKE ?"
            " AND result_json IS NOT NULL AND result_json != '' AND started_at >= ?"
            " ORDER BY started_at", (prefix + "%", since)):
        try:
            out.append({"gid": gid, "jp": jp, "d": json.loads(rj)})
        except Exception:  # noqa: BLE001
            pass
    return out


def line(name: str, ds: list[dict]) -> str:
    n = len(ds)
    if not n:
        return f"  {name:28s} 还没有数据"
    w = sum(1 for x in ds if x["d"].get("won"))
    ty = sum(1 for x in ds if x["d"].get("touYou") in (0, 2))       # 我方(南/北)拿头游
    ss = sum(1 for x in ds if set((x["d"].get("youCiList") or [])[:2]) == {0, 2})   # 双上
    up = [((x["d"].get("shengJiShu") or 0) if x["d"].get("won") else -(x["d"].get("shengJiShu") or 0))
          for x in ds]
    return (f"  {name:28s} {n:3d} 局 | 胜率 {100*w/n:5.1f}% | 头游率 {100*ty/n:5.1f}% | "
            f"双上率 {100*ss/n:5.1f}% | 场均升级 {sum(up)/n:+.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=0, help="统计最近 N 小时(默认=本轮夜跑全程 ✓)")
    a = ap.parse_args()
    if not os.path.exists(DB):
        print(f"  库不存在: {DB}")
        return 1
    since = (time.time() - a.hours * 3600) if a.hours else 0.0
    try:                                   # ★ 默认只统计**本轮夜跑**(起点存在库里 ✓)
        row = sqlite3.connect(f"file:{DB}?mode=ro", uri=True).execute(
            "SELECT v FROM control WHERE k = 'night_begin'").fetchone()
        if not a.hours and row and row[0]:
            since = float(row[0])
    except Exception:  # noqa: BLE001
        pass
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    _w = f"最近 {a.hours:g} 小时" if a.hours else "本轮夜跑"
    print(f"\n  🃏 夜跑战报({_w} · 数据源: sqlite ✓)")
    print(f"  跑法: 南那席轮流换 —— A 组用游戏本体 AI, B 组用 RL; 其它三家始终是游戏 AI ✓")
    print()
    for pre, name in ARMS:
        print(line(name, grab(db, pre, since)))

    # ── 整场(过A)层 ──
    # 掼蛋真正的胜负单位是**整场**: 得分/升级只是过程, 有人"过A"才算一场打完 ✓
    # (用户 2026-09-21: "掼蛋这种游戏一局是要过A算赢" ⇒ 段也要够长才打得完一场 ✓)
    print()
    for pre, name in ARMS:
        over, ours, played = [], 0, 0
        for (rj,) in db.execute(
                "SELECT result_json FROM deal WHERE gid LIKE ? AND started_at >= ?"
                " AND result_json IS NOT NULL AND result_json != ''", (pre + "%", since)):
            try:
                d = json.loads(rj)
            except Exception:  # noqa: BLE001
                continue
            played += 1
            mo = d.get("matchOver")
            if isinstance(mo, dict) and mo:
                over.append(mo.get("games") or 0)
                if str(mo.get("winner")) == "duiWu1":      # duiWu1 = 我方(南+北) ✓
                    ours += 1
        if played:
            extra = (f" | 打完整场 {len(over)} 次 | **我方过A {ours}** | 平均每场 "
                     f"{sum(over)/len(over):.1f} 局") if over else " | 还没有一场打到过A"
            print(f"  {name:28s} 本段共 {played} 局{extra}")

    # 对账(唯一权威口径: 决定的牌 vs 真值实出的牌 ✓)
    print()
    for pre, name in ARMS:
        row = db.execute(
            "SELECT COUNT(*), SUM(agree = 1), SUM(agree = 0) FROM decision"
            " WHERE gid LIKE ? AND agree IS NOT NULL AND ts >= ?", (pre + "%", since)).fetchone()
        if row and row[0]:
            print(f"  {name:28s} 对账 {row[1] or 0}/{row[0]} = {100*(row[1] or 0)/row[0]:.1f}%")

    print("\n  (样本 < 20 局时, 胜率差异基本是噪声 ⇒ 只看趋势 ✓)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
