#!/usr/bin/env python3
"""真值对账(P0-2 硬指标): 我们决定的牌 vs 游戏**真值**里实际打出的牌。

与 acc_report.py 的区别:
  acc_report 用"桌面视觉读回"(±1 误差 ✗); 本工具用插桩版游戏的 window.__truth() ✓
  → 逐张比对零误差, 才能真正判"操作准确率 ≥99%"(用户硬指标)。

数据:
  data/truth/<时间>.jsonl   真值快照(含 plays: [{t(ms), seat, zhi[], n}])
  data/games/<局>.jsonl     我们的事件(plan=决策, play(src=own)=我们打的)

配对: 每条 plan(决策时刻 t 秒) → 之后 60 秒内**我方(seat 0)**的第一手真值出牌 → 比对。
输出: 逐手明细 + 操作准确率 + 执行落实率 + 失败归类。

用法: PYTHONPATH=src python3 tools/acc_truth.py
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_truth() -> list:
    """所有真值快照里出现过的**去重出牌序列**: [{t(ms), seat, zhi[]}]"""
    seq, seen = [], set()
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "truth", "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            for p in d.get("plays") or []:
                key = (p.get("t"), p.get("seat"), tuple(p.get("zhi") or []))
                if key in seen:
                    continue
                seen.add(key)
                seq.append({"t": p.get("t"), "seat": p.get("seat"), "zhi": list(p.get("zhi") or [])})
    seq.sort(key=lambda x: x["t"] or 0)
    return seq


def load_plans() -> list:
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "games", "*.jsonl")), key=os.path.getmtime):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if d.get("type") == "plan" and d.get("src", "hint") == "direct":
                # 只统计**我们自己点出去**的牌: 提示臂是游戏自己挑牌, 与我们意图无关 ✗
                out.append({"t": d.get("t"), "file": os.path.basename(f),
                            "why": d.get("why", ""), "n": d.get("n"),
                            "ranks": sorted(_z(c) for c in d.get("cards", []))})
    out.sort(key=lambda x: x["t"] or 0)
    return out


def _z(name) -> int:
    s = str(name)
    if "王" in s:
        return 15 if "小" in s else 16
    import re

    m = re.search(r"(10|[2-9AJQK])", s.upper())
    if not m:
        return 0
    t = m.group(1)
    return {"A": 14, "J": 11, "Q": 12, "K": 13, "10": 10}.get(t, int(t) if t.isdigit() else 0)


def main() -> int:
    truth = load_truth()
    plans = load_plans()
    if truth:                       # 只保留真值时间跨度内的决策(别把历史陈旧决策算进来)
        t0 = min(p["t"] for p in truth if p.get("t"))
        t1 = max(p["t"] for p in truth if p.get("t"))
        plans = [p for p in plans if p["t"] and (t0 / 1000 - 5) <= p["t"] <= (t1 / 1000 + 5)]
    us = [p for p in truth if p.get("seat") == 0]
    print(f"真值出牌 {len(truth)} 手(我方 {len(us)} 手) | 我们的决策 {len(plans)} 条")
    if not truth:
        print("还没有真值数据 —— 确认 truth_log.py 在跑, 且页面是插桩版(带 __truth)")
        return 1

    used = set()
    tot = ok = 0
    noget = 0
    reasons: Counter = Counter()
    print()
    print(f"{'决策(点数)':<30}{'真值实际打出(点数)':<30}结果")
    print("-" * 84)
    for pl in plans:
        if pl["t"] is None:
            continue
        # 关键: plan 是**出牌成功那一刻**记的 → 与真值出牌的时差应在几秒内
        # (原来用 0~60s 的大窗口 → 把历史文件的陈旧决策也配上了 ✗)
        cand = [p for i, p in enumerate(truth)
                if i not in used and p.get("seat") == 0 and p.get("t")
                and abs(p["t"] - pl["t"] * 1000) <= 3000]
        if not cand:
            noget += 1
            continue
        hit = cand[0]
        used.add(truth.index(hit))
        tot += 1
        dec = pl["ranks"]
        got = sorted(hit["zhi"])
        if dec == got:
            ok += 1
            print(f"{' '.join(map(str, dec)):<30}{' '.join(map(str, got)):<30}✓ 一致")
        else:
            if len(got) > len(dec):
                reasons["实际多打了牌(自动带同点数/多点)"] += 1
            elif len(got) < len(dec):
                reasons["实际少打了牌"] += 1
            else:
                reasons["张数对但牌面不同"] += 1
            print(f"{' '.join(map(str, dec)):<30}{' '.join(map(str, got)):<30}✗ 不一致")
    print("-" * 84)
    print(f"可配对 {tot} 手（另有 {noget} 条决策没等到我方出牌/可能没打出去）")
    if tot:
        print(f"★ 操作准确率(identity级, 真值口径): {ok}/{tot} = {ok / tot * 100:.1f}%   目标 ≥99%")
        for k, v in reasons.most_common():
            print(f"    失败原因: {k} × {v}")
        if tot + noget:
            print(f"★ 执行落实率(配对成功比例): {tot}/{tot + noget} = {tot / (tot + noget) * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
