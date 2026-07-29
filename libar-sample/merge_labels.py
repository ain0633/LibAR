# -*- coding: utf-8 -*-
"""사람 라벨(label.html 제출분) → rec 학습쌍 병합.
입력: 수집조각/libar_labels_*.zip (labels.json {labels:[{id: ztag_crop_NNNN, call}]})
GT = 사람이 고른 카탈로그 참값 — 모델과 독립이라 소급 매칭의 선택 편향이 없다 (tag=human).
같은 크롭에 서로 다른 답이 오면(중복 제출·오답) 최신 zip 우선.
출력: real_rec_data_human/crops/*.jpg + meta_human.txt (file\tGT\thuman)
사용: py -3.12 merge_labels.py
"""
import io, json, glob, re, zipfile, difflib, unicodedata
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE/"real_rec_data_human"
(OUT/"crops").mkdir(parents=True, exist_ok=True)

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
rsess = ort.InferenceSession(str(HERE/"webdemo/rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
dsess = ort.InferenceSession(str(HERE/"webdemo/det_mobile.onnx"), so, providers=["CPUExecutionProvider"])
rin, din = rsess.get_inputs()[0].name, dsess.get_inputs()[0].name
chars = json.load(io.open(HERE/"webdemo/rec_charset.json", encoding="utf-8"))
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
def nfc(s): return unicodedata.normalize("NFC", str(s))
def sim(a, b): return difflib.SequenceMatcher(None, a, b).ratio()

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
    return nfc("".join(out))

def det_lines(img):
    h, w = img.shape[:2]
    sc = min(1.0, 960/max(h, w))
    nh, nw = max(32, int(round(h*sc/32))*32), max(32, int(round(w*sc/32))*32)
    rs = cv2.resize(img, (nw, nh)).astype(np.float32)/255.0
    rs = (rs - MEAN)/STD
    prob = dsess.run(None, {din: rs.transpose(2, 0, 1)[None]})[0][0, 0]
    n, lab, stats, _ = cv2.connectedComponentsWithStats((prob > 0.3).astype(np.uint8), 8)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 12 or bw < 4 or bh < 4: continue
        if float(prob[lab == i].mean()) < 0.6: continue
        px, py = int(bh*0.45), int(bh*0.28)
        cy0, cy1 = int(max(0, y-py)*h/nh), int(np.ceil(min(nh, y+bh+py)*h/nh))
        cx0, cx1 = int(max(0, x-px)*w/nw), int(np.ceil(min(nw, x+bw+px)*w/nw))
        out.append((cy0, img[cy0:cy1, cx0:cx1]))
    return sorted(out, key=lambda t: t[0])

# 1) 라벨 수집 (최신 zip 우선 — 같은 id 재답변은 나중 것으로 덮음)
answers, notlabels = {}, set()
zips = sorted(glob.glob(str(HERE/"수집조각/libar_labels_*.zip")))
for zp in zips:
    with zipfile.ZipFile(zp) as z:
        data = json.loads(z.read("labels.json").decode("utf-8"))
        for r in data.get("labels", []):
            answers[r["id"]] = nfc(r["call"]); notlabels.discard(r["id"])
        for i in data.get("notlabels", []):
            notlabels.add(i); answers.pop(i, None)
print(f"[라벨] zip {len(zips)}개 → 답변 {len(answers)}개 · 라벨아님 {len(notlabels)}개 (id 중복 최신 우선)")
if notlabels:                                          # 사람이 확정한 검출 오탐 = 검출기 v4 하드 네거티브
    hn = OUT/"hard_negatives.txt"
    old = set(io.open(hn, encoding="utf-8").read().split()) if hn.exists() else set()
    io.open(hn, "w", encoding="utf-8").write("\n".join(sorted(old | notlabels)) + "\n")
    print(f"[하드네거티브] {hn} — 누적 {len(old | notlabels)}개")

# 2) 크롭 찾기 → 줄 분해 → 사람 GT 성분과 매칭 (변환기 call-확정 경로와 동일 기준)
meta_path = OUT/"meta_human.txt"
have = set()
if meta_path.exists():
    for ln in io.open(meta_path, encoding="utf-8"):
        have.add(ln.split("\t")[0])
meta = io.open(meta_path, "a", encoding="utf-8")
n_pair = n_miss = 0
for cid, call in answers.items():
    m = re.match(r"^(\d{13})_(crop_\d+)$", cid)
    if not m: continue
    ztag, stem = m.groups()
    try:
        with zipfile.ZipFile(HERE/f"수집조각/libar_crops_{ztag}.zip") as z:
            raw = z.read(f"{stem}.jpg")
    except Exception:
        n_miss += 1; continue
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
    if img is None: continue
    big = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
    # 복본 표기(=2, =c.2)는 전산 꼬리 — 이미지에 없는 글자를 GT에 달지 않는다
    cands = [p.split("=")[0] for p in call.split("-")[:2]]
    cands = [p for p in cands if len(p) >= 2]
    for li, (y0, line) in enumerate(det_lines(big)):
        read = rec_line(line)
        if len(read) < 2: continue
        if re.match(r"^[vcVC]\.?\d", read): continue   # 권차/복본 줄(v.2·c.2)은 학습 제외
        best = max(cands, key=lambda p: sim(read, p), default=None)
        # 사람 GT라도 줄-성분 대응은 판독으로 정렬 — 문턱 0.35 (v4가 못 읽는 줄이 핵심 재료라 낮게)
        # 단, 짧은 판독('03' 2글자)이 가려진 분류번호에 얹히면 환각 교재가 된다 — 짧으면 문턱 상향
        s = sim(read, best) if best else 0
        if best is None or s < 0.35 or (len(read) < 3 and s < 0.6): continue
        digits = sum(c.isdigit() for c in read) / len(read)
        if re.search(r"[가-힣]", best) and digits > 0.7: continue   # 숫자 줄이 저자기호 GT에 붙는 오배정 차단
        if best[0].isdigit() and "." in best and "." not in read and s < 0.7: continue   # 소수점 안 보이는 조각 + 긴 분류 GT 금지
        name = f"crops/{ztag}_{stem}_{li}_{re.sub(r'[^0-9A-Za-z가-힣.]', '', best)}.jpg"
        if name in have: continue
        cv2.imencode(".jpg", line, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(OUT/name))
        meta.write(f"{name}\t{best}\thuman\n")
        have.add(name); n_pair += 1
meta.close()
print(f"[병합] 학습쌍 {n_pair}줄 추가 (크롭 못 찾음 {n_miss}) → {OUT}/meta_human.txt")
