#!/usr/bin/env python3
"""代码体检: 文件规模 + 今晚新增的疑似废函数(逐个查真实调用点)。

用法: python3 tools/audit_code.py
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

CORE = [
    "src/landlord_counter/guandan/percept.py",
    "src/landlord_counter/platform/games/guandan_adapter.py",
    "src/landlord_counter/platform/gestures.py",
    "src/landlord_counter/platform/runtime.py",
]


def calls(name: str) -> int:
    out = subprocess.run(
        f"grep -rn --include='*.py' -E '\\b{name}\\s*\\(' src tools 2>/dev/null",
        shell=True, capture_output=True, text=True).stdout.strip()
    return len([ln for ln in out.splitlines() if f"def {name}(" not in ln])


print("=== 文件规模 ===")
total = 0
for f in CORE:
    n = len(Path(f).read_text().splitlines())
    total += n
    print(f"  {n:>5} 行  {f.split('landlord_counter/')[-1]}")
print(f"  {total:>5} 行  合计")

print("\n=== 今天新增/改动的函数: 真实调用点 ===")
for f in CORE:
    for m in re.finditer(r"^def (\w+)", Path(f).read_text(), re.M):
        nm = m.group(1)
        if nm.startswith("_"):
            continue
        c = calls(nm)
        if c <= 1:                       # 只有定义处 → 死代码候选
            print(f"  ✗ 疑似死代码  {nm:32s} ({f.split('/')[-1]}, 调用 {c})")

print("\n=== tools/ 里的临时脚本 ===")
tmp = sorted(Path("tools").glob("_*.py")) + sorted(Path("tools").glob("_*.sh"))
for t in tmp:
    print(f"  {t.name}")
print(f"  共 {len(tmp)} 个")
