# -*- coding: utf-8 -*-
"""YOLO 라벨 검출기 v5 학습셋 — 박스 기준 완화(핵심 변경) + 사람 확정 하드 네거티브 배경.

v3의 하단 40% 타이트 박스는 윗변이 분류번호 줄을 자름(07-17 수집 크롭 관찰로 확정)
→ 앱은 크롭 패딩(위 35%·옆 8%)으로 응급처치 중. v5는 그 패딩 기하를 학습 박스에 반영:
  스파인 박스 높이 hs 기준 하단 40%×1.35 = 54%, 옆은 박스 폭의 8% 확장.
검출기가 처음부터 라벨 전체를 물면 패딩 우회가 불필요하고 12MP 사진 회귀(-16%)도 회복 후보.

v4(909 부트스트랩 승격)는 제외 — 07-14 권차 매칭 수술로 '검출 무죄' 판명(폐기된 처방).
하드 네거티브 = 사람이 라벨링에서 '라벨아님' 확정한 17건만(자동 후보는 흐린 진짜 라벨 오염 위험).

출력: yolo_labelset_v5/{images,labels}/{train,val}/ + data.yaml → yolo_labelset_v5.zip
     + 육안 검증 렌더 6장(yolo_labelset_v5/_preview/)
사용: py -3.12 build_yolo_labelset_v5.py
"""
import json, sys, io, glob, os, random, shutil, zipfile
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
random.seed(42)                                   # v3와 동일 분할

PAD_X, TOP_F = 0.08, 0.54                         # 하단 54% = 40%×(1+위패딩 35%)

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

OUT = HERE/"yolo_labelset_v5"
if OUT.exists(): shutil.rmtree(OUT)
for sp in ("train", "val"):
    (OUT/"images"/sp).mkdir(parents=True); (OUT/"labels"/sp).mkdir(parents=True)
(OUT/"_preview").mkdir()

items = []   # (stem, photo_path, [spine_boxes])
seen = set()
for res_dir, photo_dir, restore in SOURCES:
    for rf in sorted(glob.glob(str(res_dir/"*_ft_result.json"))):
        stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
        if stem in SKIP: continue
        photo = photo_dir/f"{restore(stem)}.jpg"
        if not photo.exists() or str(photo) in seen: continue
        seen.add(str(photo))
        rows = json.load(open(rf, encoding="utf-8"))
        boxes = [r["box"] for r in rows]
        if len(boxes) < 5: continue
        items.append((stem, photo, boxes))

random.shuffle(items)
n_val = max(2, len(items)//6)
val_items, train_items = items[:n_val], items[n_val:]
print(f"[분할] train {len(train_items)} / val {len(val_items)}")

def label_box(x0, y0, x1, y1, W, H):
    hs, bw = y1 - y0, x1 - x0
    lx0 = max(0, x0 - bw*PAD_X); lx1 = min(W, x1 + bw*PAD_X)
    ly0 = max(0, y1 - hs*TOP_F); ly1 = min(H, y1)
    return lx0, ly0, lx1, ly1

def emit(sp, photo, boxes):
    bgr = cv2.imdecode(np.fromfile(str(photo), dtype=np.uint8), 1)
    if bgr is None: return 0
    H, W = bgr.shape[:2]
    sc = min(1.0, 1920/W)
    img = cv2.resize(bgr, (int(W*sc), int(H*sc))) if sc < 1 else bgr
    cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(OUT/"images"/sp/f"{photo.stem}.jpg"))
    with io.open(OUT/"labels"/sp/f"{photo.stem}.txt", "w", encoding="utf-8") as f:
        for b in boxes:
            x0, y0, x1, y1 = label_box(*b, W, H)
            bw, bh = (x1-x0)/W, (y1-y0)/H
            if bw <= 0 or bh <= 0: continue
            f.write(f"0 {(x0+x1)/2/W:.6f} {(y0+y1)/2/H:.6f} {bw:.6f} {bh:.6f}\n")
    return 1

tot = {"train": 0, "val": 0}
for sp, its in [("val", val_items), ("train", train_items)]:
    for stem, photo, boxes in its:
        tot[sp] += emit(sp, photo, boxes)
print(f"[변환] train {tot['train']} / val {tot['val']}")

# ── 하드 네거티브: 사람 확정 '라벨아님' → 배경 이미지(라벨 0개) ──
neg_ids = [l.strip() for l in io.open(HERE/"real_rec_data_human/hard_negatives.txt", encoding="utf-8") if l.strip()]
n_neg = 0
for nid in neg_ids:
    ztag, fname = nid.split("_", 1)                  # 1784194363789_crop_0089
    zp = HERE/f"수집조각/libar_crops_{ztag}.zip"
    if not zp.exists(): print(f"  [경고] zip 없음: {nid}"); continue
    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.rsplit(".", 1)[0] == fname]
        if not names: print(f"  [경고] 크롭 없음: {nid}"); continue
        raw = z.read(names[0])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
    if img is None: continue
    cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(OUT/"images/train"/f"neg_{nid}.jpg"))
    io.open(OUT/"labels/train"/f"neg_{nid}.txt", "w").close()
    n_neg += 1
