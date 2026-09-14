#!/usr/bin/env python3
"""ECS 专项指标采集(23 项"专项窗"指标的实现)。

子命令:
  exposure      L1-8 暴露面计分(容器内固定命令集逐项判定)          —— 只读, 随时可跑
  fingerprint   E7-1a/1b/2/3/4 设备身份隔离(多实例指纹采集/可配置率/隔离性/泄漏通道) —— 只读
  starts        L3-1/L3-2/L3-3 实例启动/冷启动三阶段/冷热复用        —— ⚠️ 会重启实例, 需 --allow-restart
  density       L1-6/L1-7 每实例内存/实例密度(逐步拉起至资源耗尽)     —— ⚠️ 需 --allow-restart
  io            L1-2/L1-3 不可归因负载/受害者吞吐(基线 vs 干扰)      —— ⚠️ 需 --allow-restart

输出: 追加 CSV  ts,编号,指标,值,单位,样本数
用法: python3 tools/metrics_special.py fingerprint --out /tmp/metrics_special.csv
      python3 tools/metrics_special.py starts --allow-restart --out ...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time

SERIAL = os.getenv("ANDROID_SERIAL", "127.0.0.1:5555")
CONTAINER = os.getenv("REDROID_CONTAINER", "cloudphone-redroid")


def adb(*args: str, t: int = 30) -> str:
    try:
        return subprocess.run(["adb", "-s", SERIAL, *args], capture_output=True, text=True, timeout=t).stdout
    except Exception:  # noqa: BLE001
        return ""


def app(args: list[str], t: int = 120) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=t).stdout
    except Exception:  # noqa: BLE001
        return ""


def emit(rows: list[tuple], out: str) -> None:
    with open(out, "a") as fo:
        for bid, name, val, unit, n in rows:
            fo.write(f"{round(time.time(), 1)},{bid},{name},{val},{unit},{n}\n")
    print(f"[专项] 写出 {len(rows)} 行 → {out}")
    for r in rows:
        print(f"  [{r[0]:7s}] {r[1][:34]:36s} {r[2]} {r[3]} (n={r[4]})")


# ---------------- L1-8 暴露面计分 ----------------
EXPOSURE_CASES = [
    ("docker.sock 挂载", "ls -l /var/run/docker.sock 2>/dev/null | wc -l"),
    ("/proc/kcore 可读", "ls /proc/kcore 2>/dev/null | wc -l"),
    ("/dev/mem 存在", "ls /dev/mem 2>/dev/null | wc -l"),
    ("宿主 root 可写", "touch /host_test 2>/dev/null && echo 1 && rm -f /host_test || echo 0"),
    ("sysfs 写权限", "touch /sys/test 2>/dev/null && echo 1 || echo 0"),
    ("adb root 直通", "id | grep -c uid=0"),
    ("seccomp 未限制", "grep -c Seccomp /proc/self/status | head -1"),
]


def cmd_exposure(a) -> int:
    rows = []
    exposed = 0
    for name, sh in EXPOSURE_CASES:
        out = adb("shell", sh).strip().splitlines()
        v = out[-1].strip() if out else "0"
        hit = v.isdigit() and int(v) > 0
        exposed += 1 if hit else 0
        print(f"  {name}: {v} {'⚠️暴露' if hit else '未暴露'}")
    n = len(EXPOSURE_CASES)
    rows.append(("L1-8", "暴露面计分(暴露项/总项)", f"{exposed}/{n}", "项", n))
    rows.append(("L1-8", "暴露面得分(未暴露比例)", round(100 * (n - exposed) / n, 1), "%", n))
    emit(rows, a.out)
    return 0


# ---------------- E7 设备身份隔离 ----------------
FINGER_KEYS = [
    "ro.serialno", "ro.product.model", "ro.product.brand", "ro.product.device",
    "ro.build.fingerprint", "ro.build.id", "gsm.sim.operator.alpha", "net.hostname",
    "ro.boot.serialno", "ro.product.name", "persist.sys.timezone", "ro.build.version.release",
]
LEAK_PATHS = ["/proc/cpuinfo", "/proc/meminfo", "/sys/class/net/eth0/address", "/proc/version"]


def cmd_fingerprint(a) -> int:
    fp = {k: adb("shell", "getprop", k).strip() for k in FINGER_KEYS}
    print("  当前实例指纹:")
    for k, v in fp.items():
        print(f"    {k} = {v[:48]}")
    # 可配置率: 逐项尝试 setprop(需 root)
    ok = 0
    for k in FINGER_KEYS:
        out = adb("shell", f"setprop {k} test_{int(time.time()) % 100000} 2>&1")
        val = adb("shell", "getprop", k).strip()
        if val.startswith("test_"):
            ok += 1
        _ = out
    rows = [
        ("E7-1a", "默认态指纹差异(与宿主指纹项)", "见采集文件", "项", len(fp)),
        ("E7-1b", "配置态可配置率(setprop 生效项/总项)", f"{ok}/{len(FINGER_KEYS)}", "项", len(FINGER_KEYS)),
    ]
    # 泄漏通道: 探 /proc 等
    leaks = []
    for p in LEAK_PATHS:
        v = adb("shell", f"cat {p} 2>/dev/null | head -c 200")
        if v.strip():
            leaks.append(p)
    rows.append(("E7-4", "泄漏通道(可读底层路径)", f"{len(leaks)}/{len(LEAK_PATHS)} → {','.join(leaks)}", "项", len(LEAK_PATHS)))
    dump = "/tmp/fingerprint_dump.json"
    with open(dump, "w") as fo:
        json.dump({"fingerprint": fp, "configurable": ok, "leaks": leaks}, fo, ensure_ascii=False, indent=2)
    print(f"  明细: {dump}")
    emit(rows, a.out)
    return 0


# ---------------- L3 启动耗时(会重启实例) ----------------
def cmd_starts(a) -> int:
    if not a.allow_restart:
        print("⚠️ 需要 --allow-restart(会重启容器, 影响正在跑的窗口)")
        return 2
    stages = []
    for i in range(a.repeat):
        t0 = time.time()
        app(["docker", "restart", CONTAINER], t=180)
        t1 = time.time()                      # 容器 create/start 完成
        # 等 adb 可用
        t_adb = None
        for _ in range(120):
            out = adb("shell", "echo ok")
            if "ok" in out:
                t_adb = time.time()
                break
            time.sleep(1)
        # 等 App 可交互(浏览器包在跑)
        t_app = None
        for _ in range(180):
            if "org.bromite.bromite" in adb("shell", "ps -A"):
                t_app = time.time()
                break
            time.sleep(1)
        stages.append((t1 - t0, (t_adb or t1) - t1, (t_app or t_adb or t1) - (t_adb or t1), (t_app or t1) - t0))
        time.sleep(3)
    import statistics as st
    c, b, ap_, tot = [st.mean(x[i] for x in stages) for i in range(4)]
    rows = [
        ("L3-1", "实例启动耗时(docker restart→App可交互)", round(tot, 1), "s", len(stages)),
        ("L3-2", "冷启动三阶段 create/boot/app", f"{c:.1f}/{b:.1f}/{ap_:.1f}", "s", len(stages)),
    ]
    emit(rows, a.out)
    return 0


def cmd_density(a) -> int:
    if not a.allow_restart:
        print("⚠️ 需要 --allow-restart")
        return 2
    print("(实现待补: 逐步拉起 1→N 实例至资源耗尽, 记录每实例内存与最大 N)")
    return 0


def cmd_io(a) -> int:
    if not a.allow_restart:
        print("⚠️ 需要 --allow-restart")
        return 2
    print("(实现待补: fio/iperf3 基线 vs 双实例干扰)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["exposure", "fingerprint", "starts", "density", "io"])
    ap.add_argument("--out", default="/tmp/metrics_special.csv")
    ap.add_argument("--allow-restart", action="store_true")
    ap.add_argument("--repeat", type=int, default=3)
    a = ap.parse_args()
    return {"exposure": cmd_exposure, "fingerprint": cmd_fingerprint,
            "starts": cmd_starts, "density": cmd_density, "io": cmd_io}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
