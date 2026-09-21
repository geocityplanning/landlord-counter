#!/usr/bin/env python3
"""按会话/时间窗统计 token 与各类消耗。

用法:
  PYTHONPATH=src python3 tools/token_report.py [最近分钟数]      # 默认看最近 60 分钟
  PYTHONPATH=src python3 tools/token_report.py 10                # 最近 10 分钟
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from landlord_counter.platform.usage import USAGE_DB  # noqa: E402


def main() -> int:
    mins = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    cutoff = time.time() - mins * 60
    tot = Counter()
    tok_p = tok_c = tok_t = 0.0
    by_model: Counter = Counter()
    n = 0
    # ★ 2026-09-21(用户): 数据一律从 sql 拿(jsonl 已删 ✗) ⇒ 直接读 data/usage.db ✓
    con = sqlite3.connect(f"file:{USAGE_DB}?mode=ro", uri=True, timeout=5)
    for ts, kind, amount, meta in con.execute(
            "SELECT ts, kind, amount, meta FROM usage WHERE ts >= ? ORDER BY id", (cutoff,)):
        n += 1
        amt = float(amount or 0)
        tot[kind or "?"] += amt
        if kind == "vlm_tokens":
            m = {}
            if meta:
                try:
                    m = json.loads(meta)
                except Exception:  # noqa: BLE001
                    m = {}
            tok_p += float(m.get("prompt") or 0)
            tok_c += float(m.get("completion") or 0)
            tok_t += amt
            by_model[m.get("model", "?")] += 1
    con.close()
    print(f"=== 最近 {mins:g} 分钟 (事件 {n} 条) ===")
    for k, v in sorted(tot.items(), key=lambda kv: -kv[1]):
        print(f"  {k:16s} {v:,.0f}")
    if tok_t:
        print(f"\n★ VLM 真实 token: 总计 {tok_t:,.0f}  (输入 {tok_p:,.0f} / 输出 {tok_c:,.0f})")
        print(f"  调用 {by_model} | 平均每次 {tok_t / max(1, sum(by_model.values())):,.0f} token")
    else:
        print("\n(VLM token 数据为空 —— 说明这段时间内没有走大模型的调用 ✓ 零成本 ✓)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
