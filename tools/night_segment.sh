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
# 用法: bash tools/night_segment.sh [段秒数, 默认 3300 = 55 分钟]
#
# ⚠ 为什么一段要够长(用户 2026-09-21 指出):
#   掼蛋**一整场要以"过A"才算赢** ⇒ 30 分钟可能连一场都打不完 ✗
#   ⇒ 段长改 55 分钟(配 60 分钟一次的定时, 留 5 分钟余量 ✓)
#   ⇒ 一晚约 12 段 ⇒ 每个臂约 6 段 ⇒ 每臂能打几整场 ✓
set -u
cd /project1/landlord-counter || exit 1
export PATH=/usr/local/lib/hermes-agent/venv/bin:$PATH
export PYTHONPATH=src

RUN=/tmp/nightrun
mkdir -p "$RUN"
TS=$(date '+%Y%m%d-%H%M%S')
LOG="$RUN/timeline.txt"

# ① 时段闸门: **19:00 开始, 到早上 06:00 为止发车**(最后一段 06:00~06:55 ✓)
#    ⇒ 早上 7 点前收工 ✓ 白天(06:00~19:00)让设备给人用 ✓
H=$(date +%H)
if [ "$H" -ge 6 ] && [ "$H" -lt 19 ]; then
  echo "$(date '+%F %T') [停] 不在夜跑时段(19:00~次日 06:00)" >> "$LOG"; exit 0
fi

# ② 不并发: 已有托管在跑就让路 ✓ (同一台设备只允许一个 ✓)
if pgrep -f '[r]un_via_platform' >/dev/null 2>&1; then
  echo "$(date '+%F %T') [跳过] 已有托管在跑" >> "$LOG"; exit 0
fi

# ③ 本轮起点(存库里 ✓) + 选臂: 本轮里谁跑得少选谁 ⇒ 严格交替 ✓
python3 "$(dirname "$0")/night_arm.py" >> "$LOG" 2>&1
ARM=$(python3 "$(dirname "$0")/night_pick_arm.py")
echo "$(date '+%F %T') [起跑] arm=$ARM 时长=$(( ${1:-3300} / 60 ))分" >> "$LOG"

# ④ 设备/页面就绪(醒了 / 进桌 ✓) —— 复用现成工具, 失败也往下走(托管自己会等 ✓)
timeout 120 bash tools/wake_up.sh        >> "$RUN/prep-$TS.log" 2>&1 || true
timeout 240 python3 tools/guandan_prep.py >> "$RUN/prep-$TS.log" 2>&1 || true

# ⑤ 跑一段
L="$RUN/$ARM-$TS.log"
GUANDAN_OURS=1 GUANDAN_ARM="$ARM" timeout "${1:-3300}" python3 -u tools/run_via_platform.py > "$L" 2>&1

# ⑥ 记时间 + 质量计数(日志只用于排查 ✓ 数据仍以库为准 ✓)
echo "$(date '+%F %T') [结束] arm=$ARM 出牌=$(grep -c '直选出牌' "$L" 2>/dev/null) 对账=$(grep -c '\[对账\]' "$L" 2>/dev/null) 被拒=$(grep -c '出牌被游戏拒绝' "$L" 2>/dev/null) 未生效=$(grep -c '出牌未生效' "$L" 2>/dev/null)" >> "$LOG"
