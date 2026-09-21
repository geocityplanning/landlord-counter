#!/usr/bin/env bash
# 录一段"牌局中"的 1 分钟视频 ✓ (用户 2026-09-21: "录一段MP4, 一分钟, 确保是在牌局中的, 连续打牌")
#
# 判据(为什么要等): 现成录到的多半是"结算/发牌/大厅" ✗ ⇒ 用户明确要"牌局中连续打牌" ✓
#   ⇒ 等到"托管日志在最近 25 秒内被写过"才开录 —— 出牌才会写日志, 所以那一刻必然在打 ✓
#
# 主路: adb shell screenrecord 60s
# 备路(模拟器上 screenrecord 有时不出文件 ✗): screencap 连拍 → ffmpeg 合成
set -u
SER=127.0.0.1:5555
OUT=/tmp/guandan_live.mp4
LOG=/tmp/longrun/run.log
TMP=/tmp/rec_frames
LIMIT=${1:-600}          # 最多等多少秒等到"在打牌"的状态

echo "[录屏] $(date +%H:%M:%S) 等牌局中的状态(最多 ${LIMIT}s) ..."

# ---- ① 等: 托管进程活着 + 日志最近 25 秒内写过(=正在出牌) ----
t0=$(date +%s)
while :; do
  now=$(date +%s)
  [ $((now - t0)) -gt "$LIMIT" ] && { echo "[录屏] 超时: 一直没等到打牌状态 ✗"; exit 2; }
  if pgrep -f "[r]un_via_platform" >/dev/null 2>&1 && [ -f "$LOG" ]; then
    mt=$(stat -c %Y "$LOG" 2>/dev/null || echo 0)
    if [ $((now - mt)) -le 25 ]; then
      echo "[录屏] ✓ 检测到正在出牌(日志 $((${now}-${mt}))s 前刚写过) → 开录"
      break
    fi
  fi
  sleep 3
done

for i in 1 2 3; do adb connect $SER >/dev/null 2>&1; sleep 1; done
adb -s $SER shell rm -f /sdcard/gd_live.mp4 >/dev/null 2>&1

# ---- ② 主路: screenrecord 60 秒 ----
echo "[录屏] screenrecord 开录 60s ..."
adb -s $SER shell screenrecord --time-limit 60 --bit-rate 2000000 --size 720x1280 \
    /sdcard/gd_live.mp4 &
sleep 68
wait 2>/dev/null

adb -s $SER pull /sdcard/gd_live.mp4 "$OUT" >/dev/null 2>&1
SZ=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
echo "[录屏] screenrecord 产物: ${SZ} 字节"

# ---- ③ 备路: 主路失败 ⇒ screencap 连拍 + ffmpeg ----
if [ "$SZ" -lt 50000 ]; then
  echo "[录屏] 主路不行 ⇒ 走连拍合成(约 55 秒, 尽量密) ..."
  rm -rf "$TMP"; mkdir -p "$TMP"
  n=0; t1=$(date +%s)
  while [ $(( $(date +%s) - t1 )) -lt 55 ]; do
    adb -s $SER exec-out screencap -p > "$TMP/$(printf '%05d' $n).png" 2>/dev/null
    n=$((n+1))
  done
  echo "[录屏] 抓到 $n 帧 ($(echo "scale=1; $n/55" | bc 2>/dev/null || echo '?') fps)"
  ffmpeg -y -loglevel error -framerate 6 -i "$TMP/%05d.png" \
         -c:v libx264 -pix_fmt yuv420p -vf "scale=720:-2" "$OUT" 2>/dev/null
  SZ=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
  echo "[录屏] 合成产物: ${SZ} 字节"
fi

[ "$SZ" -lt 50000 ] && { echo "[录屏] ✗ 两条路都没产出可用视频"; exit 3; }

echo "[录屏] ✓ 完成: $OUT"
ls -la --time-style=+%H:%M:%S "$OUT"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT" 2>/dev/null | sed 's/^/  /'
