#!/usr/bin/env python3
"""本轮夜跑起点(存在库里, 不搞文件 ✗) —— 让"选臂/战报"都只认本轮的局 ✓

· 库里 control 表记 `night_begin`(本轮夜跑开始时刻) ✓
· 超过 12 小时 ⇒ 视为新一轮(今晚重新开始) ⇒ 自动刷新 ✓
· 幂等: 一段跑完再来一次, 起点不变 ✓

用法: python3 tools/night_arm.py        # 输出本轮起点时间戳
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.getenv("COMPANION_DB", os.path.join(ROOT, "data", "companion.db"))
ROUND_MAX = 12 * 3600       # 一轮夜跑最长 12 小时 ⇒ 过期就开新一轮 ✓


def main() -> int:
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE IF NOT EXISTS control(k TEXT PRIMARY KEY, v TEXT)")
    row = db.execute("SELECT v FROM control WHERE k = 'night_begin'").fetchone()
    try:
        begin = float(row[0]) if row and row[0] else 0.0
    except Exception:  # noqa: BLE001
        begin = 0.0
    now = time.time()
    if begin <= 0 or (now - begin) > ROUND_MAX:
        begin = now
        db.execute("INSERT INTO control(k, v) VALUES('night_begin', ?)"
                   " ON CONFLICT(k) DO UPDATE SET v = excluded.v", (str(begin),))
        db.commit()
        print(f"{begin:.0f}   # 新一轮起点")
    else:
        print(f"{begin:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
