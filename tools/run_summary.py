#!/usr/bin/env python3
"""跑完看数 —— **只读 sqlite**(data/companion.db), 不从日志/json 里猜 ✓

用户(2026-09-21)原话:
  "现在的自动化后台跑的代码是不是就单纯跑代码，然后记一下时间，
   然后结束之后报告直接看sqlite，而不是自己搞json在后台记录"

⇒ 是 ✓。跑的时候: 平台照跑, 事件通过 sink 直接进库(GameLog 不落盘 ✗)。
   看数的时候: 就是这个脚本, 纯 SQL 查询 ✓。

用法:
  python3 tools/run_summary.py                 # 全部已结算局
  python3 tools/run_summary.py --min 30        # 只看最近 30 分钟内开始的局
  python3 tools/run_summary.py --arm rl        # 只看某个决策臂(rl / gameai)
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


def connect() -> sqlite3.Connection:
    """只读打开 —— 看数绝不写库 ✓"""
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def deals(db, since: float, arm: str) -> list[tuple]:
    """已结算的局(有 result 的)"""
    rows = db.execute(
        "SELECT gid, ji_pai, started_at, ended_at, result_json FROM deal"
        " WHERE result_json IS NOT NULL AND result_json != '' AND started_at >= ?"
        " ORDER BY started_at", (since,)).fetchall()
    out = []
    for gid, jp, st, en, rj in rows:
        if arm != "all":
            # 臂从 decision.note 里认(实测: 'RL决策' / '游戏AI决策' ✓)
            tag = "游戏AI决策" if arm == "gameai" else "RL决策"
            got = db.execute("SELECT COUNT(*) FROM decision WHERE gid = ? AND note LIKE ?",
                             (gid, f"%{tag}%")).fetchone()[0]
            if not got:
                continue
        try:
            d = json.loads(rj)
        except Exception:  # noqa: BLE001
            d = {}
        out.append((gid, jp, st, en or st, d))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=0, help="只看最近 N 分钟内开始的局")
    ap.add_argument("--arm", default="all", choices=["all", "rl", "gameai"])
    a = ap.parse_args()
    if not os.path.exists(DB):
        print(f"  库不存在: {DB}")
        return 1

    since = (time.time() - a.min * 60) if a.min else 0.0
    db = connect()
    ds = deals(db, since, a.arm)

    print(f"\n  ═══ 跑数汇总(sqlite: {os.path.relpath(DB, ROOT)}) ═══")
    print(f"  口径: {'全部' if not a.min else f'最近 {a.min:g} 分钟'} / 决策臂={a.arm}")
    print(f"  已结算局数: {len(ds)}")
    if not ds:
        print("  (还没有可统计的局 ✓)")
        return 0

    n = len(ds)
    wins = sum(1 for *_, d in ds if d.get("won"))
    ty = sum(1 for *_, d in ds if d.get("touYou") in (0, 2))       # 我方(南/北)拿头游
    ss = sum(1 for *_, d in ds if set((d.get("youCiList") or [])[:2]) == {0, 2})
    ups = [((d.get("shengJiShu") or 0) if d.get("won") else -(d.get("shengJiShu") or 0))
           for *_, d in ds]
    print(f"  胜率 {wins}/{n} = {100*wins/n:.1f}%  |  头游率 {100*ty/n:.1f}%  |  "
          f"双上率 {100*ss/n:.1f}%  |  场均升级 {sum(ups)/n:+.2f}")

    # 每一局一行(级牌/胜负/升级/名次) —— 同样只从库里读 ✓
    print("  ── 逐局 ──")
    for gid, jp, st, en, d in ds[-12:]:
        print(f"    {gid:24s} 级牌{jp:<3} {'赢' if d.get('won') else '输'}  "
              f"头游={d.get('touYou')}  升级{d.get('shengJiShu')}  "
              f"名次{d.get('youCiList')}")

    # 出牌与对账(全库口径, 按时间过滤)
    p_all = db.execute("SELECT COUNT(*) FROM play WHERE mine = 1 AND ts >= ?", (since,)).fetchone()[0]
    p_tot = db.execute("SELECT COUNT(*) FROM play WHERE ts >= ?", (since,)).fetchone()[0]
    dec = db.execute("SELECT COUNT(*), SUM(agree = 1), SUM(agree = 0) FROM decision WHERE ts >= ?",
                     (since,)).fetchone()
    print("  ── 动作/对账 ──")
    print(f"    我方出牌 {p_all} / 全场事件 {p_tot}")
    if dec and dec[0]:
        ok, ng = dec[1] or 0, dec[2] or 0
        print(f"    决策 {dec[0]} 次 | 对账一致 {ok} | 不一致 {ng}"
              f"{'  ⇒ 一致率 %.1f%%' % (100*ok/dec[0]) if dec[0] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
