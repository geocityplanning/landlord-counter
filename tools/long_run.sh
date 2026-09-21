#!/usr/bin/env bash
# 长跑 + 数据记录 ✓ (用户 2026-09-21: "挂着长跑, 记录数据")
#
# 用法:
#   bash tools/long_run.sh [小时数] [每段秒数]      # 默认 2 小时, 每段 400 秒
#
# 它做三件事(都是"只读+记账", 不改牌局逻辑 ✓):
#   ① 分段跑托管(每段落盘一次, 断一段不影响整体 ✓)
#   ② 每 5 分钟存一次**指标快照**(JSONL) ⇒ 能看到"随时间的走势" ✓
#   ③ 全程日志留痕(/tmp/longrun/ ✓), 出问题可回查 ✓
#
# 为什么分段: 单段有超时上限, 分段后每段独立 ✓ 而且每段开头都会重新 prep ✓
set -u
cd "$(dirname "$0")/.." || exit 1
export PATH=/usr/local/lib/hermes-agent/venv/bin:$PATH
export PYTHONPATH=src

HOURS="${1:-2}"
SEG="${2:-400}"
OUT=/tmp/longrun
mkdir -p "$OUT"
STAMP=$(date +%Y%m%d-%H%M)

# 防重: 已有长跑在跑就别再起 ✓
if [ -f "$OUT/pid" ] && kill -0 "$(cat "$OUT/pid")" 2>/dev/null; then
  echo "已有长跑在跑(pid $(cat "$OUT/pid")) ⇒ 退出 ✓"; exit 0
fi
echo $$ > "$OUT/pid"

DEADLINE=$(( $(date +%s) + HOURS * 3600 ))
RUNLOG="$OUT/run-$STAMP.log"
MLOG="$OUT/metrics-$STAMP.jsonl"
echo "长跑开始 $(date '+%F %T')  小时=$HOURS  每段=${SEG}s" | tee "$RUNLOG"

# ① 指标快照(后台并行, 每 5 分钟一次 ✓)
(
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    TS=$(date '+%F %T')
    M=$(curl -s --max-time 8 http://127.0.0.1:8131/api/metrics 2>/dev/null)
    A=$(curl -s --max-time 8 http://127.0.0.1:8131/api/accuracy 2>/dev/null)
    if [ -n "$M" ]; then
      printf '{"t":"%s","metrics":%s,"accuracy":%s}\n' "$TS" "${M#*\"metrics\":}" "$A" >> "$MLOG"
    fi
    sleep 300
  done
) &
MLOG_PID=$!

# ② 分段跑
i=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  i=$((i + 1))
  echo "=== 第 $i 段  $(date '+%T') ===" >> "$RUNLOG"
  GUANDAN_OURS=1 GUANDAN_DECIDE=rl GUANDAN_ALLOW_WILD=1 \
    timeout "$SEG" python3 -u tools/run_via_platform.py >> "$RUNLOG" 2>&1
  sleep 3
done

kill "$MLOG_PID" 2>/dev/null
echo "长跑结束 $(date '+%F %T')  共 $i 段" | tee -a "$RUNLOG"
echo "  日志: $RUNLOG"
echo "  指标: $MLOG"
rm -f "$OUT/pid"
