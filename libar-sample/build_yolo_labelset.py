# -*- coding: utf-8 -*-
"""YOLO26n 라벨 검출기 학습셋 — 파이프라인이 검증한 라벨 박스를 자동 라벨로 변환.

클래스 1개(call_label). 박스 = result.json의 책별 라벨 스트립 박스(흰 라벨+색 스티커).
검출이 붕괴한 강한 각도 프레임(라벨 신뢰 불가)은 제외 — 각도 강건성은 학습 증강(perspective)으로 확보.

출력: yolo_labelset/{images,labels}/{train,val}/ + data.yaml → yolo_labelset.zip
"""
import json, sys, io, glob, os, shutil, random
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
random.seed(42)

def stem_800_close(s):
    return "KakaoTalk_20260707_184409459" + ("" if s == "_00" else s)

def photo_3rd(s):
    for d in range(1, 6):
        if (HERE.parent/f"대림데이터/3차데이터/{d}번/{s}.jpg").exists(): return f"{d}번/{s}"
    return s

SOURCES = [
    (HERE/"m2_results/out_ondevice", HERE.parent/"대림데이터/600번대", lambda s: s),
    (HERE/"m2_results/out_ondevice", HERE.parent/"대림데이터/700번대", lambda s: s),
    (HERE/"daelim_v3_results/out_ondevice", HERE.parent/"대림데이터", lambda s: s),
    (HERE/"out_ondevice", HERE.parent/"대림데이터", stem_800_close),
    (HERE/"video_results/out_ondevice", HERE.parent/"대림데이터/3차데이터/vid_frames_all", lambda s: s),
    (HERE/"video_results/out_ondevice", HERE.parent/"대림데이터/3차데이터", photo_3rd),
]
# 검출 붕괴 프레임(자동 라벨 신뢰 불가) — AR 이미지 검수로 확인
SKIP = {"KakaoTalk_20260708_164051931_02", "KakaoTalk_20260708_164051931_10",
        "KakaoTalk_20260708_164051931_11"}

OUT = HERE/"yolo_labelset"
if OUT.exists(): shutil.rmtree(OUT)
for sp in ("train", "val"):
    (OUT/"images"/sp).mkdir(parents=True); (OUT/"labels"/sp).mkdir(parents=True)

items = []   # (photo_path, [boxes])
seen = set()
for res_dir, photo_dir, restore in SOURCES:
    for rf in sorted(glob.glob(str(res_dir/"*_ft_result.json"))):
        stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
        if stem in SKIP: continue
        photo = photo_dir/f"{restore(stem)}.jpg"
        if not photo.exists() or str(photo) in seen: continue
        seen.add(str(photo))
        rows = json.load(open(rf, encoding="utf-8"))
        # v3: 클러스터 기둥(높이/폭 3.4~4.6)이 아닌 라벨 부위만 — 하단 40%.
        # v2가 책등 박스를 배운 탓에 걷기 스트립이 410px로 두꺼워져 ×3 업스케일 미발동(판독률
        # 89% vs 휴리스틱 95%)이 근본 원인. 40%는 사진·동영상 렌더 육안 검증(흰 스티커+색 밴드).
        boxes = []
        for r in rows:
            x0, y0, x1, y1 = r["box"]
            boxes.append([x0, y1 - (y1-y0)*0.40, x1, y1])
        if len(boxes) < 5: continue
        items.append((photo, boxes))

random.shuffle(items)
n_val = max(2, len(items)//6)
splits = [("val", items[:n_val]), ("train", items[n_val:])]
tot = {"train": 0, "val": 0}
for sp, its in splits:
    for photo, boxes in its:
        bgr = cv2.imdecode(np.fromfile(str(photo), dtype=np.uint8), 1)
        if bgr is None: continue
        H, W = bgr.shape[:2]
        name = photo.stem
        # 학습 이미지는 1920px로 축소 (원본 4032px — imgsz 1280 학습이므로 충분)
        sc = min(1.0, 1920/W)
        img = cv2.resize(bgr, (int(W*sc), int(H*sc))) if sc < 1 else bgr
        cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(OUT/"images"/sp/f"{name}.jpg"))
        with io.open(OUT/"labels"/sp/f"{name}.txt", "w", encoding="utf-8") as f:
            for x0, y0, x1, y1 in boxes:
                cx, cy = (x0+x1)/2/W, (y0+y1)/2/H
                bw, bh = (x1-x0)/W, (y1-y0)/H
                if bw <= 0 or bh <= 0: continue
                f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        tot[sp] += 1

io.open(OUT/"data.yaml", "w", encoding="utf-8").write(
    "path: yolo_labelset\ntrain: images/train\nval: images/val\nnames:\n  0: call_label\n")
print(f"[변환] 사진 train {tot['train']} / val {tot['val']} (제외 {len(SKIP)} 각도 붕괴 프레임)")
print(f"[박스] 총 {sum(len(b) for _, b in items)}개")

import zipfile
z = zipfile.ZipFile(HERE/"yolo_labelset.zip", "w", zipfile.ZIP_DEFLATED)
for f in glob.glob(str(OUT/"**/*"), recursive=True):
    if os.path.isfile(f):
        z.write(f, os.path.relpath(f, HERE).replace(os.sep, "/"))
z.close()
print(f"[저장] yolo_labelset.zip {os.path.getsize(HERE/'yolo_labelset.zip')/1e6:.0f}MB")
