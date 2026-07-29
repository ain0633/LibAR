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
NO_TITLE = "--no_title" in sys.argv                 # 걷기 실시간 경로: 직독+투표만 (제목복구는 최종 화면용)

# ── 카탈로그 + 매칭 (daelim_closeup.py 검증본 복사) ──
def nn(s):
    return re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ.]", "", unicodedata.normalize("NFC", str(s)))
def ntitle(s):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", unicodedata.normalize("NFC", str(s))).lower()
cat = []
for r in csv.DictReader(open(CATALOG, encoding="utf-8-sig")):
    call = re.sub(r"\s*(?:=|[cC]\.)\d+$", "", r["call_number"].strip())
    parts = call.split("-")
    if len(parts) < 2: continue
    m = re.match(r"^[가-힣A-Z]*([\d.]+)$", parts[0].strip())
    cat.append({"call": call, "cls": m.group(1) if m else parts[0].strip(),
                "author": nn(parts[1].strip()), "title": r["title"],
                "t": ntitle(r["title"].split(":")[0])})
by_cls = {}
for c in cat: by_cls.setdefault(c["cls"], []).append(c)

JAMO_FIX = {"0": "ㅇ", "O": "ㅇ", "o": "ㅇ", "Q": "ㅇ", "으": "ㅇ", "이": "ㅇ",
            "피": "ㅍ", "디": "ㄷ", "기": "ㄱ", "니": "ㄴ", "리": "ㄹ", "미": "ㅁ",
            "비": "ㅂ", "시": "ㅅ", "지": "ㅈ", "치": "ㅊ", "키": "ㅋ", "티": "ㅌ", "히": "ㅎ",
            "프": "ㅍ", "표": "ㅍ", "드": "ㄷ", "그": "ㄱ", "느": "ㄴ", "르": "ㄹ", "므": "ㅁ",
            "브": "ㅂ", "스": "ㅅ", "즈": "ㅈ", "츠": "ㅊ", "크": "ㅋ", "트": "ㅌ", "흐": "ㅎ"}

def _vol_pick(hits, txt):
    """복본(v.1/v.2) 다의성은 읽힌 권차로 판별."""
    mv = re.search(r"[vV]\.?(\d+)", txt)
    if mv:
        vhits = [c for c in hits if re.match(r"^[vV]?\.?0*%s$" % mv.group(1), c["call"].split("-")[-1])]
        if len(vhits) == 1: return vhits[0]
    if len({c["call"] for c in hits}) == 1: return hits[0]
    return None

def match(txt):
    # 권차 수술(07-14): 걷기 909~911 미판독 10권의 진범은 검출·인식이 아니라 매칭이었다.
    # ①권차 토큰이 분류번호-저자 사이에 끼면('911 v.1 이15ㄱ') 인접 정규식이 끊김 → 매칭 전 제거
    # ②복본 다의성은 권차로 판별(폴백 포함) ③첫 글자만 오독(상↔싱)은 나머지 완전일치 유일 후보 인정
    # 재채점 실측: 걷기 판독률 89%→99% (86/87), 확인율 97% — 정답지 밖 3권은 실재 확인(심65ㅎ 등)
    t = nn(re.sub(r"[vV]\.?\d+", " ", txt))
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
            elif len(hits) > 1 and len(a) >= 4:
                p = _vol_pick(hits, txt)
                if p: best = p
        return (best, 0.9) if best else (None, 0.0)
    variants = {author}
    if author[-1] in JAMO_FIX: variants.add(author[:-1] + JAMO_FIX[author[-1]])
    hits = [c for c in cands if c["author"] in variants]
    if len(hits) > 1:
        p = _vol_pick(hits, txt)
        return (p, 1.0) if p else (None, 1.0)
    if len(hits) == 1: return hits[0], 1.0
    h3 = [c for c in cands if len(c["author"]) == len(author) and c["author"][1:] == author[1:]
          and c["author"][:1] != author[:1]]
    if len({c["author"] for c in h3}) == 1:
        p = _vol_pick(h3, txt) if len(h3) > 1 else h3[0]
        if p: return p, 0.95
    def digit_ok(c):
        da, dc = re.sub(r"\D", "", author), re.sub(r"\D", "", c["author"])
        return not (len(da) == len(dc) and da != dc)
    scored = sorted(((max(difflib.SequenceMatcher(None, v, c["author"]).ratio()
                          for v in variants), c) for c in cands
                     if c["author"][:1] == author[:1] and digit_ok(c)), key=lambda x: x[0])
    if not scored or scored[-1][0] < 0.75: return None, scored[-1][0] if scored else 0.0
    if len(scored) > 1 and scored[-1][0] - scored[-2][0] < 0.05: return None, scored[-1][0]
    return scored[-1][1], scored[-1][0]

