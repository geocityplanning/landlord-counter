#!/usr/bin/env python3
"""游戏真值采样器(仅实验室): 周期性把 window.__truth() 落盘, 供离线对账。

为什么: 纯视觉读回有 ±1 误差 ✗, 分不清"真多打一张"还是"读错一张";
插桩版游戏暴露的 __truth() 是**绝对真值** ✓ → 操作准确率才有可信基准。

落盘: data/truth/<YYYYmmdd_HHMM>.jsonl  一行一个快照
    {"t":…, "phase":…, "current":…, "hands":{0:[…zhi…],…}, "plays":[{t,seat,zhi,n}…]}

用法: PYTHONPATH=src python3 tools/truth_log.py [时长秒=1500] [间隔秒=1.5]
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.platform.cdp import CDP  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "truth")


def main() -> int:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 1500.0
    iv = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, time.strftime("%Y%m%d_%H%M") + ".jsonl")
    c = CDP()
    if not c.find_truth():
        print("✗ 没找到带 __truth 钩子的页面(需要插桩版 + 带时间戳的 URL 进桌)", flush=True)
        return 2
    print(f"▶ 真值采样: {path}  时长 {dur}s 间隔 {iv}s", flush=True)
    t_end = time.time() + dur
    n = 0
    seen_plays = 0
    while time.time() < t_end:
        try:
            t = c.truth()
            if t:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
                n += 1
                pl = len(t.get("plays") or [])
                if pl != seen_plays:
                    seen_plays = pl
                    p = (t.get("plays") or [])[-1]
                    if p:
                        seat = {0: "你(南)", 1: "ai1(东)", 2: "ai2(北)", 3: "ai3(西)"}.get(p.get("seat"), p.get("seat"))
                        z = " ".join(str(x) for x in p.get("zhi", []))
                        print(f"  [真值] {seat} 出 {z}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  (采样异常 {type(e).__name__})", flush=True)
        time.sleep(iv)
    print(f"▶ 结束: 共 {n} 个快照 → {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
