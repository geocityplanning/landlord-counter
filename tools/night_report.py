#!/usr/bin/env python3
"""战报: **主指标(双上率 + 场均升级)打头** ✓ 其余作参考 ✓ (2026-09-22 用户定)"""
import argparse
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.getenv("COMPANION_DB", os.path.join(ROOT, "data", "companion.db"))
ARMS = (("gameai-", "A 游戏AI 打南(四家全游戏AI = 基准线)"),
        ("gd-", "B RL 打南(三家游戏AI)            "))


def grab(db, prefix, since):
    out = []
    for gid, jp, rj in db.execute(
            "SELECT gid, ji_pai, result_json FROM deal WHERE gid LIKE ?"
            " AND result_json IS NOT NULL AND result_json != '' AND started_at >= ?"
            " ORDER BY started_at", (prefix + "%", since)):
        try:
            out.append(json.loads(rj))
        except Exception:  # noqa: BLE001
            pass
    return out


def line(name, ds):
    n = len(ds)
    if not n:
        return f"  {name}  还没有数据"
    ss = sum(1 for d in ds if set((d.get("youCiList") or [])[:2]) == {0, 2})
    up = [((d.get("shengJiShu") or 0) if d.get("won") else -(d.get("shengJiShu") or 0)) for d in ds]
    w = sum(1 for d in ds if d.get("won"))
    return (f"  {name} {n:3d} 局\n"
            f"      ★主指标  双上率 **{100*ss/n:5.1f}%**   场均升级 **{sum(up)/n:+.2f}**\n"
            f"       参考    胜率 {100*w/n:5.1f}%   头游率 "
            f"{100*sum(1 for d in ds if d.get('touYou') in (0, 2))/n:5.1f}%   被双下率 "
            f"{100*sum(1 for d in ds if set((d.get('youCiList') or [])[:2]) == {1, 3})/n:5.1f}%")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=0, help="统计最近 N 小时(默认=本轮夜跑 ✓)")
    a = ap.parse_args()
    if not os.path.exists(DB):
        print(f"  库不存在: {DB}")
        return 1
    since = (time.time() - a.hours * 3600) if a.hours else 0.0
    try:
        row = sqlite3.connect(f"file:{DB}?mode=ro", uri=True).execute(
            "SELECT v FROM control WHERE k = 'night_begin'").fetchone()
        if not a.hours and row and row[0]:
            since = float(row[0])
    except Exception:  # noqa: BLE001
        pass
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    _w = f"最近 {a.hours:g} 小时" if a.hours else "本轮夜跑"
    print(f"\n  🃏 夜跑战报({_w} · 数据源: sqlite ✓)")
    print("  跑法: 南那席轮流换 —— A=游戏本体AI(基准线 ✓ 自打自, 天然≈50%) / B=RL; 其它三家始终是游戏AI")
    print("  看数: **先看双上率 + 场均升级**(主指标 ✓ 灵敏); 胜负只作参考(样本需求大 ✗)\n")
    for pre, name in ARMS:
        print(line(name, grab(db, pre, since)))
        print()
    for pre, name in ARMS:
        row = db.execute("SELECT COUNT(*), SUM(agree = 1) FROM decision"
                         " WHERE gid LIKE ? AND agree IS NOT NULL AND ts >= ?",
                         (pre + "%", since)).fetchone()
        if row and row[0]:
            print(f"  {name} 对账 {row[1] or 0}/{row[0]} = {100*(row[1] or 0)/row[0]:.1f}%")
    print("\n  (每种指标样本 <20 局时, 差异基本是噪声 ⇒ 只看趋势 ✓)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
