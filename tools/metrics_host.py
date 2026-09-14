#!/usr/bin/env python3
"""宿主采样器(夜跑期间后台跑): 每 N 秒记一次 容器CPU%/容器内存%、宿主 load/内存。

输出 CSV: ts,cpu_pct,mem_pct,host_load1,host_mem_used_mb
用于指标: L1-5 CPU时间片抖动、L3-7 资源利用率。
用法: python3 tools/metrics_host.py --secs 3600 --interval 15 --out /tmp/guandan_host.csv
"""
from __future__ import annotations

import argparse
import subprocess
import time


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
    except Exception:  # noqa: BLE001
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=3600)
    ap.add_argument("--interval", type=float, default=15)
    ap.add_argument("--out", default="/tmp/guandan_host.csv")
    ap.add_argument("--container", default="cloudphone-redroid")
    a = ap.parse_args()
    t_end = time.time() + a.secs
    while time.time() < t_end:
        stats = sh(["docker", "stats", "--no-stream", "--format",
                    "{{.CPUPerc}},{{.MemPerc}}", a.container]).strip().replace("%", "")
        cpu = mem = 0.0
        if "," in stats:
            try:
                cpu, mem = float(stats.split(",")[0]), float(stats.split(",")[1])
            except ValueError:
                pass
        load = (sh(["cat", "/proc/loadavg"]).split() or ["0"])[0]
        memused = 0
        for ln in sh(["free", "-m"]).splitlines():
            if ln.startswith("Mem:"):
                memused = int(ln.split()[2])
        with open(a.out, "a") as fo:
            fo.write(f"{round(time.time(), 1)},{cpu},{mem},{load},{memused}\n")
        time.sleep(a.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
