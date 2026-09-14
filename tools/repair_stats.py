#!/usr/bin/env python3
"""修复统计 CSV 里的"未判定(?)"行: 从原始结算串重新判定 win/lose。

用途: read_settle 的解析 bug(只认冒号)导致 62 局判成 '?', 数据其实还在 raw 列里 →
      本脚本按修好的规则重算, 写回 CSV(原文件备份为 .bak)。

用法: python3 tools/repair_stats.py /tmp/guandan_stats.csv
"""
from __future__ import annotations

import re
import shutil
import sys

R_HEAD = re.compile(r"头游\s*[:：=]\s*([东南西北])")
R_UP = re.compile(r"我方是否升级\s*[:：=]\s*(是|否)")


def judge(raw: str) -> bool | None:
    raw = raw.replace("&#10;", "\n").replace("<br>", "\n")
    m = R_HEAD.search(raw)
    head = m.group(1) if m else ""
    if head in ("南", "北"):
        return True
    if head in ("东", "西"):
        return False
    m2 = R_UP.search(raw)
    if m2:
        return m2.group(1) == "是"
    return None


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/guandan_stats.csv"
    shutil.copy(path, path + ".bak")
    out, fixed, still = [], 0, 0
    for ln in open(path, errors="ignore"):
        parts = ln.rstrip("\n").split(",", 4)
        if len(parts) == 5 and parts[2] == "?":
            w = judge(parts[4])
            if w is not None:
                parts[2] = "win" if w else "lose"
                fixed += 1
            else:
                still += 1
        out.append(",".join(parts))
    with open(path, "w") as fo:
        fo.write("\n".join(out) + "\n")
    # 汇总
    from collections import Counter
    c = Counter()
    by = {}
    for ln in open(path, errors="ignore"):
        p = ln.rstrip("\n").split(",", 4)
        if len(p) >= 4:
            c[p[2]] += 1
            if p[2] in ("win", "lose") and p[3] in ("ours", "mvp"):
                n, w = by.get(p[3], (0, 0))
                by[p[3]] = (n + 1, w + (1 if p[2] == "win" else 0))
    print(f"[修复] 重判 {fixed} 行, 仍无法判定 {still} 行; 备份: {path}.bak")
    print(f"[分布] {dict(c)}")
    for tag, (n, w) in sorted(by.items()):
        print(f"[A/B] {tag}: {w}/{n} = {100 * w / max(1, n):.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
