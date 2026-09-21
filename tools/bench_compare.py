#!/usr/bin/env python3
"""A/B 对照: **游戏自打(A组)** vs **RL打南(B组)** —— 同一套口径, 并排出数 ✓

用户(2026-09-21): "一个全游戏(游戏自己跟自己打), 再换 RL(RL 和游戏打)"

组别靠 gid 前缀区分(库里同表, 都是走同一套托管链 ✓):
  A 组 = gameai-…   (南=**游戏本体 AI**, 其它三家=游戏 AI)  GUANDAN_ARM=gameai
  B 组 = gd-…    (南=**RL**, 其它三家=游戏 AI)           GUANDAN_ARM=rl

  两点说明:
   ① 两个臂**平级**: 同一套执行链(身份定位点选/真值对账) + 同一套护栏(代价过滤/领出兜底) ✓
      ⇒ 差异只来自"谁来选牌" ✓
   ② A 组里"南"和"三家"用的是**同一份游戏 AI** ⇒ 相当于"游戏自己跟自己打" ✓
      如果 A 组胜率明显偏低于 50% ⇒ 说明**我们这条链里有拖后腿的东西** ✗ (用户要测的就是这个 ✓)

用法: PYTHONPATH=src python3 tools/bench_compare.py [--min-deals 10]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from landlord_counter.companion.store import CompanionStore   # noqa: E402


def load(store: CompanionStore, prefix: str, since: float = 0.0) -> list[dict]:
    """since: 只统计这个时刻之后开始的局(排除改代码之前跑的旧数据 ✗)"""
    out = []
    for r in store.list_games(limit=100000):
        gid = str(r.get("gid", ""))
        if not gid.startswith(prefix):
            continue
        if since and float(r.get("started_at") or 0) < since:
            continue
        try:
            d = json.loads(r.get("result_json") or "{}")
        except Exception:  # noqa: BLE001
            continue
        if d.get("won") is None:
            continue
        out.append(d)
    return out


def stats(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0}
    wins = sum(1 for d in rows if d.get("won"))
    ty = sum(1 for d in rows if d.get("touYou") in (0, 2))
    ss = sum(1 for d in rows if len(d.get("youCiList") or []) >= 2
             and set((d.get("youCiList") or [])[:2]) == {0, 2})
    ups = [(d.get("shengJiShu") or 0) if d.get("won") else -(d.get("shengJiShu") or 0) for d in rows]
    ranks = []
    for d in rows:
        yc = d.get("youCiList") or []
        me = [i + 1 for i, s in enumerate(yc) if s in (0, 2)]
        if me:
            ranks.append(min(me))
    return {"n": n, "win": 100 * wins / n, "ty": 100 * ty / n, "ss": 100 * ss / n,
            "up": sum(ups) / len(ups), "rank": (sum(ranks) / len(ranks)) if ranks else None}


def line(name: str, s: dict) -> str:
    if not s.get("n"):
        return f"  {name:<22} 还没有数据"
    return (f"  {name:<22} {s['n']:>4} 局 | 胜率 {s['win']:>5.1f}% | 头游 {s['ty']:>5.1f}% | "
            f"双上 {s['ss']:>5.1f}% | 场均升级 {s['up']:>+5.2f} | 我方名次 {s['rank']:.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-deals", type=int, default=0, help="少于这么多局就提示样本不足")
    ap.add_argument("--since-min", type=float, default=0, help="只看最近 N 分钟内开始的局")
    a = ap.parse_args()
    import time as _t
    since = (_t.time() - a.since_min * 60) if a.since_min else 0.0
    st = CompanionStore()
    A = stats(load(st, "gameai-", since))
    B = stats(load(st, "gd-", since))
    OLD = stats(load(st, "allai-"))          # 早期用"改游戏"采的那批(已废弃 ✗)
    if since:
        print(f"\n  (只统计最近 {a.since_min:g} 分钟内开始的局 ✓)")

    print("\n══════ A/B 对照: 南那席 谁来打(其它三家都是游戏 AI) ══════")
    print(line("A 游戏AI打南(=自己打自己)", A))
    print(line("B RL打南", B))
    if OLD.get("n"):
        print(line("(废弃)改游戏采的那批", OLD))
    if A.get("n") and B.get("n"):
        d = B["win"] - A["win"]
        print(f"\n  ⇒ 胜率差(RL − 游戏AI): **{d:+.1f} 个百分点**")
        print(f"     场均升级差: {B['up'] - A['up']:+.2f} 级/局")
    if a.min_deals and (A.get("n", 0) < a.min_deals or B.get("n", 0) < a.min_deals):
        print(f"\n  ⚠ 样本不足({a.min_deals} 局): A={A.get('n', 0)} B={B.get('n', 0)} ⇒ 别看结论, 继续攒 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
