# -*- coding: utf-8 -*-
"""YOLO 검출 통합 파이프라인 (M3 본편) — 색 휴리스틱 대신 YOLO26n으로 라벨을 찾는다.

구조 = 온디바이스 설계(PRD §5.0.1)와 동일: 검출 1회 → 라벨 크롭 배치 인식 → 매칭·LIS.
색·밴드 가정이 없어서 각도·원거리·흔들림 프레임에서도 동작하는 것이 목적.
매칭 로직은 daelim_closeup.py에서 검증된 것을 그대로 복사(프로토타입 단계 의도적 중복).

사용: python daelim_yolo_pipeline.py <사진> [--catalog csv] [--rec_dir 모델] [--conf 0.25]
"""
import os, sys, json, re, csv, time, difflib, unicodedata
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

args = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(args[0])
def opt(name, default):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default
CATALOG = Path(opt("--catalog", HERE/"daelim_catalog.csv"))
REC_DIR = opt("--rec_dir", "korean_lowres_v4_rec_infer")
YOLO = opt("--yolo", "call_label_yolo2/best.onnx")
CONF = float(opt("--conf", 0.25))

# ── 카탈로그 + 매칭 (daelim_closeup.py 검증본 복사) ──
def nn(s):
    return re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ.]", "", unicodedata.normalize("NFC", str(s)))
cat = []
for r in csv.DictReader(open(CATALOG, encoding="utf-8-sig")):
    call = re.sub(r"\s*(?:=|[cC]\.)\d+$", "", r["call_number"].strip())
    parts = call.split("-")
    if len(parts) < 2: continue
    m = re.match(r"^[가-힣A-Z]*([\d.]+)$", parts[0].strip())
    cat.append({"call": call, "cls": m.group(1) if m else parts[0].strip(),
                "author": nn(parts[1].strip()), "title": r["title"]})
by_cls = {}
for c in cat: by_cls.setdefault(c["cls"], []).append(c)

JAMO_FIX = {"0": "ㅇ", "O": "ㅇ", "o": "ㅇ", "Q": "ㅇ", "으": "ㅇ", "이": "ㅇ",
            "피": "ㅍ", "디": "ㄷ", "기": "ㄱ", "니": "ㄴ", "리": "ㄹ", "미": "ㅁ",
            "비": "ㅂ", "시": "ㅅ", "지": "ㅈ", "치": "ㅊ", "키": "ㅋ", "티": "ㅌ", "히": "ㅎ",
            "프": "ㅍ", "표": "ㅍ", "드": "ㄷ", "그": "ㄱ", "느": "ㄴ", "르": "ㄹ", "므": "ㅁ",
            "브": "ㅂ", "스": "ㅅ", "즈": "ㅈ", "츠": "ㅊ", "크": "ㅋ", "트": "ㅌ", "흐": "ㅎ"}

def match(txt):
    t = nn(txt)
    m = None
    for m2 in re.finditer(r"(\d{3}(?:\.\d+)?)([가-힣][0-9]{1,3}[가-힣ㄱ-ㅎ0Oo]?)", t):
        if m2.group(1) in by_cls: m = m2; break
    if m:
        clsv, author = m.group(1), m.group(2)
        cands = by_cls[clsv]
    else:
        best = None
        for a in re.findall(r"[가-힣][0-9]{2,3}[가-힣ㄱ-ㅎ]?", t):
            vs = {a} | ({a[:-1]+JAMO_FIX[a[-1]]} if a[-1] in JAMO_FIX else set())
            hits = [c for c in cat if c["author"] in vs]
            if len(hits) == 1 and len(a) >= 4: best = hits[0]
        return (best, 0.9) if best else (None, 0.0)
    variants = {author}
    if author[-1] in JAMO_FIX: variants.add(author[:-1] + JAMO_FIX[author[-1]])
    hits = [c for c in cands if c["author"] in variants]
    if len(hits) > 1:
        mv = re.search(r"[vV]\.?(\d+)", txt)
        if mv:
            vhits = [c for c in hits if re.match(r"^[vV]?\.?0*%s$" % mv.group(1), c["call"].split("-")[-1])]
            if len(vhits) == 1: return vhits[0], 1.0
        if len({c["call"] for c in hits}) == 1: return hits[0], 1.0
        return None, 1.0
    if len(hits) == 1: return hits[0], 1.0
    def digit_ok(c):
        da, dc = re.sub(r"\D", "", author), re.sub(r"\D", "", c["author"])
        return not (len(da) == len(dc) and da != dc)
    scored = sorted(((max(difflib.SequenceMatcher(None, v, c["author"]).ratio()
                          for v in variants), c) for c in cands
                     if c["author"][:1] == author[:1] and digit_ok(c)), key=lambda x: x[0])
    if not scored or scored[-1][0] < 0.75: return None, scored[-1][0] if scored else 0.0
    if len(scored) > 1 and scored[-1][0] - scored[-2][0] < 0.05: return None, scored[-1][0]
    return scored[-1][1], scored[-1][0]

