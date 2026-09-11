#!/bin/bash
LOG=${1:-/tmp/gd_m4e1.log}
echo "== 总回落: $(grep -c '回落' $LOG) =="
for pat in "手牌读取失败" "桌面读取失败" "选牌校验失败" "出牌未生效" "读数.*vs 像素" "待压牌型非法" "选牌映射失败" "提示无可出" "无进展"; do
  n=$(grep -c "$pat" $LOG)
  [ "$n" -gt 0 ] && echo "  $pat: $n"
done
echo "== 出牌成功率 =="
echo "  自研出牌成功: $(grep -c '出牌(ours)' $LOG)"
echo "  回落提示钮执行成功: $(grep -c '✓ 出牌 (' $LOG)"
