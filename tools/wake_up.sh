#!/bin/bash
# 睡醒后拉回环境(2026-09-17 记录的做法)
export PATH=/usr/local/lib/hermes-agent/venv/bin:$PATH
cd /project1/landlord-counter || exit 1

echo "=== ① 容器 ==="
docker ps --format '{{.Names}}\t{{.Status}}' 2>/dev/null | head -5 || echo "  (docker 不可用)"

echo
echo "=== ② adb 连接 ==="
adb connect 127.0.0.1:5555 2>&1 | tail -1
adb -s 127.0.0.1:5555 shell getprop ro.build.version.release 2>&1 | tail -1
adb devices | tail -3

echo
echo "=== ③ MaaTouch ==="
if adb -s 127.0.0.1:5555 shell ps -A 2>/dev/null | grep -qi maatouch; then
    echo "  ✓ 已在跑"
else
    adb -s 127.0.0.1:5555 shell "CLASSPATH=/data/local/tmp/maatouch app_process /data/local/tmp com.shxyke.MaaTouch.App" >/dev/null 2>&1 &
    sleep 3
    adb -s 127.0.0.1:5555 shell ps -A 2>/dev/null | grep -ci maatouch | sed 's/^/  启动后实例数: /'
fi

echo
echo "=== ④ 常驻服务 ==="
for p in 8123 8130 8140; do
    printf "  :%s " $p
    curl -s -o /dev/null -w "%{http_code}\n" --max-time 2 "http://127.0.0.1:$p/" 2>/dev/null || echo "✗(需要重启)"
done

echo
echo "=== ⑤ 系统已记录的服务启动命令 ==="
ls -1 tools/*.py 2>/dev/null | head -20 | tr '\n' ' '
echo
