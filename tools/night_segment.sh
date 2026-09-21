#!/usr/bin/env bash
# 夜跑·一段 —— 每次只跑**一个臂**, 跑哪边由库里数据量决定(谁少跑谁 ✓)
#
# 用户(2026-09-21): "写一个夜跑吧，一个是RL一个是游戏ai，分别跑"
# 纪律(用户 2026-09-21 定的形态):
#   · 单纯跑代码 + 记时间 ✓ 数据通过 sink 直接进 sqlite ✓ (不搞 json ✗)
#   · 报告用 tools/run_summary.py **只读库** ✓
#   · 同一设备**只能一个托管** ⇒ 有在跑的就跳过 ✓
#   · 臂轮流(库里哪边少跑哪边 ✓) ⇒ 两组条件相近, 可对比 ✓
#
# 用法: bash tools/night_segment.sh [段秒数, 默认 1200]
set -u
cd /project1/landlord-counter || exit 1
export PATH=/usr/local/lib/hermes-agent/venv/bin:$PATH
export PYTHONPATH=src

RUN=/tmp/nightrun
mkdir -p "$RUN"
TS=$(date '+%Y%m%d-%H%M%S')
LOG="$RUN/timeline.txt"

# ① 时段闸门: 只在夜跑时段(22:30~07:15)跑 ✓ —— 白天让人用设备 ✓
H=$(date +%H); MI=$(date +%M)
if [ "$H" -ge 7 ] && [ "$H" -lt 22 ]; then
  echo "$(date '+%F %T') [停] 不在夜跑时段(22:30~07:15)" >> "$LOG"; exit 0
fi
if [ "$H" -eq 7 ] && [ "$MI" -gt 15 ]; then
  echo "$(date '+%F %T') [停] 过点了" >> "$LOG"; exit 0
fi

# ② 不并发: 已有托管在跑就让路 ✓ (同一台设备只允许一个 ✓)
if pgrep -f '[r]un_via_platform' >/dev/null 2>&1; then
  echo "$(date '+%F %T') [跳过] 已有托管在跑" >> "$LOG"; exit 0
fi

# ③ 本轮起点(存库里 ✓) + 选臂: 本轮里谁跑得少选谁 ⇒ 严格交替 ✓
python3 "$(dirname "$0")/night_arm.py" >> "$LOG" 2>&1
ARM=$(python3 "$(dirname "$0")/night_pick_arm.py")
echo "$(date '+%F %T') [起跑] arm=$ARM 时长=$(( ${1:-1200} / 60 ))分" >> "$LOG"

# ④ 设备/页面就绪(醒了 / 进桌 ✓) —— 复用现成工具, 失败也往下走(托管自己会等 ✓)
timeout 120 bash tools/wake_up.sh        >> "$RUN/prep-$TS.log" 2>&1 || true
timeout 240 python3 tools/guandan_prep.py >> "$RUN/prep-$TS.log" 2>&1 || true

# ⑤ 跑一段
L="$RUN/$ARM-$TS.log"
GUANDAN_OURS=1 GUANDAN_ARM="$ARM" timeout "${1:-1200}" python3 -u tools/run_via_platform.py > "$L" 2>&1

# ⑥ 记时间 + 质量计数(日志只用于排查 ✓ 数据仍以库为准 ✓)
echo "$(date '+%F %T') [结束] arm=$ARM 出牌=$(grep -c '直选出牌' "$L" 2>/dev/null) 对账=$(grep -c '\[对账\]' "$L" 2>/dev/null) 被拒=$(grep -c '出牌被游戏拒绝' "$L" 2>/dev/null) 未生效=$(grep -c '出牌未生效' "$L" 2>/dev/null)" >> "$LOG"
