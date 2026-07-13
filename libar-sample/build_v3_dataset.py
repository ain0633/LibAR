# -*- coding: utf-8 -*-
"""v3 학습셋 조립 — v2 수확분(354) + 페어 이식분(16)을 줄높이로 층화 태그.

v2 실패 원인(저해상 쏠림) 대응: 크롭을 근접(h≥32px)/저해상(<32px)으로 태그해서
Colab 노트북에서 배합 비율을 조절할 수 있게 meta 형식으로 저장.
"""
import io, sys, os, glob, random, shutil
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
random.seed(42)
OUT = HERE/"real_rec_data_v3"
(OUT/"crops").mkdir(parents=True, exist_ok=True)

items = []  # (경로, 텍스트, 태그)
# 1) v2 수확분 복사
for split in ("train.txt", "val.txt"):
    for ln in io.open(HERE/"real_rec_data"/split, encoding="utf-8").read().splitlines():
        p, t = ln.split("\t")
        src = HERE/"real_rec_data"/p
        dst = OUT/p
        if not dst.exists(): shutil.copy2(src, dst)
        im = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), 1)
        tag = "close" if im.shape[0] >= 32 else "low"
        items.append((p, t, tag))
# 2) 페어 이식분 (전부 저해상 hard)
for ln in io.open(OUT/"pairs.txt", encoding="utf-8").read().splitlines():
    p, t = ln.split("\t")
    items.append((p, t, "pair"))

random.shuffle(items)
n_val = max(4, len(items)//10)
val, train = items[:n_val], items[n_val:]
for name, rows in (("meta_train.txt", train), ("meta_val.txt", val)):
    io.open(OUT/name, "w", encoding="utf-8").write("".join(f"{p}\t{t}\t{g}\n" for p, t, g in rows))

from collections import Counter
c = Counter(g for _, _, g in items)
print(f"[v3 학습셋] 총 {len(items)}줄 — 근접 {c['close']} · 저해상 {c['low']} · 페어 {c['pair']}")
print(f"[분할] train {len(train)} / val {len(val)}")

import zipfile
z = zipfile.ZipFile(HERE/"real_rec_data_v3.zip", "w", zipfile.ZIP_DEFLATED)
for f in glob.glob(str(OUT/"**/*"), recursive=True):
    if os.path.isfile(f) and "montage" not in f and not f.endswith("pairs.txt"):
        z.write(f, os.path.relpath(f, HERE).replace(os.sep, "/"))
z.close()
print(f"[저장] real_rec_data_v3.zip {os.path.getsize(HERE/'real_rec_data_v3.zip')/1e6:.1f}MB")
