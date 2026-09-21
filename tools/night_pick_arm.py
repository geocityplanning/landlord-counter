#!/usr/bin/env python3
"""夜跑选臂: 本轮夜跑里**已结算局数**少的那边先跑 ⇒ 两组严格交替、样本数接近 ✓

为什么不用文件记状态(用户 2026-09-21: "别自己搞json在后台记录" ✗):
  数据源就是 sqlite ⇒ 选臂也直接从库里数 ✓ 不引入第二种"真相" ✓

⚠ 口径: 只数**本轮夜跑开始之后**的局 ✓
  (今天白天 A/B 试跑的旧数据是修代码前/半程的 ⇒ 不能拿来当"这轮已跑过" ✗
   否则选臂会以为 RL 跑够了, 一晚上光跑游戏AI ✗)
"""
from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.getenv("COMPANION_DB", os.path.join(ROOT, "data", "companion.db"))
ARM_PREFIX = {"rl": "gd-", "gameai": "gameai-"}
NIGHT_START = (22, 30)      # 夜跑时段起点(与 night_segment.sh 的闸门一致 ✓)


def night_begin_ts(now: _dt.datetime | None = None) -> float:
    """本轮夜跑起点: 最近的 22:30 ✓"""
    now = now or _dt.datetime.now()
    begin = now.replace(hour=NIGHT_START[0], minute=NIGHT_START[1], second=0, microsecond=0)
    if now < begin:                                  # 凌晨(还没到今天 22:30) ⇒ 用昨天的 ✓
        begin -= _dt.timedelta(days=1)
    return begin.timestamp()


def settled(db: sqlite3.Connection, prefix: str, since: float) -> int:
    try:
        return db.execute(
            "SELECT COUNT(*) FROM deal WHERE gid LIKE ? AND started_at >= ?"
            " AND result_json IS NOT NULL AND result_json != ''", (prefix + "%", since)).fetchone()[0]
    except Exception:  # noqa: BLE001
        return 0


def main() -> int:
    try:
        db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    except Exception:  # noqa: BLE001
        print("rl")
        return 0
    since = night_begin_ts()
    try:
        row = db.execute("SELECT v FROM control WHERE k = 'night_begin'").fetchone()
        if row and row[0]:
            since = float(row[0])          # ★ 以库里的"本轮起点"为准 ✓ (白天旧数据不算 ✗)
    except Exception:  # noqa: BLE001
        pass
    n_rl, n_ai = settled(db, ARM_PREFIX["rl"], since), settled(db, ARM_PREFIX["gameai"], since)
    print("rl" if n_rl <= n_ai else "gameai")       # 平手先跑 RL(基线 ✓)
    return 0


if __name__ == "__main__":
    sys.exit(main())