# ── 1) YOLO 검출 (1회) ──
import onnxruntime as ort
im0 = ImageOps.exif_transpose(Image.open(SRC).convert("RGB"))
bgr = cv2.cvtColor(np.array(im0), cv2.COLOR_RGB2BGR)
H, W = bgr.shape[:2]
sess = ort.InferenceSession(str(HERE/YOLO), providers=["CPUExecutionProvider"])
r = 1280/max(H, W)
canvas = np.full((1280, 1280, 3), 114, np.uint8)
canvas[:int(H*r), :int(W*r)] = cv2.resize(bgr, (int(W*r), int(H*r)))
x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32)/255.0
t0 = time.time()
out = sess.run(None, {"images": x})[0][0]
boxes = [tuple((b[:4]/r).astype(int)) for b in out if b[4] >= CONF]
print(f"[검출] YOLO 라벨 박스 {len(boxes)}개 · {time.time()-t0:.1f}s")

# ── 2) 하이브리드 인식: YOLO 박스로 '줄'을 만들고, 검증된 스트립 OCR로 읽는다 ──
# (기각 실험: 박스별 개별 크롭 OCR — det가 작은 조각에서 붕괴, 각도 3권·광각 7권으로 휴리스틱에 패배.
#  스트립 방식이 이기는 이유 = det는 문맥 있는 긴 줄에서 강함. 각도는 줄 기울기 회전 보정으로 해결.)
from paddleocr import PaddleOCR
ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_server_det",
                text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
                text_recognition_model_dir=REC_DIR)
suffix = SRC.stem
out_dir = HERE/"out_ondevice"; out_dir.mkdir(exist_ok=True)
CACHE = out_dir/f"yolo_{suffix}_tokens.json"
tok_cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}

def _ocr_once(img):
    res = ocr.predict(img)
    out2 = []
    if res:
        rr = res[0]
        for txt, poly in zip(rr.get("rec_texts", []), rr.get("rec_polys", [])):
            p = np.array(poly)
            out2.append((txt, float(p[:, 0].mean()), float(p[:, 1].mean())))
    return out2

def ocr_tokens(img, chunk=1280, ov=120, maxh=1000):
    """daelim_closeup.py 검증본: 저해상 업스케일 + 가로 청크 분할."""
    h, w = img.shape[:2]
    if h < 320: f = min(3.0, 960/h)
    else: f = min(1.0, maxh/h)
    if f != 1.0:
        interp = cv2.INTER_LANCZOS4 if f > 1 else cv2.INTER_AREA
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=interp)
        h, w = img.shape[:2]
    out2 = []
    if max(h, w) <= chunk + ov:
        out2 = _ocr_once(img)
    else:
        x = 0
        while x < w:
            piece = img[:, x:min(w, x+chunk+ov)]
            for txt, xc, yc in _ocr_once(piece):
                if x > 0 and xc < ov*0.5: continue
                out2.append((txt, xc+x, yc))
            x += chunk
    return [(t, x2/f, y2/f) for t, x2, y2 in out2]

# 줄 구성: y중심 정렬 후 연쇄 클러스터 (기울어진 줄도 인접 순서로 따라감)
bxs = sorted(boxes, key=lambda b: (b[1]+b[3])/2)
hmed = float(np.median([b[3]-b[1] for b in bxs])) if bxs else 100
rows_of_boxes, last_y = [], -1e9
for b in bxs:
    yc = (b[1]+b[3])/2
    if yc - last_y > hmed*0.8: rows_of_boxes.append([])
    rows_of_boxes[-1].append(b); last_y = yc