print(f"[하드네거티브] 배경 이미지 {n_neg}/{len(neg_ids)}개 (train)")

# ── 육안 검증 렌더: val 3 + train 3 ──
for sp, its in [("val", val_items[:3]), ("train", train_items[:3])]:
    for stem, photo, boxes in its:
        bgr = cv2.imdecode(np.fromfile(str(photo), dtype=np.uint8), 1)
        H, W = bgr.shape[:2]
        for b in boxes:
            x0, y0, x1, y1 = [int(v) for v in label_box(*b, W, H)]
            cv2.rectangle(bgr, (x0, y0), (x1, y1), (0, 255, 0), max(2, W//1200))
        sc = 1400/W
        bgr = cv2.resize(bgr, (1400, int(H*sc)))
        cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(str(OUT/"_preview"/f"{sp}_{stem}.jpg"))
print("[렌더] _preview/ 6장")

io.open(OUT/"data.yaml", "w", encoding="utf-8").write(
    "path: yolo_labelset_v5\ntrain: images/train\nval: images/val\nnames:\n  0: call_label\n")

z = zipfile.ZipFile(HERE/"yolo_labelset_v5.zip", "w", zipfile.ZIP_DEFLATED)
for f in glob.glob(str(OUT/"**/*"), recursive=True):
    if os.path.isfile(f) and "_preview" not in f:
        z.write(f, os.path.relpath(f, HERE).replace(os.sep, "/"))
z.close()
print(f"[저장] yolo_labelset_v5.zip {os.path.getsize(HERE/'yolo_labelset_v5.zip')/1e6:.0f}MB")

# ── 노트북: v4 복제 + 치환 ──
nb = json.load(io.open(HERE/"train_label_yolo_v4_colab.ipynb", encoding="utf-8"))
NL = chr(10)
nb["cells"][0]["source"] = [ln + NL for ln in f"""# YOLO 청구기호 라벨 검출기 **v5** — 박스 기준 완화 + 하드 네거티브

**v3에서 바뀐 것:** ①학습 박스를 하단 40%→54%+옆 8%(앱 크롭 패딩 기하와 일치)로 완화 —
타이트 박스가 분류번호 줄을 자르던 문제의 근본 수정 ②사람이 '라벨아님' 확정한 오탐 크롭
{n_neg}건을 배경 이미지로 투입. v4(부트스트랩)는 '검출 무죄' 판명으로 폐기, 승격 없음.
나머지(증강·epochs·모델)는 v3와 동일 — 변인 통제.

**데이터:** `yolo_labelset_v5.zip` (train {tot['train']}+배경 {n_neg} · val {tot['val']})
**채택 기준(로컬 A/B):** 걷기 표본 검출 수 v3 이상 + 사진 회귀 회복 + 웹데모 autotest 14권 유지
**런타임:** GPU(T4) · 약 40~50분""".splitlines()]

def swap(i, pairs):
    src = "".join(nb["cells"][i]["source"])
    for a, b in pairs:
        assert a in src, f"셀{i}에 '{a}' 없음"
        src = src.replace(a, b)
    nb["cells"][i]["source"] = [ln + NL for ln in src.splitlines()]

swap(1, [("yolo_labelset_v4", "yolo_labelset_v5")])
swap(2, [("yolo_labelset_v4/data.yaml", "yolo_labelset_v5/data.yaml"), ("call_label_v4", "call_label_v5")])
swap(3, [("call_label_v4", "call_label_v5"), ("yolo_labelset_v4", "yolo_labelset_v5")])
swap(4, [("call_label_v4", "call_label_v5"), ("call_label_yolo_v4.zip", "call_label_yolo_v5.zip")])
nb["cells"][5]["source"] = [ln + NL for ln in """## 5) 로컬 채점 (다운로드 후)

`call_label_yolo_v5.zip`을 저(클로드)에게 주시면:
① 동적 ONNX 재수출(라이브 960/사진 1280 겸용) ② 걷기 표본·사진 회귀 A/B(v3 대비)
③ 웹데모 autotest(14권 유지) + 패딩 조정 영향 분석 → **보고 후 승인받고 배포**""".splitlines()]

out_nb = HERE/"train_label_yolo_v5_colab.ipynb"
json.dump(nb, io.open(out_nb, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[노트북] {out_nb.name}")