def match_title(text, thr=0.62):
    full = ntitle(text)
    han = re.sub(r"[a-z0-9]", "", full)
    best, bs = None, 0.0
    for t in {full, han}:
        if len(t) < 3: continue
        for c in cat:
            if not c["t"]: continue
            lm = difflib.SequenceMatcher(None, t, c["t"]).find_longest_match(0, len(t), 0, len(c["t"]))
            p = lm.size/max(4, min(len(t), len(c["t"])))
            s = 0.6*p + 0.4*difflib.SequenceMatcher(None, t, c["t"]).ratio()
            if s > bs: best, bs = c, s
    return (best, bs) if bs >= thr else (None, bs)

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

_ocr_title = None
def get_ocr_title():
    """제목은 기존 rec (이원화 — 파인튜닝 rec은 큰 글자에서 퇴화).
    det도 mobile: 제목은 크롭에서 가장 큰 글자라 server det 불필요 (server는 박스당 42초 실측 → 병목)."""
    global _ocr_title
    if _ocr_title is None:
        _ocr_title = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                               use_doc_unwarping=False, use_textline_orientation=False,
                               text_detection_model_name="PP-OCRv5_mobile_det",
                               text_recognition_model_name="korean_PP-OCRv5_mobile_rec")
    return _ocr_title

def _ocr_once(img, eng=None):
    res = (eng or ocr).predict(img)
    out2 = []
    if res:
        rr = res[0]
        for txt, poly in zip(rr.get("rec_texts", []), rr.get("rec_polys", [])):
            p = np.array(poly)
            out2.append((txt, float(p[:, 0].mean()), float(p[:, 1].mean())))
    return out2

