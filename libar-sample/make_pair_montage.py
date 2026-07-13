# -*- coding: utf-8 -*-
"""학습쌍 몽타주 재생성 — 한글 정답을 PIL 폰트로 (cv2 putText는 한글 불가 → 이스케이프 문자열 사고 방지)."""
import io, sys, random
import cv2, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
D = HERE/"real_rec_data_v3"
random.seed(7)

rows = []
for ln in io.open(D/"meta_train.txt", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) >= 3 and p[2] == "pair": rows.append((p[0], p[1]))
random.shuffle(rows)
rows = rows[:24]
print("pair 크롭", len(rows), "개 선택")

CW, CH, LBL = 180, 84, 26                       # 셀 폭·크롭 높이·라벨 영역
COLS = 6
R = (len(rows)+COLS-1)//COLS
canvas = Image.new("RGB", (COLS*CW, R*(CH+LBL)+8), (250, 250, 250))
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
for i, (f, gt) in enumerate(rows):
    im = cv2.imdecode(np.fromfile(str(D/f), dtype=np.uint8), 1)
    if im is None: continue
    h, w = im.shape[:2]
    s = min((CW-8)/w, CH/h)
    im = cv2.resize(im, (int(w*s), int(h*s)))
    pi = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    cx, cy = (i % COLS)*CW, (i//COLS)*(CH+LBL)+4
    canvas.paste(pi, (cx + (CW-pi.width)//2, cy + (CH-pi.height)//2))
    tw = draw.textlength(gt, font=font)
    draw.text((cx + (CW-tw)/2, cy+CH+2), gt, fill=(200, 20, 20), font=font)

canvas.save(D/"pair_montage_3rd.jpg", quality=88)
print("저장:", D/"pair_montage_3rd.jpg")
