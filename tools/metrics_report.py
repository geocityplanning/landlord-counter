#!/usr/bin/env python3
"""夜跑指标汇总: 把 metrics.jsonl + 夜跑日志 + 统计 CSV 折成 **ECS 口径指标行**。

输出: 每行 = 一个指标(编号, 指标, 值, 单位, 样本数, 窗口, 数据来源)
用法: python3 tools/metrics_report.py --jsonl /tmp/guandan_metrics.jsonl \
        --log /tmp/guandan_night.log --csv /tmp/guandan_stats.csv \
        --host /tmp/guandan_host.csv --out /tmp/metrics_night.csv [--since-ts T]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import time


def pctl(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(round(p / 100 * (len(xs) - 1)))))
    return xs[i]


def load_jsonl(path: str, since: float = 0.0) -> list[dict]:
    out = []
    try:
        for ln in open(path, errors="ignore"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            if r.get("ts", 0) >= since:
                out.append(r)
    except FileNotFoundError:
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", default="/tmp/guandan_metrics.jsonl")
    ap.add_argument("--log", default="/tmp/guandan_night.log")
    ap.add_argument("--csv", default="/tmp/guandan_stats.csv")
    ap.add_argument("--host", default="/tmp/guandan_host.csv")
    ap.add_argument("--out", default="/tmp/metrics_night.csv")
    ap.add_argument("--since-ts", type=float, default=0.0)
    a = ap.parse_args()

    ev = load_jsonl(a.jsonl, a.since_ts)
    steps = [e for e in ev if e.get("ev") == "step"]
    deals = [e for e in ev if e.get("ev") == "deal_end"]
    recs = [e for e in ev if e.get("ev") == "recover"]

    rows: list[tuple] = []          # (编号, 指标, 值, 单位, 样本, 来源)

    def add(bid, name, val, unit, n, src="夜跑夜窗"):
        rows.append((bid, name, val, unit, n, src))

    # ---- L2-1 任务成功率 SR / R3 真实业务成功率: 从统计 CSV(我方升级=成功) ----
    wins = tot = 0
    try:
        for ln in open(a.csv, errors="ignore"):
            m = re.match(r"^(\d+),(\d+),(win|lose|\?),", ln)
            if m and int(m.group(1)) >= a.since_ts:
                tot += 1
                wins += 1 if m.group(3) == "win" else 0
    except FileNotFoundError:
        pass
    if tot:
        add("L2-1/R3", "任务成功率SR=真实业务成功率", round(100 * wins / tot, 1), "%", tot, "夜跑统计CSV")

    # ---- L2-2 端到端耗时(每局时长) ----
    durs = [e["dur"] for e in deals if e.get("dur")]
    if durs:
        add("L2-2", "端到端耗时(每局)", f"{st.mean(durs):.1f}±{st.pstdev(durs) / max(1, len(durs) ** 0.5):.1f}"
            f" (p50={pctl(durs, 50):.1f}, p95={pctl(durs, 95):.1f})", "s", len(durs))

    # ---- L2-3 GUI 每步延迟 / R7 操作延迟 ----
    if steps:
        dec = [e["t_decide"] for e in steps if e.get("t_decide")]
        exe = [e["t_exec"] for e in steps if e.get("t_exec")]
        snp = [e["t_snap"] for e in steps if e.get("t_snap")]
        if dec:
            add("L2-3/R7", "决策耗时", f"mean={st.mean(dec):.2f} p95={pctl(dec, 95):.2f}", "s", len(dec))
        if exe:
            add("L2-3/R7", "执行→回执耗时", f"mean={st.mean(exe):.2f} p95={pctl(exe, 95):.2f}", "s", len(exe))
        if snp:
            add("L2-3", "截屏耗时", f"mean={st.mean(snp):.3f} p95={pctl(snp, 95):.3f}", "s", len(snp))
        # ---- L2-4 交互延迟预算: 执行→画面反馈 分布 ----
        if exe:
            add("L2-4", "交互延迟(执行→反馈, 预算20ms)", f"p50={pctl(exe, 50):.3f} p95={pctl(exe, 95):.3f}", "s", len(exe))

    # ---- L2-7 SGA 子目标通过率 ----
    if steps:
        n = len(steps)
        read_ok = sum(1 for e in steps if e.get("read_ok") is True)
        read_try = sum(1 for e in steps if e.get("read_ok") is not None)
        exec_ok = sum(1 for e in steps if e.get("ok"))
        parts = [exec_ok / n]
        if read_try:
            parts.append(read_ok / read_try)
        add("L2-7", "子目标通过率SGA(执行有效+读牌正确均值)", round(100 * sum(parts) / len(parts), 1), "%", n)

    # ---- L2-6 长程完成率(局/小时) ----
    if deals:
        span = max(1e-6, (deals[-1]["ts"] - deals[0]["ts"]) / 3600)
        add("L2-6", "长程完成率", f"{len(deals) / span:.1f} 局/小时 (共{len(deals)}局)", "局/h", len(deals))

    # ---- L3-10 故障恢复 / L4-1 异常率 / L4-2 中断率 ----
    if recs:
        secs = [e["secs"] for e in recs if e.get("secs")]
        if secs:
            add("L3-10", "故障恢复耗时(看门狗重开)", f"mean={st.mean(secs):.1f} p95={pctl(secs, 95):.1f}", "s", len(secs))
    if steps:
        add("L4-1", "异常率(看门狗触发/每步)", round(100 * len(recs) / max(1, len(steps)), 2), "%", len(steps))
    if deals or steps:
        add("L4-2", "任务中断率(重开/局)", round(len(recs) / max(1, len(deals)), 2) if deals else "n/a", "次/局", len(deals))

    # ---- L1-5 CPU抖动 / L3-7 资源利用率: 从宿主采样 ----
    cpu, mem = [], []
    try:
        for ln in open(a.host, errors="ignore"):
            parts = ln.strip().split(",")
            if len(parts) >= 3 and parts[0].replace(".", "", 1).isdigit():
                cpu.append(float(parts[1]))
                mem.append(float(parts[2]))
    except FileNotFoundError:
        pass
    if cpu:
        add("L1-5", "容器CPU使用抖动(p95/p50)", f"{pctl(cpu, 95) / max(1e-6, pctl(cpu, 50)):.2f}", "比值", len(cpu), "宿主采样")
        add("L3-7", "容器资源利用率(CPU/内存均值)", f"CPU={st.mean(cpu):.1f}% MEM={st.mean(mem):.1f}%", "%", len(cpu), "宿主采样")

    # ---- R2 真实App启动率: 从日志(prep 是否成功) ----
    ok = fail = 0
    try:
        txt = open(a.log, errors="ignore").read()
        ok = txt.count("[prep] ✅ 已开局") + txt.count("已在对局内")
        fail = txt.count("[prep] ⚠️ 未确认开局")
    except FileNotFoundError:
        pass
    if ok or fail:
        add("R2", "真实App(游戏页)启动率", round(100 * ok / max(1, ok + fail), 1), "%", ok + fail, "夜跑日志")

    # ---- 写出 ----
    with open(a.out, "a") as fo:
        for r in rows:
            fo.write(",".join(str(x) for x in r) + "\n")
    print(f"[指标] 本窗产出 {len(rows)} 行 → {a.out}")
    for r in rows:
        print(f"  [{r[0]:8s}] {r[1][:32]:34s} {r[2]} {r[3]}  (n={r[4]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
