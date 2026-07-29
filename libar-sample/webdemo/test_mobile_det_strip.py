# -*- coding: utf-8 -*-
"""상한 확인: 파이프라인 스트립 흐름에서 det만 server→mobile로 바꾸면 몇 권 매칭되나.
(브라우저에 이식 가능한 구조의 성능 상한 — 통과 기준 감: demo1 12권·demo2 10권 대비)"""
import io, sys, os, json, re, csv, difflib, unicodedata, time
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
os.chdir(HERE.parent)                     # Paddle 한글 절대경로 회피
OUT = io.open(HERE/"mobile_det_result.txt", "w", encoding="utf-8")

# match — tune_browser_rec와 동일
def nn(s): return re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ.]", "", unicodedata.normalize("NFC", str(s)))
cat = json.load(io.open(HERE/"demo/catalog.json", encoding="utf-8"))
items, by_cls = [], {}
for r in cat:
    call = re.sub(r"\s*(?:=|[cC]\.)\d+$", "", str(r["call"]).strip())
    parts = call.split("-")
    if len(parts) < 2: continue
    m = re.match(r"^[가-힣A-Z]*([\d.]+)$", parts[0].strip())
    it = {"call": call, "cls": m.group(1) if m else parts[0].strip(),
          "author": nn(parts[1].strip()), "title": r["title"]}
    items.append(it); by_cls.setdefault(it["cls"], []).append(it)
JF = {"0":"ㅇ","O":"ㅇ","o":"ㅇ","Q":"ㅇ","으":"ㅇ","이":"ㅇ","피":"ㅍ","디":"ㄷ","기":"ㄱ","니":"ㄴ",
      "리":"ㄹ","미":"ㅁ","비":"ㅂ","시":"ㅅ","지":"ㅈ","치":"ㅊ","키":"ㅋ","티":"ㅌ","히":"ㅎ",
      "프":"ㅍ","표":"ㅍ","드":"ㄷ","그":"ㄱ","느":"ㄴ","르":"ㄹ","므":"ㅁ","브":"ㅂ","스":"ㅅ",
      "즈":"ㅈ","츠":"ㅊ","크":"ㅋ","트":"ㅌ","흐":"ㅎ"}
def match(txt):
    t = nn(txt); m = None
    for m2 in re.finditer(r"(\d{3}(?:\.\d+)?)([가-힣][0-9]{1,3}[가-힣ㄱ-ㅎ0Oo]?)", t):
        if m2.group(1) in by_cls: m = m2; break
    if not m:
        best = None
        for a in re.findall(r"[가-힣][0-9]{2,3}[가-힣ㄱ-ㅎ]?", t):
            vs = {a} | ({a[:-1]+JF[a[-1]]} if a[-1] in JF else set())
            hits = [c for c in items if c["author"] in vs]
            if len(hits) == 1 and len(a) >= 4: best = hits[0]
        return best
    clsv, author = m.group(1), m.group(2); cands = by_cls[clsv]
    variants = {author} | ({author[:-1]+JF[author[-1]]} if author[-1] in JF else set())
    hits = [c for c in cands if c["author"] in variants]
    if len(hits) > 1:
        if len({c["call"] for c in hits}) == 1: return hits[0]
        return None
    if len(hits) == 1: return hits[0]
    def dok(c):
        da, dc = re.sub(r"\D","",author), re.sub(r"\D","",c["author"])
        return not (len(da) == len(dc) and da != dc)
    sc = sorted(((max(difflib.SequenceMatcher(None,v,c["author"]).ratio() for v in variants), c)
                 for c in cands if c["author"][:1] == author[:1] and dok(c)), key=lambda x: x[0])
    if not sc or sc[-1][0] < 0.75: return None
    if len(sc) > 1 and sc[-1][0]-sc[-2][0] < 0.05: return None
    return sc[-1][1]

from paddleocr import PaddleOCR
ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
                text_recognition_model_dir="korean_lowres_v4_rec_infer")

def ocr_once(img):
    res = ocr.predict(img)
    out = []
    if res:
        rr = res[0]
        for txt, poly in zip(rr.get("rec_texts", []), rr.get("rec_polys", [])):
            p = np.array(poly)
            out.append((txt, float(p[:,0].mean()), float(p[:,1].mean())))
    return out

