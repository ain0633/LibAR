# -*- coding: utf-8 -*-
"""v4 1차 검사 (검출만, 로컬 고속) — 909 부트스트랩 처방이 들었는지.
미판독 10권의 휴리스틱 정답 박스(31프레임) 위치를 v3/v4가 각각 검출하는지 IoU로 채점.
+ 사진 회귀 예비 신호: 600_11·700_10 검출 박스 수 v2/v3/v4 비교."""
import glob, io, json, os, re, sys
from collections import Counter, defaultdict
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3

def load(name):
    return ort.InferenceSession(str(HERE/name/"best.onnx"), so, providers=["CPUExecutionProvider"])
S = {"v3": load("call_label_yolo3"), "v4": load("call_label_yolo_v4")}
try: S["v2"] = load("call_label_yolo")
except Exception: pass

def detect(sess, img, conf=0.25):
    H, W = img.shape[:2]
    r = 1280/max(H, W)
    canvas = np.full((1280, 1280, 3), 114, np.uint8)
    canvas[:int(H*r), :int(W*r)] = cv2.resize(img, (int(W*r), int(H*r)))
    x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32)/255.0
    out = sess.run(None, {"images": x})[0][0]
    return [tuple(b[:4]/r) for b in out if b[4] >= conf]

def iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0: return 0.0
    inter = (x1-x0)*(y1-y0)
    return inter/((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter)

# ── 미판독 10권 + 휴리스틱 GT 박스 (diag_v4와 동일) — GT는 하단 40% 타이트로 변환해 비교 ──
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

def photo_3rd(s):
    for d in range(1, 6):
        p = HERE.parent/f"대림데이터/3차데이터/{d}번/{s}.jpg"
        if p.exists(): return p
    return None

cases = []   # (stem, img_path, call, gt_tight_box)
for rf in sorted(glob.glob(str(HERE/"video_results/out_ondevice/*_ft_result.json"))):
    stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
    p = HERE.parent/f"대림데이터/3차데이터/vid_frames_all/{stem}.jpg"
    if not p.exists(): p = photo_3rd(stem)
    if not p or not Path(p).exists(): continue
    for r in json.load(open(rf, encoding="utf-8")):
        if r["call"] in missed and r.get("how") == "청구기호":
            x0, y0, x1, y1 = r["box"]
            cases.append((stem, p, r["call"], (x0, y1-(y1-y0)*0.40, x1, y1)))
print(f"[검사] 미판독 {len(missed)}권 · GT 박스 {len(cases)}개 (31프레임)")

det_cache = {}
hit_book = {k: defaultdict(int) for k in S}
tot_book = defaultdict(int)
for stem, p, call, gt in cases:
    tot_book[call] += 1
    if stem not in det_cache:
        img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), 1)
        det_cache[stem] = {k: detect(s, img) for k, s in S.items()}
    for k in S:
        if any(iou(gt, b) >= 0.3 for b in det_cache[stem][k]): hit_book[k][call] += 1

print(f"\n{'책':<16}{'GT수':>4}" + "".join(f"{k:>8}" for k in S))
for call in sorted(tot_book):
    print(f"{call:<16}{tot_book[call]:>4}" + "".join(f"{hit_book[k][call]:>8}" for k in S))
print(f"\n[박스 회수율(IoU≥0.3)]" +
      "".join(f" {k}={sum(hit_book[k].values())}/{len(cases)}" for k in S))
rec2 = {k: sum(1 for c in tot_book if hit_book[k][c] >= 2) for k in S}
print(f"[책 단위: 2프레임↑ 검출(안정 후보)]" +
      "".join(f" {k}={rec2[k]}/{len(tot_book)}권" for k in S))

# ── 동영상 프레임만 (걷기 판독률에 실제 반영되는 지형) ──
vid_cases = [(st, p, c, g) for st, p, c, g in cases if st.startswith("동영상")]
hitv = {k: defaultdict(int) for k in S}; totv = defaultdict(int)
for stem, p, call, gt in vid_cases:
    totv[call] += 1
    for k in S:
        if any(iou(gt, b) >= 0.3 for b in det_cache[stem][k]): hitv[k][call] += 1
print(f"\n[동영상 프레임만] GT {len(vid_cases)}개")
print(f"{'책':<16}{'GT수':>4}" + "".join(f"{k:>8}" for k in S))
for call in sorted(totv):
    print(f"{call:<16}{totv[call]:>4}" + "".join(f"{hitv[k][call]:>8}" for k in S))
print("[박스 회수]" + "".join(f" {k}={sum(hitv[k].values())}/{len(vid_cases)}" for k in S))
rec2v = {k: sum(1 for c in totv if hitv[k][c] >= 2) for k in S}
print("[책 단위 2프레임↑]" + "".join(f" {k}={rec2v[k]}/{len(totv)}권" for k in S))

# ── 사진 예비 신호: 검출 박스 수 ──
print("\n[사진 검출 박스 수] (참고 — 판정은 파이프라인 재실행 필요)")
for name, rel in [("600_11", "대림데이터/600번대/600_11.jpg"), ("700_10", "대림데이터/700번대/700_10.jpg")]:
    p = HERE.parent/rel
    if not p.exists():
        print(f"   {name}: 파일 없음({rel})"); continue
    img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), 1)
    print(f"   {name}: " + " ".join(f"{k}={len(detect(s, img))}" for k, s in S.items()))
