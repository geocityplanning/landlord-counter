#!/bin/bash
# 掼蛋夜间长跑(窗口制 + A/B 对照 + 低产出告警)
# 奇数点=自研(OURS=1), 偶数点=提示驱动(MVP); 统计打标签; 产出异常直接报警(输出会被投递到 QQ)
PY=/usr/local/lib/hermes-agent/venv/bin/python3
cd /project1/landlord-counter || exit 9
LOG=/tmp/guandan_night.log
CSV=/tmp/guandan_stats.csv

# 注: 旧主循环(legacy)已补看门狗(连续3次动作无效 → 重开页面)与240s无进展重开
export GUANDAN_LEGACY=1
H=$(date +%H)
H=$((10#$H))
if [ $((H % 2)) -eq 1 ]; then
  export GUANDAN_OURS=1
  export STATS_TAG=ours
else
  export STATS_TAG=mvp
fi

START_LINE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
ROWS_BEFORE=$( [ -f "$CSV" ] && wc -l < "$CSV" || echo 0 )

# 保底1: 8123 游戏页服务没起就自动拉起(手工进程掉了会导致整夜白跑)
if ! curl -s -o /dev/null --max-time 5 http://127.0.0.1:8123/index.html; then
  echo "[guard] 8123 无响应 → 自动拉起静态服务 $(date '+%F %T')" >> "$LOG"
  nohup $PY -m http.server 8123 --bind 0.0.0.0 --directory reference/guandan/www >> "$LOG" 2>&1 &
  sleep 3
  curl -s -o /dev/null --max-time 5 http://127.0.0.1:8123/index.html && echo "[guard] 8123 已就绪" >> "$LOG"
fi
# 保底2: 设备连接(容器重启后 adb 会掉)
adb connect 127.0.0.1:5555 >/dev/null 2>&1

echo "=== 掼蛋夜跑窗口开始 $(date '+%F %T') 模式=$STATS_TAG ===" >> "$LOG"
$PY tools/guandan_prep.py >> "$LOG" 2>&1
WIN=${GUANDAN_WIN:-3240}          # 窗口时长(秒), 可用 GUANDAN_WIN 覆盖便于测试
STATS_FILE=$CSV PYTHONPATH=src timeout $((WIN + 60)) \
  $PY -u -m landlord_counter.guandan.agent "$WIN" >> "$LOG" 2>&1
rc=$?
echo "--- 窗口结束 rc=$rc ($STATS_TAG) $(date '+%F %T')" >> "$LOG"

ROWS_AFTER=$( [ -f "$CSV" ] && wc -l < "$CSV" || echo 0 )
DELTA=$((ROWS_AFTER - ROWS_BEFORE))
END_LINE=$(wc -l < "$LOG")
SEG=$(sed -n "$((START_LINE + 1)),${END_LINE}p" "$LOG")
ACTS=$(echo "$SEG" | grep -o "累计出牌[0-9]* 不出[0-9]*" | tail -1)
RECOVER=$(echo "$SEG" | grep -c "看门狗")
STALL=$(echo "$SEG" | grep -c "动作无效")

# 汇总(始终输出)
$PY - "$CSV" <<'PYEOF'
import re, sys
rows = []
for ln in open(sys.argv[1], errors='ignore'):
    m = re.match(r'^\d+,\d+,(win|lose|\?),([a-z\-]*),', ln)
    if m:
        rows.append((m.group(1), m.group(2)))
from collections import Counter
c = Counter(rows)
tot = len(rows)
w = sum(1 for r in rows if r[0] == 'win')
print(f"累计 {tot} 局: 我方升级 {w} ({100*w/max(1,tot):.0f}%)")
for tag in ('ours', 'mvp'):
    n = sum(1 for r in rows if r[1] == tag)
    ww = sum(1 for r in rows if r[1] == tag and r[0] == 'win')
    if n:
        print(f"  {tag}: {n} 局, 我方升级 {ww} ({100*ww/n:.0f}%)")
PYEOF

# 低产出告警(窗口记录 <5 局视为异常)
if [ "$DELTA" -lt 5 ]; then
  echo "⚠️ 掼蛋夜跑告警 | $(date '+%m-%d %H:%M') 模式=$STATS_TAG | 本窗仅记录 ${DELTA} 局(异常)"
  echo "   窗口内动作: ${ACTS:-无} | 看门狗触发 ${RECOVER} 次 | 判定卡死 ${STALL} 次"
  echo "   可能原因: 页面不吃点击/浏览器卡死; 建议人工看一眼 (bash /root/.hermes/scripts/guandan_night.sh 可补跑)"
else
  echo "✅ 掼蛋夜跑窗口正常 | $(date '+%m-%d %H:%M') 模式=$STATS_TAG | 本窗记录 ${DELTA} 局 | ${ACTS:-无} | 看门狗 ${RECOVER} 次"
fi
