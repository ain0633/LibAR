#!/bin/bash
# 걷기 표본 재측정: 5장 간격 30프레임 — v3 검출기 예비 판정용 (전체 10시간 전 2시간 신호)
cd "$(dirname "$0")"
n=0
for f in $(ls ../대림데이터/3차데이터/vid_frames_all/*.jpg | awk 'NR % 5 == 1'); do
  n=$((n+1))
  echo "--- [$n] $(basename "$f") ---"
  py -3.12 daelim_yolo_pipeline.py "$f" --catalog catalog_900.csv --no_title --yolo call_label_yolo3/best.onnx 2>&1 | grep -E "검출|매칭|Traceback|Error"
done
echo WALK-SAMPLE-DONE
