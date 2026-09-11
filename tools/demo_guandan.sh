#!/bin/bash
# 掼蛋一键演示: 进桌 + 托管 N 分钟 (+ 可选逐帧录屏)
# 用法: bash tools/demo_guandan.sh [分钟=6] [录制=1|0] [自研=1|0]
PY=/usr/local/lib/hermes-agent/venv/bin/python3
cd /project1/landlord-counter || exit 9
MIN=${1:-6}
REC=${2:-1}
OURS=${3:-0}
SECS=$((MIN * 60))
echo "=== 演示开始 $(date '+%F %T') 时长=${MIN}分钟 录制=${REC} 自研=${OURS} ==="
$PY tools/guandan_prep.py
if [ "$OURS" = "1" ]; then export GUANDAN_OURS=1; export STATS_TAG=ours; else export STATS_TAG=mvp; fi

FRAMES=/tmp/demo_frames
if [ "$REC" = "1" ]; then
  ( rm -rf $FRAMES; mkdir -p $FRAMES; i=0; end=$((SECONDS+SECS))
    while [ $SECONDS -lt $end ]; do
      i=$((i+1))
      adb -s 127.0.0.1:5555 exec-out screencap -p > $FRAMES/f_$(printf "%05d" $i).png
      sleep 0.05
    done
    echo "采集 $i 帧" ) &
fi

STATS_FILE=/tmp/guandan_stats.csv PYTHONPATH=src timeout $SECS \
  $PY -u -m landlord_counter.guandan.agent $((SECS - 10))

if [ "$REC" = "1" ]; then
  sleep 2
  OUT=/tmp/demo_guandan_$(date +%H%M).mp4
  ffmpeg -y -framerate 5 -i $FRAMES/f_%05d.png \
    -vf "drawtext=fontfile=/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc:text='云手机 AI 托管实拍 · 无人工干预':fontcolor=white:fontsize=26:box=1:boxcolor=black@0.55:boxborderw=10:x=(w-text_w)/2:y=h-90,format=yuv420p" \
    -c:v libx264 -preset veryfast -crf 26 -movflags +faststart $OUT 2>&1 | tail -1
  echo "演示视频: $OUT"
  ls -la $OUT
fi
echo "=== 演示结束 $(date '+%F %T') | 累计结算 $(wc -l < /tmp/guandan_stats.csv 2>/dev/null || echo 0) 行 ==="
