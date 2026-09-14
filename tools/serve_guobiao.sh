#!/bin/bash
# 国标麻将(guobiao-majiang)托管: 8125 端口, 供云手机内浏览器访问
# 用法: bash tools/serve_guobiao.sh [端口]
set -e
PORT="${1:-8125}"
cd "$(dirname "$0")/../reference/guobiao-majiang" || exit 9
if [ ! -d node_modules ]; then
  echo "[setup] 安装依赖(npm 镜像)"
  npm install --registry https://registry.npmmirror.com --no-audit --no-fund
fi
echo "[serve] 国标麻将: http://0.0.0.0:${PORT}/  (容器内用 http://172.18.0.1:${PORT}/)"
PORT="$PORT" exec node server.js
