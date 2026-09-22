#!/usr/bin/env bash
# 起 8140 手动操作台 —— 口令从**持久位置**读 ✓
#
# ⚠ 2026-09-22 修的隐患: 口令原来在 /tmp/live_token ⇒ 机器重启(/tmp 被清)就没了
#   ⇒ 服务读到空串 ⇒ **静默失去口令保护** ✗ (页面谁都能开, 不报错 ✗)
#   现在放 /root/.live_token(持久 ✓), 没有就现生成一个 ✓
#
# 用法: bash tools/start_live_view.sh [端口=8140] [fps=2]
TOKF=/root/.live_token
if [ ! -s "$TOKF" ]; then
  head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$TOKF"
  echo "▶ 已生成新口令 → $TOKF"
fi
[ -s /tmp/live_token ] || cp "$TOKF" /tmp/live_token 2>/dev/null || true   # 兼容旧路径 ✓

cd /project1/landlord-counter || exit 1
export PATH=/usr/local/lib/hermes-agent/venv/bin:$PATH
export PYTHONPATH=src
export LIVE_TOKEN=$(cat "$TOKF")
echo "▶ 手动操作台: 口令文件 $TOKF (长度 $(wc -c < "$TOKF") 字节)"
exec python3 tools/live_view.py "${1:-8140}" "${2:-2}"
