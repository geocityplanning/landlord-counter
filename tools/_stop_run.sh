#!/bin/bash
# 停掉当前托管轮(用户要求: 提示驱动是错的 ✗)
ps -eo pid,cmd | grep "[r]un_via_platform" | awk '{print $1}' | xargs -r kill
sleep 2
echo "剩余托管进程: $(ps -eo cmd | grep -c '[r]un_via_platform')"