t0 = time.time()
rows_out = []
for ri, rboxes in enumerate(rows_of_boxes):
    if len(rboxes) < 2:  # 한 박스짜리 줄은 잡음 가능성 — 그래도 처리
        pass
    rboxes = sorted(rboxes, key=lambda b: b[0])
    xc = np.array([(b[0]+b[2])/2 for b in rboxes], dtype=float)
    yc = np.array([(b[1]+b[3])/2 for b in rboxes], dtype=float)
    deg = 0.0
    if len(rboxes) >= 3 and float(xc.max() - xc.min()) > 50:
        slope = float(np.polyfit(xc, yc, 1)[0])
        deg = float(np.degrees(np.arctan(slope)))
    # 줄 기울기 회전 보정 (각도 컷 대응)
    M = cv2.getRotationMatrix2D((W/2, H/2), deg, 1.0)
    def rot_pt(x, y): return (M[0, 0]*x + M[0, 1]*y + M[0, 2], M[1, 0]*x + M[1, 1]*y + M[1, 2])
    rb = []
    for (x0, y0, x1, y1) in rboxes:
        pts = [rot_pt(x0, y0), rot_pt(x1, y0), rot_pt(x0, y1), rot_pt(x1, y1)]
        rb.append((min(p[0] for p in pts), min(p[1] for p in pts),
                   max(p[0] for p in pts), max(p[1] for p in pts)))
    sy0 = max(0, int(min(b[1] for b in rb)))
    sy1 = min(H, int(max(b[3] for b in rb)))
    key = f"r{ri}_{sy0}_{sy1}_{deg:.1f}"
    if key in tok_cache:
        toks = [tuple(t) for t in tok_cache[key]]
    else:
        rot = cv2.warpAffine(bgr, M, (W, H)) if abs(deg) > 1.5 else bgr
        strip = rot[sy0:sy1, :]
        toks = ocr_tokens(strip)
        toks = [(t, x2, y2+sy0) for t, x2, y2 in toks]      # 회전 좌표계 절대값
        tok_cache[key] = toks
        json.dump(tok_cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[줄{ri}] 박스 {len(rboxes)}개 · 기울기 {deg:.1f}° · 토큰 {len(toks)}개")
    # 토큰 → 최근접 박스 배정 (엄격한 '박스 안쪽' 규칙은 경계 토큰을 버려 600_11에서 9권 실측 — 기각)
    centers = [((b[0]+b[2])/2, b) for b in rb]
    assign = {i: [] for i in range(len(rb))}
    for t in toks:
        j = min(range(len(centers)), key=lambda k: abs(centers[k][0] - t[1]))
        bx = centers[j][1]
        if abs(centers[j][0] - t[1]) <= max(60, (bx[2]-bx[0]) * 0.9):
            assign[j].append(t)
    for j, (ob, b) in enumerate(zip(rboxes, rb)):
        inb = sorted(assign[j], key=lambda t: (round(t[2]/30), t[1]))
        txt = " ".join(t[0] for t in inb)
        row, sc = match(txt)
        rows_out.append({"box": list(map(int, ob)), "band": ri, "read": txt,
                         "call": row["call"] if row else None,
                         "title": row["title"][:20] if row else None,
                         "how": "청구기호" if row else None, "score": round(sc, 2)})
print(f"[인식] 줄 {len(rows_of_boxes)}개 스트립 OCR · {time.time()-t0:.0f}s")

# 같은 책의 중복 박스(YOLO 이중 검출) 정리: 같은 call이 x 근접 박스에 2회 → 1회
seen = {}
for rr in rows_out:
    if not rr["call"]: continue
    k = rr["call"]
    if k in seen and abs(seen[k]["box"][0] - rr["box"][0]) < (rr["box"][2]-rr["box"][0])*2:
        loser = min(seen[k], rr, key=lambda z: z["score"])
        loser["call"] = None; loser["how"] = None
        if loser is seen[k]: seen[k] = rr
    else: seen[k] = rr

n_call = sum(1 for z in rows_out if z["call"])
uniq = len({z["call"] for z in rows_out if z["call"]})
print(f"[매칭] {n_call}/{len(rows_out)} 박스 · 고유 {uniq}권")

# ── AR 렌더 + 저장 ──
im = im0.convert("RGBA")
d = ImageDraw.Draw(im, "RGBA")
try: fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 40)
except Exception: fs = ImageFont.load_default()
for z in rows_out:
    x0, y0, x1, y1 = z["box"]
    c = (40, 190, 90) if z["call"] else (150, 150, 150)
    d.rectangle([x0, y0, x1, y1], outline=c+(255,), width=6)
    if z["call"]:
        d.text((x0, max(0, y0-46)), z["call"].split("-")[-1], fill=(0, 90, 0, 255), font=fs,
               stroke_width=2, stroke_fill=(255, 255, 255, 255))
im = im.convert("RGB")
p = out_dir/f"yolo_{suffix}_ar.jpg"
im.save(p, quality=87)
json.dump(rows_out, open(out_dir/f"yolo_{suffix}_result.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"[완료] {p}")
