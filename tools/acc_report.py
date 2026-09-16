#!/usr/bin/env python3
"""操作准确率对账(identity 级): "决定出的牌" vs "游戏实际打出的牌"。

口径(用户 2026-09-16 定):
    操作准确率 = 实际打出的牌 == 我们决定的牌 的比例。目标 ≥99%。
    —— 注意: 游戏有"点一张会自动带上同点数整组"的设定, 所以这个指标能直接抓到
       "手跟不上脑子"(决定打1张, 实际打出3张) 那类错误。

数据来源(纯视觉, 产品路径):
    plan 事件  = 决策层选的牌(我们自己写的)
    play 事件  = 出牌后从**桌面读回**的牌(src=table, 实测)
对账方法:
    ① 牌面: 按**点数多重集**比较(花色识别不稳, 点数稳)
    ② 张数: 长度必须一致
输出: 逐手明细 + 准确率 + 失败原因归类

用法: PYTHONPATH=src python3 tools/acc_report.py [局ID或文件路径...]
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def zhi(name: str) -> int:
    s = str(name)
    if "王" in s:
        return 15 if "小" in s else 16
    m = re.search(r"(10|[2-9AJQK])", s.upper())
    if not m:
        return 0
    t = m.group(1)
    return {"A": 14, "J": 11, "Q": 12, "K": 13, "10": 10}.get(t, int(t) if t.isdigit() else 0)


def _files(args) -> list:
    if args:
        out = []
        for a in args:
            if os.path.exists(a):
                out.append(a)
            else:
                g = os.path.join(ROOT, "data", "games", f"{a}.jsonl")
                if os.path.exists(g):
                    out.append(g)
        return out
    return sorted(glob.glob(os.path.join(ROOT, "data", "games", "*.jsonl")), key=os.path.getmtime)


def pair(path: str) -> list:
    """把 plan 与紧随其后的"桌面读回"配成对。"""
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    pairs, pending = [], None
    for r in rows:
        if r.get("type") == "plan":
            pending = r                       # 只记最近一次决策
        elif r.get("type") == "play" and r.get("seat") == "南":
            src = r.get("src", "table")
            if src == "own":
                continue                      # 我们自己写的, 不算"实际"
            if pending:
                pairs.append((pending, r))
                pending = None
    return pairs


def verify_stats(path: str) -> tuple:
    """张数口径: 决策打 N 张 → 实际掉几张?(verify 事件)"""
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    plans = [r for r in rows if r.get("type") == "plan"]
    vers = [r for r in rows if r.get("type") == "verify"]
    return plans, vers


def main() -> int:
    fs = _files(sys.argv[1:])
    if not fs:
        print("没有牌局数据")
        return 1
    tot = ok = 0
    reasons: Counter = Counter()
    print(f"{'局':<22}{'决定(点数)':<26}{'实际打出(点数)':<26}结果")
    print("-" * 96)
    for f in fs:
        gid = os.path.basename(f)[:-6]
        for plan, act in pair(f):
            tot += 1
            dec = sorted(zhi(c) for c in plan.get("cards", []))
            got = sorted(zhi(c) for c in act.get("cards", []))
            same = dec == got
            if same:
                ok += 1
                res = "✓ 一致"
            elif len(dec) == len(got):
                res = "✗ 牌面不同"
                reasons["牌面不同(同张数)"] += 1
            elif len(got) > len(dec):
                res = f"✗ 多打出 {len(got) - len(dec)} 张(疑似自动带同点数)"
                reasons["自动带上同点数"] += 1
            else:
                res = f"✗ 少打出 {len(dec) - len(got)} 张(疑似读漏)"
                reasons["疑似读漏"] += 1
            fd = " ".join(str(x) for x in dec)
            fg = " ".join(str(x) for x in got)
            print(f"{gid:<22}{fd:<26}{fg:<26}{res}")
    print()
    print("=== 张数口径(不依赖桌面读回) ===")
    print(f"{'局':<22}{'决策张数':<12}{'实际掉牌':<12}结果")
    print("-" * 60)
    vt = vok = 0
    vreason: Counter = Counter()
    for f in fs:
        gid = os.path.basename(f)[:-6]
        plans, vers = verify_stats(f)
        pn = [p for p in plans if p.get("hand_before")]
        for i, v in enumerate(vers):
            vt += 1
            exp, got = v.get("expected_after"), v.get("hand_after")
            n_dec = None
            if i < len(pn):
                n_dec = pn[i].get("n")
            if v.get("ok"):
                vok += 1
                print(f"{gid:<22}{str(n_dec):<12}{str(got):<12}✓ 一致")
            else:
                d = None
                if exp is not None and got is not None:
                    d = exp - got
                res = f"✗ 多打出 {-d} 张(自动带同点数?)" if d is not None and d < 0 else \
                      ("✗ 少打出 %s 张" % d if d is not None and d > 0 else "✗ 不符")
                vreason["多打出(自动带同点数)" if d is not None and d < 0 else "少打出" if d else "不符"] += 1
                print(f"{gid:<22}{str(n_dec):<12}{str(got):<12}{res}")
    print("-" * 60)
    if vt:
        print(f"张数口径准确率: {vok}/{vt} = {vok / vt * 100:.1f}%   目标 ≥99%")
        for k, v in vreason.most_common():
            print(f"   失败原因: {k} × {v}")
    else:
        print("(还没有 verify 事件 —— 需要带张数校验的版本跑窗口)")
    print()
    if tot:
        print(f"操作准确率(identity级): {ok}/{tot} = {ok / tot * 100:.1f}%   目标 ≥99%")
        for k, v in reasons.most_common():
            print(f"   失败原因: {k} × {v}")
    else:
        print("还没有可对账的'决策(plan)+实际(读回)'数据 —— "
              "需要跑**直选/RL 臂**(会自己做决策), 提示臂没有'决定'可对账。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
