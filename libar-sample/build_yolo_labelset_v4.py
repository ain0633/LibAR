# -*- coding: utf-8 -*-
"""YOLO 라벨 검출기 v4 학습셋 — v3 레시피(하단 40% 타이트) + 909 부트스트랩 승격.

v3 채점(151프레임)에서 하이브리드만 못 읽은 10권(909~911 집중)은 검출 누락이 원인.
휴리스틱은 같은 프레임에서 정답 박스를 갖고 있고, 그 31프레임은 라벨셋에 이미 포함돼
있었으나 4,972박스에 묻혀 학습되지 않음 → 처방: 해당 프레임을 train으로 강제 + ×3 복제.
val은 v3와 동일 분할 유지(부트스트랩 프레임만 train으로 이동, 복제본은 train 전용).

출력: yolo_labelset_v4/{images,labels}/{train,val}/ + data.yaml → yolo_labelset_v4.zip
"""
import json, sys, io, glob, os, re, shutil, random
from collections import Counter, defaultdict
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
random.seed(42)                                   # v3와 동일 분할
BOOST = 3                                         # 부트스트랩 프레임 복제 배수

# ── 부트스트랩 프레임 산출 (diag_v4.py와 동일 논리) ──
truth = set()
for rf in glob.glob(str(HERE/"video_results/out_ondevice/*_ft_result.json")):
    rows = json.load(open(rf, encoding="utf-8"))
    m = [r for r in rows if r["call"]]
    if not rows or len(m)/len(rows) < 0.6: continue
    truth |= {r["call"] for r in m if r.get("how") == "청구기호"}
vids = defaultdict(Counter)
for rf in sorted(glob.glob(str(HERE/"hybrid_v3_results/yolo_동영상*_result.json"))):
    rows = json.load(open(rf, encoding="utf-8"))
    m = re.search(r"(동영상\d)_f\d+", os.path.basename(rf))
    for c in {r["call"] for r in rows if r["call"]}:
        vids[m.group(1)][c] += 1
stable = set()
for v in vids: stable |= {c for c, n in vids[v].items() if n >= 2}
missed = truth - stable
boost_stems = set()
for rf in sorted(glob.glob(str(HERE/"video_results/out_ondevice/*_ft_result.json"))):
    stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
    rows = json.load(open(rf, encoding="utf-8"))
    if any(r["call"] in missed and r.get("how") == "청구기호" for r in rows):
        boost_stems.add(stem)
print(f"[부트스트랩] 미판독 {len(missed)}권 → 승격 프레임 {len(boost_stems)}개 (×{BOOST})")

# ── 이하 v3 빌더(build_yolo_labelset.py)와 동일 수집 ──
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
SKIP = {"KakaoTalk_20260708_164051931_02", "KakaoTalk_20260708_164051931_10",
        "KakaoTalk_20260708_164051931_11"}

OUT = HERE/"yolo_labelset_v4"
if OUT.exists(): shutil.rmtree(OUT)
for sp in ("train", "val"):
    (OUT/"images"/sp).mkdir(parents=True); (OUT/"labels"/sp).mkdir(parents=True)

items = []   # (stem, photo_path, [boxes])
seen = set()
for res_dir, photo_dir, restore in SOURCES:
    for rf in sorted(glob.glob(str(res_dir/"*_ft_result.json"))):
        stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
        if stem in SKIP: continue
        photo = photo_dir/f"{restore(stem)}.jpg"
        if not photo.exists() or str(photo) in seen: continue
        seen.add(str(photo))
        rows = json.load(open(rf, encoding="utf-8"))
        boxes = []
        for r in rows:
            x0, y0, x1, y1 = r["box"]
            boxes.append([x0, y1 - (y1-y0)*0.40, x1, y1])   # 하단 40% 타이트 (v3 검증)
        if len(boxes) < 5: continue
        items.append((stem, photo, boxes))

random.shuffle(items)
n_val = max(2, len(items)//6)
val_items = [it for it in items[:n_val] if it[0] not in boost_stems]
moved = len(items[:n_val]) - len(val_items)
train_items = items[n_val:] + [it for it in items[:n_val] if it[0] in boost_stems]
print(f"[분할] train {len(train_items)} / val {len(val_items)} (부트스트랩 {moved}개 val→train 이동)")

def emit(sp, stem, photo, boxes, suffix=""):
    bgr = cv2.imdecode(np.fromfile(str(photo), dtype=np.uint8), 1)
    if bgr is None: return 0
    H, W = bgr.shape[:2]
    name = photo.stem + suffix
    sc = min(1.0, 1920/W)
    img = cv2.resize(bgr, (int(W*sc), int(H*sc))) if sc < 1 else bgr
    cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(OUT/"images"/sp/f"{name}.jpg"))
    with io.open(OUT/"labels"/sp/f"{name}.txt", "w", encoding="utf-8") as f:
        for x0, y0, x1, y1 in boxes:
            cx, cy = (x0+x1)/2/W, (y0+y1)/2/H
            bw, bh = (x1-x0)/W, (y1-y0)/H
            if bw <= 0 or bh <= 0: continue
            f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
    return 1

tot = {"train": 0, "val": 0}; n_boost = 0
for stem, photo, boxes in val_items:
    tot["val"] += emit("val", stem, photo, boxes)
for stem, photo, boxes in train_items:
    tot["train"] += emit("train", stem, photo, boxes)
    if stem in boost_stems:                       # 복제 승격 (train 전용)
        for k in range(2, BOOST+1):
            n_boost += emit("train", stem, photo, boxes, f"_boost{k}")
tot["train"] += n_boost

io.open(OUT/"data.yaml", "w", encoding="utf-8").write(
    "path: yolo_labelset_v4\ntrain: images/train\nval: images/val\nnames:\n  0: call_label\n")
print(f"[변환] train {tot['train']} (복제 {n_boost}) / val {tot['val']}")

import zipfile
z = zipfile.ZipFile(HERE/"yolo_labelset_v4.zip", "w", zipfile.ZIP_DEFLATED)
for f in glob.glob(str(OUT/"**/*"), recursive=True):
    if os.path.isfile(f):
        z.write(f, os.path.relpath(f, HERE).replace(os.sep, "/"))
z.close()
print(f"[저장] yolo_labelset_v4.zip {os.path.getsize(HERE/'yolo_labelset_v4.zip')/1e6:.0f}MB")
