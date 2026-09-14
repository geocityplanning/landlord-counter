#!/bin/bash
# 掼蛋夜跑启动检查(21:05): 检查托管进程/网页服务/已结算局数, 输出短讯(供 QQ 提醒)
LOG=/tmp/guandan_night.log
CSV=/tmp/guandan_stats.csv
alive=$(pgrep -f "landlord_counter.guandan.agent" | wc -l)
svc=$(ss -ltn 2>/dev/null | grep -c ':8123 ')
[ -f "$CSV" ] && deals=$(wc -l < "$CSV") || deals=0
last=$( [ -f "$LOG" ] && tail -2 "$LOG" | tr '\n' ' ' | cut -c1-160 || echo '(暂无日志)')
echo "【掼蛋夜跑检查】托管进程:${alive} | 网页服务:${svc} | 已结算:${deals}局"
echo "最近日志: ${last}"
if [ "$alive" -eq 0 ]; then
  echo "⚠️ 夜跑未在运行! 可手动补跑: bash /root/.hermes/scripts/guandan_night.sh"
fi
