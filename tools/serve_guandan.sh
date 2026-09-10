#!/bin/bash
# 掼蛋 www 托管(幂等): 8123 未监听则用仓库内 reference/guandan/www 起服务
# 用法: bash tools/serve_guandan.sh   (手机侧访问 http://172.18.0.1:8123/index.html)
set -u
PORT=8123
DIR=/project1/landlord-counter/reference/guandan/www
PY=/usr/local/lib/hermes-agent/venv/bin/python3

if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  echo "[serve] $PORT 已在监听, 跳过"
  exit 0
fi
[ -f "$DIR/index.html" ] || { echo "[serve] 缺少 $DIR/index.html"; exit 1; }
if [ ! -x "$PY" ]; then PY=python3; fi
echo "[serve] 启动: $PY -m http.server $PORT --bind 0.0.0.0 --directory $DIR"
exec "$PY" -m http.server "$PORT" --bind 0.0.0.0 --directory "$DIR"