def ocr_tokens(img, eng=None, chunk=1280, ov=120, maxh=1000, up=True):
    """daelim_closeup.py 검증본: 저해상 업스케일 + 가로 청크 분할.
    up=False: 제목 크롭용 — 제목 글자는 라벨보다 커서 업스케일 불필요(×3 확대가 det 비용 9배)."""
    h, w = img.shape[:2]
    if h < 320: f = min(3.0, 960/h) if up else 1.0
    else: f = min(1.0, maxh/h)
    if f != 1.0:
        interp = cv2.INTER_LANCZOS4 if f > 1 else cv2.INTER_AREA
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=interp)
        h, w = img.shape[:2]
    if f > 1: ov = int(ov*f)   # 겹침은 원본 기준 유지 — ×3 확대 시 120px이 원본 40px로 줄어
                               # 라벨 폭(~90px)보다 좁아져 청크 경계 라벨이 통째로 유실됐음 (f00060 13→10 실측)
    out2 = []
    if max(h, w) <= chunk + ov:
        out2 = _ocr_once(img, eng)
    else:
        x = 0
        while x < w:
            piece = img[:, x:min(w, x+chunk+ov)]
            for txt, xc, yc in _ocr_once(piece, eng):
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
# 줄 간격(=책등 높이 근사): 제목 크롭 높이 상한 — 윗줄 침범·과대 크롭 방지
row_yc = [float(np.median([(b[1]+b[3])/2 for b in r])) for r in rows_of_boxes]
pitch = float(np.median(np.diff(row_yc))) if len(row_yc) >= 2 else H*0.35
rows_out = []; rows_bottom = {}
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
    # 기각 실험(07-13): 동영상 프레임에서 v2 검출이 책등 전체 박스(높이 305px↑)를 뱉어 스트립이
    # 두꺼워지고 ×3 업스케일 미발동 → 걷기 판독률 89% vs 휴리스틱 95%. 하단 45% 슬라이스로 절단
    # 시도 → 4프레임 실측 +1/-2 혼조·속도 2배 악화로 기각. 근본 원인은 검출기 학습 데이터(동영상
    # 라벨 박스가 느슨) — 수술은 파이프라인이 아니라 YOLO v3 재학습(타이트 라벨)에서.
    key = f"r{ri}_{sy0}_{sy1}_{deg:.1f}"
    rot = cv2.warpAffine(bgr, M, (W, H)) if abs(deg) > 1.5 else bgr
    if key in tok_cache:
        toks = [tuple(t) for t in tok_cache[key]]
    else:
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
    this_row = []
    for j, (ob, b) in enumerate(zip(rboxes, rb)):
        inb = sorted(assign[j], key=lambda t: (round(t[2]/30), t[1]))
        txt = " ".join(t[0] for t in inb)
        row, sc = match(txt)
        this_row.append({"box": list(map(int, ob)), "rbox": b, "band": ri, "read": txt,
                         "call": row["call"] if row else None,
                         "title": row["title"][:20] if row else None,
                         "how": "청구기호" if row else None, "score": round(sc, 2)})
    # ── 클러스터 채널(병렬): 전체 토큰을 x-연쇄로 묶어 독립 매칭 — 미검출 라벨(재현율 밖) 회수 ──
    # 걷기 151프레임 실측: 박스 배정만으로 판독률 89% vs 휴리스틱 95% — 미검출 책의 토큰이 이웃
    # 박스에 흡수돼 유실. 미배정 토큰만 쓰는 폴백은 촘촘한 프레임에서 미발동(캡 60px > 박스 간격 33px)
    # 이라 기각. 박스 배정은 그대로 두고 휴리스틱 클러스터 매칭을 병렬 채널로 — call 중복만 제거.
    have = {z["call"] for z in this_row if z["call"]}
    n_fb = 0
    if toks and rb:
        wmed = float(np.median([b[2]-b[0] for b in rb]))
        ts = sorted(toks, key=lambda t: t[1])
        cl = [[ts[0]]]
        for t in ts[1:]:
            if t[1] - cl[-1][-1][1] > wmed*0.7: cl.append([])
            cl[-1].append(t)
        for c2 in cl:
            txt = " ".join(t[0] for t in sorted(c2, key=lambda t: (round(t[2]/30), t[1])))
            row, sc = match(txt)
            if not row or row["call"] in have: continue
            xs = [t[1] for t in c2]
            fb = (min(xs)-wmed*0.4, sy0, max(xs)+wmed*0.4, sy1)
            this_row.append({"box": [int(v) for v in fb], "rbox": fb, "band": ri, "read": txt,
                             "call": row["call"], "title": row["title"][:20],
                             "how": "청구기호", "score": round(sc, 2)})
            have.add(row["call"]); n_fb += 1
    if n_fb: print(f"[줄{ri}] 클러스터 채널 +{n_fb}권 (미검출 라벨 회수)")
    # ── 제목 복구 (daelim_closeup 검증본 이식): 미매칭 박스는 라벨 위 제목 기둥을 기존 rec으로 ──
    n_rec = 0
    prev_bottom = rows_bottom.get(ri-1, 0)
    for z in this_row:
        if NO_TITLE or z["call"]: continue
        bx0, by0r, bx1, by1r = z["rbox"]
        wid = bx1 - bx0
        tx0, tx1 = int(bx0 - wid*0.15), int(bx1 + wid*0.15)
        ty0 = max(0, int(prev_bottom), int(by0r - min(H*0.55, pitch*0.95))); ty1 = int(by0r + 20)
        tkey = f"{key}_t3_{int(bx0)}"          # _t_(업스케일·전체높이)·_t2_(server det) 구세대 캐시와 분리
        if tkey in tok_cache:
            cand_txts = tok_cache[tkey]
        else:
            tc = rot[ty0:ty1, max(0, tx0):min(W, tx1)]
            if not tc.size: continue
            cand_txts = [" ".join(t[0] for t in ocr_tokens(r2, get_ocr_title(), up=False))
                         for r2 in (cv2.rotate(tc, cv2.ROTATE_90_COUNTERCLOCKWISE), tc)]
            tok_cache[tkey] = cand_txts
            json.dump(tok_cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)  # 박스 단위 저장(중단 내성)
        best_row, best_sc = None, 0.0
        for txt2 in cand_txts:
            trow, sc2 = match_title(txt2)
            if sc2 > best_sc: best_row, best_sc = trow, sc2
        if best_row:
            z["call"] = best_row["call"]; z["title"] = best_row["title"][:20]
            z["how"] = "제목복구"; z["score"] = round(best_sc, 2)
            n_rec += 1
    json.dump(tok_cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    if n_rec: print(f"[줄{ri}] 제목 복구 +{n_rec}권")
    rows_bottom[ri] = max(b[3] for b in rb)
    for z in this_row: z.pop("rbox", None)
    rows_out += this_row
print(f"[인식] 줄 {len(rows_of_boxes)}개 스트립 OCR + 제목복구 · {time.time()-t0:.0f}s")

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

# 중복 배정 제거 (카탈로그 등록 수 초과분 해제 — 주로 제목복구 오지정)
from collections import Counter
cat_n = Counter(c["call"] for c in cat)
by_call = {}
for z in rows_out:
    if z["call"]: by_call.setdefault(z["call"], []).append(z)
n_drop = 0
for call2, rs in by_call.items():
    allow = max(1, cat_n.get(call2, 1))
    if len(rs) > allow:
        rs.sort(key=lambda z: (z.get("how") == "청구기호", z.get("score", 0)), reverse=True)
        for z in rs[allow:]:
            z["call"] = None; z["how"] = None; z["title"] = None; n_drop += 1
if n_drop: print(f"[중복 배정 해제] {n_drop}건")

n_call = sum(1 for z in rows_out if z["call"])
uniq = len({z["call"] for z in rows_out if z["call"]})
print(f"[매칭] {n_call}/{len(rows_out)} 박스 · 고유 {uniq}권")

# ── 행별 순서(LIS) 오배열 판정 — daelim_closeup 검증본 이식 (4축 완성: 검출→인식→대조→판정) ──
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
def hkey(ch):
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3:
        i = o - 0xAC00
        return (i//588, i%588//28 + 1, i%28)
    if ch in _CHO: return (_CHO.index(ch), 0, 0)
    return (ord(ch)+100, 0, 0)
def authkey(a):
    m = re.match(r"^([가-힣A-Z]+)(\d*)(.*)$", a)
    if not m: return (a,)
    head, num, tail = m.groups()
    return (tuple(hkey(c) for c in head),
            float("0." + num) if num else 0,       # 커터 번호는 소수 취급: 295(.295) < 58(.58)
            tuple(hkey(c) for c in tail))
def sortkey(call):
    p = call.split("-"); cls2 = re.sub(r"^[가-힣A-Z]+", "", p[0])
    vol = 0
    if len(p) > 2:
        mv = re.search(r"\d+", p[2]); vol = int(mv.group(0)) if mv else 0
    return (float(cls2) if re.match(r"^[\d.]+$", cls2) else 999,
            authkey(nn(p[1])) if len(p) > 1 else (), vol)
import libar_ondevice as L
n_mis = 0
for bi2 in {z["band"] for z in rows_out}:
    seq = [z for z in rows_out if z["band"] == bi2 and z["call"]]
    seq.sort(key=lambda z: z["box"][0])
    mis = L.lis_misplaced([sortkey(z["call"]) for z in seq])
    for j, z in enumerate(seq):
        # 플래그는 직독만: 제목복구는 퍼지 매칭(오지정 가능)이라 오배열 경보의 근거로 쓰지 않는다
        z["mis"] = (j in mis) and z["how"] == "청구기호"
        if z["mis"]: n_mis += 1
if n_mis: print(f"[오배열 의심] {n_mis}건")

# ── AR 렌더 + 저장 ──
im = im0.convert("RGBA")
d = ImageDraw.Draw(im, "RGBA")
try: fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 40)
except Exception: fs = ImageFont.load_default()
for z in rows_out:
    x0, y0, x1, y1 = z["box"]
    if z["call"] is None: c = (150, 150, 150)
    elif z.get("mis"): c = (235, 60, 60)
    elif z["how"] == "제목복구": c = (50, 130, 240)
    else: c = (40, 190, 90)
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
