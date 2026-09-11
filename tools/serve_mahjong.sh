#!/bin/bash
# 麻将(電脳麻将)托管: 8124 → reference/mahjong (幂等: 已监听则跳过)
PORT=8124
ROOT=/project1/landlord-counter/reference/mahjong
if ss -ltn | grep -q ":$PORT "; then
  echo "[serve_mahjong] 已在监听 $PORT"
  exit 0
fi
cd "$ROOT" || exit 9
nohup python3 -m http.server $PORT --bind 0.0.0.0 > /tmp/serve_mahjong.log 2>&1 &
sleep 1
echo "[serve_mahjong] 启动 $PORT → $ROOT (pid $!)"
