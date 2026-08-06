#!/bin/sh
# rec v2 A/B — 구간별 기준샷 3장 (캐시 접미사 _ft2로 분리되어 v1 캐시 오염 없음)
PY="C:/Users/ain06/AppData/Local/Programs/Python/Python312/python.exe"
export PYTHONIOENCODING=utf-8

echo "=== v2 · 800 광각 기준샷 ==="
"$PY" daelim_closeup.py "../대림데이터/KakaoTalk_20260707_135237882.jpg" --rec_dir korean_lowres_v2_rec_infer 2>&1 | grep -E "^\[밴드\]|^\[줄|^\[청구|^\[이중|^\[오배열|^\[중복|^\[완료\]"
echo "=== v2 · 600 기준샷 ==="
"$PY" daelim_closeup.py "../대림데이터/600번대/KakaoTalk_20260708_163804413.jpg" --rec_dir korean_lowres_v2_rec_infer --catalog catalog_600.csv 2>&1 | grep -E "^\[밴드\]|^\[줄|^\[청구|^\[이중|^\[오배열|^\[중복|^\[완료\]"
echo "=== v2 · 700 기준샷 ==="
"$PY" daelim_closeup.py "../대림데이터/700번대/KakaoTalk_20260708_164051931.jpg" --rec_dir korean_lowres_v2_rec_infer --catalog catalog_700.csv 2>&1 | grep -E "^\[밴드\]|^\[줄|^\[청구|^\[이중|^\[오배열|^\[중복|^\[완료\]"
echo "=== v2 A/B 완료 ==="
