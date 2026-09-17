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

import glob

USAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "usage")


def main() -> int:
    mins = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    cutoff = time.time() - mins * 60
    tot = Counter()
    tok_p = tok_c = tok_t = 0.0
    by_model: Counter = Counter()
    n = 0
    for fp in sorted(glob.glob(os.path.join(USAGE_DIR, "usage-*.jsonl"))):
        for ln in open(fp, encoding="utf-8", errors="ignore"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            if float(e.get("t", 0)) < cutoff:
                continue
            n += 1
            kind = e.get("kind", "?")
            amt = float(e.get("amount") or 0)
            tot[kind] += amt
            if kind == "vlm_tokens":
                m = e.get("meta") or {}
                tok_p += float(m.get("prompt") or 0)
                tok_c += float(m.get("completion") or 0)
                tok_t += amt
                by_model[m.get("model", "?")] += 1
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
