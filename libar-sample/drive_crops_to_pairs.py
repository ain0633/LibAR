# -*- coding: utf-8 -*-
"""드라이브 수집 조각 → rec 학습쌍 변환기.

입력: 공유 드라이브 수신함에서 받은 libar_crops_*.zip 폴더 (앱이 자동 업로드한 것)
  zip 내용 = crop_NNNN.jpg (라벨 박스 크롭) + manifest.json {crops:[{file,call,how,box,scan}]}
변환: call 있는 크롭만 → mobile det(×3)로 텍스트 줄 분리 → rec 판독 → 줄 읽기가
  카탈로그 정답 성분(분류번호·저자기호)과 유사하면 그 줄을 학습쌍으로 승격.
  GT는 판독문이 아니라 **카탈로그의 참값** (pair_align_harvest와 같은 원칙).
출력: real_rec_data_field/crops/*.jpg + meta_field.txt (file\tGT\tfield)
사용: py -3.12 drive_crops_to_pairs.py [--inbox 수집조각] [--out real_rec_data_field]
"""
import io, sys, json, glob, os, re, zipfile, difflib, unicodedata
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

def opt(name, default):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default
INBOX = HERE/opt("--inbox", "수집조각")
OUT = HERE/opt("--out", "real_rec_data_field")
(OUT/"crops").mkdir(parents=True, exist_ok=True)

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
rsess = ort.InferenceSession(str(HERE/"webdemo/rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
dsess = ort.InferenceSession(str(HERE/"webdemo/det_mobile.onnx"), so, providers=["CPUExecutionProvider"])
rin, din = rsess.get_inputs()[0].name, dsess.get_inputs()[0].name
chars = json.load(io.open(HERE/"webdemo/rec_charset.json", encoding="utf-8"))

def rec_line(img):
    h, w = img.shape[:2]
    if h < 4 or w < 4: return ""
    tw = min(320, max(8, int(np.ceil(48*w/h))))
    r = cv2.resize(img, (tw, 48)).astype(np.float32)
    r = (r/255.0 - 0.5)/0.5
    pad = np.zeros((48, 320, 3), np.float32); pad[:, :tw] = r
    logits = rsess.run(None, {rin: pad.transpose(2, 0, 1)[None]})[0][0]
    idx = logits.argmax(axis=1)
    out, prev = [], -1
    for t in idx:
        if t != prev and t != 0: out.append(chars[t-1] if t-1 < len(chars) else "?")
        prev = t
    return unicodedata.normalize("NFC", "".join(out))

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
def det_lines(img):
    """webdemo 검증본과 동일한 간이 DB 후처리 — (y0, 줄크롭) 목록."""
    h, w = img.shape[:2]
    sc = min(1.0, 960/max(h, w))
    nh, nw = max(32, int(round(h*sc/32))*32), max(32, int(round(w*sc/32))*32)
    rs = cv2.resize(img, (nw, nh)).astype(np.float32)/255.0
    rs = (rs - MEAN)/STD
    prob = dsess.run(None, {din: rs.transpose(2, 0, 1)[None]})[0][0, 0]
    binm = (prob > 0.3).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(binm, 8)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 12 or bw < 4 or bh < 4: continue
        if float(prob[lab == i].mean()) < 0.6: continue
        px, py = int(bh*0.45), int(bh*0.28)
        x0, y0 = max(0, x-px), max(0, y-py)
        x1, y1 = min(nw, x+bw+px), min(nh, y+bh+py)
        cy0, cy1 = int(y0*h/nh), int(np.ceil(y1*h/nh))
        cx0, cx1 = int(x0*w/nw), int(np.ceil(x1*w/nw))
        out.append((cy0, img[cy0:cy1, cx0:cx1]))
    return sorted(out, key=lambda t: t[0])

def nfc(s): return unicodedata.normalize("NFC", str(s))
def sim(a, b): return difflib.SequenceMatcher(None, a, b).ratio()

meta_path = OUT/"meta_field.txt"
have = set()
if meta_path.exists():
    for ln in io.open(meta_path, encoding="utf-8"):
        have.add(ln.split("\t")[0])
meta = io.open(meta_path, "a", encoding="utf-8")

import hashlib
seen_zip = set()
n_zip = n_crop = n_pair = n_dup = 0
for zp in sorted(glob.glob(str(INBOX/"libar_crops_*.zip"))):
    h = hashlib.md5(open(zp, "rb").read()).hexdigest()
    if h in seen_zip:                                  # 재전송 중복 zip (전송 재시도 흔적)
        n_dup += 1; continue
    seen_zip.add(h)
    n_zip += 1
    ztag = Path(zp).stem.replace("libar_crops_", "")
    with zipfile.ZipFile(zp) as z:
        man = json.loads(z.read("manifest.json").decode("utf-8"))
        for c in man.get("crops", []):
            call = c.get("call")
            if not call: continue                      # 정답 확정 크롭만
            n_crop += 1
            img = cv2.imdecode(np.frombuffer(z.read(c["file"]), np.uint8), 1)
            if img is None: continue
            big = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
            parts = nfc(call).split("-")
            cands = [p for p in parts[:2] if len(p) >= 2]  # 분류번호·저자기호 (권차 줄 제외)
            for li, (y0, line) in enumerate(det_lines(big)):
                read = rec_line(line)
                if len(read) < 2: continue
                best = max(cands, key=lambda p: sim(read, p), default=None)
                if best is None or sim(read, best) < 0.5: continue
                name = f"crops/{ztag}_{Path(c['file']).stem}_{li}_{re.sub(r'[^0-9A-Za-z가-힣.]', '', best)}.jpg"
                if name in have: continue
                cv2.imencode(".jpg", line, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(OUT/name))
                meta.write(f"{name}\t{best}\tfield\n")
                have.add(name); n_pair += 1
meta.close()
print(f"[변환] zip {n_zip}개(중복 제외 {n_dup}) · 정답 크롭 {n_crop}개 → 학습쌍 {n_pair}줄 (GT=카탈로그 참값)")
print(f"[출력] {OUT}/meta_field.txt — rec 파인튜닝 v5 학습 시 meta_train에 병합")
