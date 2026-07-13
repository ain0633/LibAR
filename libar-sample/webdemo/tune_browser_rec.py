# -*- coding: utf-8 -*-
"""브라우저 인식 경로 개선 실험 — v3 박스 → 라벨 영역 격리(HSV) → ×3 → 줄분할 → 트림 → rec → match.
demo1·demo2 전체에서 매칭 권수로 채점 (파이프라인 실측 직독과 비교)."""
import io, sys, json, re, csv, difflib, unicodedata
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
OUT = io.open(HERE/"tune_rec.txt", "w", encoding="utf-8")

chars = json.load(io.open(HERE/"rec_charset.json", encoding="utf-8"))
import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
sess = ort.InferenceSession(str(HERE/"rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
iname = sess.get_inputs()[0].name
ysess = ort.InferenceSession(str(HERE.parent/"call_label_yolo3/best.onnx"), so,
                             providers=["CPUExecutionProvider"])

# match (make_golden.py와 동일)
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

def rec_line(img):
    h, w = img.shape[:2]
    if h < 4 or w < 4: return ""
    tw = min(320, max(8, int(np.ceil(48*w/h))))
    r = cv2.resize(img, (tw, 48)).astype(np.float32)
    r = (r/255.0 - 0.5)/0.5
    pad = np.zeros((48, 320, 3), np.float32); pad[:, :tw] = r
    logits = sess.run(None, {iname: pad.transpose(2, 0, 1)[None]})[0][0]
    idx = logits.argmax(axis=1)
    out, prev = [], -1
    for t in idx:
        if t != prev and t != 0: out.append(chars[t-1] if t-1 < len(chars) else "?")
        prev = t
    return unicodedata.normalize("NFC", "".join(out))

def isolate_label(crop):
    """크림 라벨(저채도·고명도) 최장 연속 행/열 — libar_ondevice.isolate_label 확장(열도 자름)."""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:,:,1] < 70) & (hsv[:,:,2] > 135)).astype(np.uint8)
    def longest(frac, thr):
        best = (0, 0); cur = None
        for i, g in enumerate(list(frac > thr) + [False]):
            if g and cur is None: cur = i
            if not g and cur is not None:
                if i-cur > best[1]-best[0]: best = (cur, i)
                cur = None
        return best
    r0, r1 = longest(mask.mean(axis=1), 0.4)
    if r1-r0 < 8: return crop, mask
    c0, c1 = longest(mask[r0:r1].mean(axis=0), 0.5)
    if c1-c0 < 8: return crop[r0:r1], mask[r0:r1]
    return crop[r0:r1, c0:c1], mask[r0:r1, c0:c1]

def split_trim_lines(label):
    """라벨 내 잉크 행 프로파일로 줄 분할 + 줄별 좌우 트림."""
    g = cv2.cvtColor(label, cv2.COLOR_BGR2GRAY)
    thr = cv2.threshold(g, 0, 255, cv2.THRESH_OTSU)[0]
    ink = g < thr
    frac = ink.mean(axis=1)
    segs, start = [], None
    h = len(frac)
    for y in range(h+1):
        on = y < h and frac[y] > 0.06
        if on and start is None: start = y
        if not on and start is not None:
            if segs and start - segs[-1][1] <= 2: segs[-1][1] = y
            else: segs.append([start, y])
            start = None
    out = []
    minh = max(6, int(h*0.10))
    for a, b in segs:
        if b-a < minh: continue
        col = ink[a:b].mean(axis=0)
        xs = np.where(col > 0.04)[0]
        if len(xs) == 0: continue
        x0, x1 = max(0, xs[0]-2), min(label.shape[1], xs[-1]+3)
        if x1-x0 < 4: continue
        pad = max(1, (b-a)//8)
        out.append(label[max(0,a-pad):min(h,b+pad), x0:x1])
    return out

def run_variant(img, boxes, mode):
    """mode: A=현행(박스 그대로 Otsu 줄분할) / B=라벨격리+x3+트림"""
    H, W = img.shape[:2]
    n_match, reads = 0, []
    for (x0, y0, x1, y1) in boxes:
        x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(W, int(x1)), min(H, int(y1))
        if x1-x0 < 8 or y1-y0 < 8: continue
        crop = img[y0:y1, x0:x1]
        if mode == "A":
            g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            thr = cv2.threshold(g, 0, 255, cv2.THRESH_OTSU)[0]
            frac = (g < thr).mean(axis=1)
            segs, start = [], None
            h = len(frac)
            for y in range(h+1):
                on = y < h and frac[y] > 0.05
                if on and start is None: start = y
                if not on and start is not None:
                    if segs and start-segs[-1][1] <= 2: segs[-1][1] = y
                    else: segs.append([start, y]);
                    start = None
            lines = [crop[a:b] for a, b in segs if b-a >= 6] or [crop]
        else:
            label, _ = isolate_label(crop)
            label = cv2.resize(label, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
            lines = split_trim_lines(label) or [label]
        txt = " ".join(t for t in (rec_line(l) for l in lines) if t)
        row = match(txt)
        reads.append((txt, row["call"] if row else None))
        if row: n_match += 1
    return n_match, reads

for demo in (1, 2):
    img = cv2.imdecode(np.fromfile(str(HERE/f"demo/demo{demo}.jpg"), dtype=np.uint8), 1)
    H, W = img.shape[:2]
    r_ = 1280/max(H, W)
    canvas = np.full((1280, 1280, 3), 114, np.uint8)
    canvas[:int(H*r_), :int(W*r_)] = cv2.resize(img, (int(W*r_), int(H*r_)))
    x_ = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32)/255.0
    out_ = ysess.run(None, {"images": x_})[0][0]
    boxes = [tuple(b[:4]/r_) for b in out_ if b[4] >= 0.25]
    pipe = json.load(io.open(HERE/f"demo/demo{demo}.json", encoding="utf-8"))
    n_pipe = sum(1 for p in pipe if p["call"] and p.get("how") == "청구기호")
    for mode in ("A", "B"):
        n, reads = run_variant(img, boxes, mode)
        OUT.write(f"demo{demo} {mode}: {n}권 매칭 / 박스 {len(boxes)} (파이프라인 직독 {n_pipe}권)\n")
        if mode == "B":
            for t, c in reads[:30]: OUT.write(f"   {c or '-':24s} read={t!r}\n")
OUT.close(); print("done")