def ocr_tokens(img, chunk=1280, ov=120, up=True):   # 파이프라인 검증본 축약
    h, w = img.shape[:2]
    f = (min(3.0, 960/h) if h < 320 else min(1.0, 1000/h)) if up else 1.0
    if f != 1.0:
        img = cv2.resize(img, None, fx=f, fy=f,
                         interpolation=cv2.INTER_LANCZOS4 if f > 1 else cv2.INTER_AREA)
        h, w = img.shape[:2]
    if f > 1: ov = int(ov*f)
    out = []
    if max(h, w) <= chunk + ov: out = ocr_once(img)
    else:
        x = 0
        while x < w:
            piece = img[:, x:min(w, x+chunk+ov)]
            for txt, xc, yc in ocr_once(piece):
                if x > 0 and xc < ov*0.5: continue
                out.append((txt, xc+x, yc))
            x += chunk
    return [(t, x2/f, y2/f) for t, x2, y2 in out]

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
ysess = ort.InferenceSession("call_label_yolo3/best.onnx", so, providers=["CPUExecutionProvider"])

for demo in (1, 2):
    img = cv2.imdecode(np.fromfile(str(HERE/f"demo/demo{demo}.jpg"), dtype=np.uint8), 1)
    H, W = img.shape[:2]
    r_ = 1280/max(H, W)
    canvas = np.full((1280, 1280, 3), 114, np.uint8)
    canvas[:int(H*r_), :int(W*r_)] = cv2.resize(img, (int(W*r_), int(H*r_)))
    x_ = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32)/255.0
    out_ = ysess.run(None, {"images": x_})[0][0]
    boxes = [tuple((b[:4]/r_).astype(int)) for b in out_ if b[4] >= 0.25]
    # 밴드 클러스터 (파이프라인 검증본)
    bxs = sorted(boxes, key=lambda b: (b[1]+b[3])/2)
    hmed = float(np.median([b[3]-b[1] for b in bxs]))
    bands, last = [], -1e9
    for b in bxs:
        yc = (b[1]+b[3])/2
        if yc - last > hmed*0.8: bands.append([])
        bands[-1].append(b); last = yc
    t0 = time.time()
    n_match, n_tok = 0, 0
    for rboxes in bands:
        rboxes = sorted(rboxes, key=lambda b: b[0])
        sy0 = max(0, min(b[1] for b in rboxes)); sy1 = min(H, max(b[3] for b in rboxes))
        toks = ocr_tokens(img[sy0:sy1, :])
        n_tok += len(toks)
        centers = [((b[0]+b[2])/2, b) for b in rboxes]
        assign = {i: [] for i in range(len(rboxes))}
        for t in toks:
            j = min(range(len(centers)), key=lambda k: abs(centers[k][0]-t[1]))
            bx = centers[j][1]
            if abs(centers[j][0]-t[1]) <= max(60, (bx[2]-bx[0])*0.9): assign[j].append(t)
        have = set()
        for j in range(len(rboxes)):
            inb = sorted(assign[j], key=lambda t: (round(t[2]/30), t[1]))
            txt = " ".join(t[0] for t in inb)
            row = match(txt)
            if row and row["call"] not in have: n_match += 1; have.add(row["call"])
        # 클러스터 채널
        if toks:
            wmed = float(np.median([b[2]-b[0] for b in rboxes]))
            ts = sorted(toks, key=lambda t: t[1]); cl = [[ts[0]]]
            for t in ts[1:]:
                if t[1]-cl[-1][-1][1] > wmed*0.7: cl.append([])
                cl[-1].append(t)
            for c2 in cl:
                txt = " ".join(t[0] for t in sorted(c2, key=lambda t: (round(t[2]/30), t[1])))
                row = match(txt)
                if row and row["call"] not in have: n_match += 1; have.add(row["call"])
    OUT.write(f"demo{demo}: mobile-det 스트립 매칭 {n_match}권 · 토큰 {n_tok} · {time.time()-t0:.0f}s\n")
OUT.close(); print("done")
