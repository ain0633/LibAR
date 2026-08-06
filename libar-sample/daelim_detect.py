# -*- coding: utf-8 -*-
"""대림 라벨 검출 (색 기반, 학습 불필요) — 행 프로파일 방식.
  1) 파란띠 마스크 → 행별 밀도로 '라벨 줄(row band)' 탐지 (contour 병합 문제 회피)
  2) 각 줄에서 파란 컬럼 세그먼트 = 띠 스트립
  3) 스트립 위 흰 스티커의 연속 컬럼으로 개별 라벨 분할
  출력: 사진별 라벨 박스 JSON + 시각화
"""
import sys, json
import cv2, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")

def detect_labels(bgr):
    H, W = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    blue = ((hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 135) &
            (hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 60)).astype(np.uint8)
    white = ((hsv[:, :, 1] < 75) & (hsv[:, :, 2] > 135)).astype(np.uint8)

    # 1) 라벨 줄: 파란 밀도가 높은 행 클러스터
    rowfrac = blue.mean(axis=1)
    thr = max(0.04, float(np.percentile(rowfrac, 90)) * 0.5)
    on = rowfrac > thr
    bands = []
    st = None
    for i, g in enumerate(list(on) + [False]):
        if g and st is None: st = i
        elif not g and st is not None:
            if 10 <= i - st <= 90: bands.append((st, i))
            st = None
    # 인접 밴드 병합
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] < 12:
            merged[-1] = (merged[-1][0], b[1])
        else:
            merged.append(list(b) if isinstance(b, tuple) else b)
        merged[-1] = tuple(merged[-1])
    bands = [b for b in merged if 10 <= b[1]-b[0] <= 110]

    labels = []
    for (by0, by1) in bands:
        strip = blue[by0:by1, :]
        colfrac = strip.mean(axis=0)
        onc = colfrac > 0.45
        segs = []
        st = None
        for i, g in enumerate(list(onc) + [False]):
            if g and st is None: st = i
            elif not g and st is not None:
                if i - st >= 14: segs.append((st, i))
                st = None
        bh = by1 - by0
        uy0 = max(0, by0 - int(bh * 2.9)); uy1 = by0
        for (sx0, sx1) in segs:
            reg = white[uy0:uy1, sx0:sx1]
            if reg.size == 0: continue
            wf = reg.mean(axis=0)
            onw = wf > 0.45
            st2 = None
            found = False
            for i, g in enumerate(list(onw) + [False]):
                if g and st2 is None: st2 = i
                elif not g and st2 is not None:
                    if i - st2 >= 13:
                        labels.append((sx0+st2, uy0, sx0+i, by1)); found = True
                    st2 = None
            if not found:                      # 흰 스티커 못 찾으면 스트립 자체를 라벨로
                labels.append((sx0, uy0, sx1, by1))
    return labels, bands

if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"..\대림데이터\KakaoTalk_20260707_135237882.jpg")
    im = Image.open(src).convert("RGB")
    bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    labels, bands = detect_labels(bgr)
    print(f"{src.name}: 라벨 줄 {len(bands)}개 → 라벨 박스 {len(labels)}개")
    d = ImageDraw.Draw(im)
    for (y0, y1) in bands:
        d.line([(0, y0), (im.width, y0)], fill=(0, 200, 0), width=2)
        d.line([(0, y1), (im.width, y1)], fill=(0, 200, 0), width=2)
    for b in labels: d.rectangle(list(b), outline=(255, 0, 0), width=3)
    json.dump(labels, open(f"daelim_labels_{src.stem[-2:]}.json", "w"))
    im.thumbnail((1800, 1800)); im.save("out_ondevice/daelim_color_det.jpg", quality=85)
    print("saved out_ondevice/daelim_color_det.jpg")
