# -*- coding: utf-8 -*-
"""2차 파인튜닝용 실전 학습쌍 수확.

파이프라인이 카탈로그로 검증한 책(직독+제목복구)의 라벨 크롭에서 텍스트 줄을 분리해
(줄 이미지, 정답 텍스트) 쌍을 만든다. 제목복구 책 = OCR이 라벨을 못 읽었지만
제목으로 정답이 확정된 케이스 → 가장 가치 있는 hard 샘플.

출력: real_rec_data/crops/*.jpg + train.txt / val.txt (PaddleOCR rec 형식)
"""
import json, re, sys, io, glob, os, random
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
random.seed(42)

# (result.json 폴더, 사진 폴더, 사진 파일명 복원 규칙)
def stem_800_close(s):   # closeup_00 → KakaoTalk_20260707_184409459(.jpg), _01 → ..._01
    return "KakaoTalk_20260707_184409459" + ("" if s == "_00" else s)

def photo_3rd(s):
    """3차 세트 사진은 1번~5번 폴더에 분산 — 스템으로 탐색."""
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

OUT = HERE/"real_rec_data"; (OUT/"crops").mkdir(parents=True, exist_ok=True)

def imread(p): return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), 1)

def text_lines(crop):
    """흰 라벨 영역을 먼저 찾고, 그 안의 검정 텍스트 줄만 분리 → [(y0,y1), ...]
       (색 스티커 위 숫자·선반 배경이 줄로 오인되는 것 방지)"""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    white = (hsv[:, :, 1] < 90) & (hsv[:, :, 2] > 150)
    wrow = white.mean(axis=1)
    H, W = crop.shape[:2]
    # 가장 긴 연속 흰 라벨 구간
    runs, st = [], None
    for i, g in enumerate(list(wrow > 0.3) + [False]):
        if g and st is None: st = i
        elif not g and st is not None:
            runs.append((st, i)); st = None
    if not runs: return []
    wy0, wy1 = max(runs, key=lambda r: r[1]-r[0])
    if wy1 - wy0 < 30: return []
    dark = hsv[:, :, 2] < 110
    drow = dark[wy0:wy1].sum(axis=1)
    on = drow > W*0.04
    lines, st = [], None
    for i, g in enumerate(list(on) + [False]):
        if g and st is None: st = i
        elif not g and st is not None:
            if lines and st - lines[-1][1] <= 3: lines[-1] = (lines[-1][0], i)
            elif i - st >= 8: lines.append((st, i))
            st = None
    out = []
    for a, b in lines:
        if b - a < 10: continue
        seg = dark[wy0+a:wy0+b]
        cols = np.where(seg.any(axis=0))[0]
        if len(cols) < 8 or (cols[-1]-cols[0]) < W*0.25: continue  # 내용이 너무 좁으면 잡음
        out.append((wy0+a, wy0+b))
    return out

def call_parts(call):
    """청구기호 → 인쇄 줄 텍스트 목록. 별치기호(양843 등)는 그대로 첫 줄."""
    m = re.match(r"^(.*?)-(.+?)(?:-(.+))?$", call)
    if not m: return None
    cls, author, vol = m.group(1), m.group(2), m.group(3)
    if vol: return None                       # 권차 줄은 인쇄 표기가 제각각(1, v.2, c.2) → 학습쌍 제외
    return [cls, author]

seen = set(); n_img = 0; stats = {"청구기호": 0, "제목복구": 0}
gt = []
for res_dir, photo_dir, restore in SOURCES:
    for rf in sorted(glob.glob(str(res_dir/"*_ft_result.json"))):
        stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
        photo = photo_dir/f"{restore(stem)}.jpg"
        if not photo.exists(): continue
        key0 = str(photo)
        if key0 in seen: continue                  # 같은 사진이 여러 소스에 있으면 1회만
        seen.add(key0)
        bgr = imread(photo)
        if bgr is None: continue
        rows = json.load(open(rf, encoding="utf-8"))
        for ri, r in enumerate(rows):
            if not r.get("call") or r.get("how") not in ("청구기호", "제목복구"): continue
            parts = call_parts(r["call"])
            if not parts: continue
            x0, y0, x1, y1 = r["box"]
            crop = bgr[y0:y1, max(0, x0):x1]
            if crop.size == 0 or crop.shape[1] < 30: continue
            lines = text_lines(crop)
            if len(lines) != len(parts): continue  # 줄 수와 청구기호 구성이 일치할 때만 (오지정 방어)
            hard = (r["how"] == "제목복구")
            for (ly0, ly1), txt in zip(lines, parts):
                pad = max(2, (ly1-ly0)//5)
                line_img = crop[max(0, ly0-pad):ly1+pad]
                if line_img.shape[0] < 12: continue
                name = f"{stem}_{ri}_{txt}.jpg".replace("/", "")
                ok, buf = cv2.imencode(".jpg", line_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if not ok: continue
                (OUT/"crops"/name).write_bytes(buf.tobytes())
                gt.append((f"crops/{name}", txt, hard))
                n_img += 1
            stats[r["how"]] += 1

random.shuffle(gt)
n_val = max(1, len(gt)//10)
with io.open(OUT/"val.txt", "w", encoding="utf-8") as f:
    for p, t, _ in gt[:n_val]: f.write(f"{p}\t{t}\n")
with io.open(OUT/"train.txt", "w", encoding="utf-8") as f:
    for p, t, _ in gt[n_val:]: f.write(f"{p}\t{t}\n")

n_hard = sum(1 for _, _, h in gt if h)
print(f"[수확] 책 {stats['청구기호']+stats['제목복구']}권 (직독 {stats['청구기호']} · 제목복구 hard {stats['제목복구']})")
print(f"[수확] 줄 이미지 {n_img}장 (hard {n_hard}) → train {len(gt)-n_val} / val {n_val}")
print(f"[저장] {OUT}")
