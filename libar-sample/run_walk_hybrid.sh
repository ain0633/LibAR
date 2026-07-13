#!/bin/bash
# 걷기 동영상 151프레임 하이브리드 재측정 (실시간 경로: --no_title 직독+투표만)
cd "$(dirname "$0")"
n=0
for f in ../대림데이터/3차데이터/vid_frames_all/*.jpg; do
  n=$((n+1))
  echo "--- [$n/151] $(basename "$f") ---"
  py -3.12 daelim_yolo_pipeline.py "$f" --catalog catalog_900.csv --no_title 2>&1 | grep -E "검출|매칭|Error|Traceback"
done
echo WALK-HYBRID-DONE
