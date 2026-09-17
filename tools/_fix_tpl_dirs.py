#!/usr/bin/env python3
"""一次性: 两套模板分开目录, 互不覆盖。

   data/templates_sr/   花色+点数(来自用户标注的参考图, 24 类)
   data/templates_rank/ 点数级(来自实时帧真值自动采集, "0_<点数>")

教训(2026-09-17): 两套都写同一个目录且开跑先清空 → **互相删** ✗(先后复测都掉到 25/27)
"""
import os
import re

# ① 采集器: 输出改到 templates_rank, 且**不清空**(追加)
A = "tools/tm_collect_live.py"
s = open(A).read()
s = s.replace('OUT = "data/templates_sr"', 'OUT = "data/templates_rank"   # 点数级(实时真值采集)')
s = s.replace('    os.makedirs(OUT, exist_ok=True)\n', '    os.makedirs(OUT, exist_ok=True)   # 追加式: 不清空(与花色级分目录)\n')
open(A, "w").write(s)
print("✓ tm_collect_live → data/templates_rank(追加)")

# ② 标注图构建器: 保留 templates_sr, 去掉"先清空"
B = "tools/tm_build.py"
s = open(B).read()
s = re.sub(r"\n    for f in os\.listdir\(OUT\):\n        os\.remove\(os\.path\.join\(OUT, f\)\)\n", "\n    # 追加式: 不清空(清空会连累别的套件 ✗)\n", s)
open(B, "w").write(s)
print("✓ tm_build → 不再清空 templates_sr")

# ③ 加载器: 两个目录都读
C = "src/landlord_counter/guandan/percept.py"
s = open(C).read()
old = '''    import os as _os
    if d is None:
        d = _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "data", "templates_sr")
    d = _os.path.abspath(d)
    bank: dict = {}
    if not _os.path.isdir(d):
        return bank
    for fn in _os.listdir(d):'''
new = '''    import os as _os
    # 两个目录都读: 花色+点数(参考图标注) + 点数级(实时真值采集) ✓
    root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", "..", "data"))
    dirs = [d] if d else [_os.path.join(root, "templates_sr"), _os.path.join(root, "templates_rank")]
    bank: dict = {}
    files = []
    for dd in dirs:
        dd = _os.path.abspath(dd)
        if _os.path.isdir(dd):
            files += [_os.path.join(dd, fn) for fn in _os.listdir(dd)]
    for full in files:
        fn = _os.path.basename(full)'''
assert old in s, "找不到 load_templates_sr 主体"
s = s.replace(old, new)
s = s.replace('np.load(_os.path.join(d, fn))', 'np.load(full)')
open(C, "w").write(s)
print("✓ percept.load_templates_sr → 合并两个目录")
