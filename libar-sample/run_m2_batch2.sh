#!/bin/sh
# M2 재실행 잔여분 (600_10·600_11 + 700 전체)
PY="C:/Users/ain06/AppData/Local/Programs/Python/Python312/python.exe"
export PYTHONIOENCODING=utf-8

for f in "../대림데이터/600번대/KakaoTalk_20260708_163804413_10.jpg" "../대림데이터/600번대/KakaoTalk_20260708_163804413_11.jpg"; do
  echo "=== 600 · $f ==="
  "$PY" daelim_closeup.py "$f" --rec_dir korean_lowres_rec_infer --catalog catalog_600.csv 2>&1 | grep -E "^\[밴드\]|^\[줄|^\[청구|^\[이중|^\[오배열|^\[중복|^\[완료\]"
done
for f in "../대림데이터/700번대"/*.jpg; do
  echo "=== 700 · $f ==="
  "$PY" daelim_closeup.py "$f" --rec_dir korean_lowres_rec_infer --catalog catalog_700.csv 2>&1 | grep -E "^\[밴드\]|^\[줄|^\[청구|^\[이중|^\[오배열|^\[중복|^\[완료\]"
done
echo "=== M2 배치2 완료 ==="
