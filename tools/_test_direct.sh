#!/bin/bash
# 直选端到端测试: 重置牌桌 → 跑一轮 → 汇总
export PATH=/usr/local/lib/hermes-agent/venv/bin:$PATH
cd /project1/landlord-counter || exit 1
python3 -m py_compile src/landlord_counter/platform/gestures.py || exit 1
echo "[1] 重置牌桌"
bash tools/reset_table.sh 2>&1 | tail -3
echo "[2] 直选窗口 240s"
GUANDAN_OURS=1 GUANDAN_DECIDE=rl PYTHONPATH=src timeout 280 \
  python3 tools/run_via_platform.py 240 guandan > /tmp/d5.log 2>&1
echo "[3] 结果"
echo "  成功 $(grep -cE 'ok=True' /tmp/d5.log) / 失败 $(grep -cE 'ok=False' /tmp/d5.log)"
grep -E "\[动作\]|组选完成|直选出牌|残留|身份校验" /tmp/d5.log | tail -12
