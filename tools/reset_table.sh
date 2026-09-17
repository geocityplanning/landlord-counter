#!/bin/bash
# 重置牌桌: 关掉浏览器 → 重新打开游戏页(带调试口) → 进桌
export PATH=/usr/local/lib/hermes-agent/venv/bin:$PATH
cd /project1/landlord-counter || exit 1
echo "[1/3] 关掉 Bromite(云手机里的游戏浏览器)"
adb -s 127.0.0.1:5555 shell am force-stop org.bromite.bromite
sleep 3
echo "[2/3] 重开游戏页 + 进桌"
PYTHONPATH=src timeout 200 python3 tools/guandan_prep.py 2>&1 | tail -3
echo "[3/3] 现场核对"
PYTHONPATH=src timeout 120 python3 - <<'PY'
from landlord_counter.platform.cdp import CDP
from landlord_counter.guandan import percept as P
from landlord_counter.platform.device import AdbDevice
c = CDP(); ok = c.find_truth(); print("真值钩子:", ok)
if ok:
    t = c.truth() or {}
    print("阶段", t.get("phase"), "| 轮到", t.get("current"),
          "| selected =", t.get("selected"),
          "| 四家张数", {k: len(v) for k, v in (t.get("hands") or {}).items()})
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
f = dev.snap()
print("lifted_px =", P.lifted_px(f), "(空≈197)")
rd, _ = P.tm_read_hand(f)
print("读取张数:", len(rd))
PY
