# -*- coding: utf-8 -*-
"""대림 근접 사진 파이프라인 — 라벨이 커서(150px+) PaddleOCR 자체 검출이 동작함.
   색 검출은 라벨줄(밴드) 위치 찾기에만 사용, 라벨 분할은 OCR 토큰 x좌표 클러스터링.
   이중 인식: 청구기호 매칭 실패 클러스터는 책등 제목 OCR로 복구.
   사용: python daelim_closeup.py [사진경로] [--rec_dir 파인튜닝모델폴더]
"""
import os, sys, json, re, csv, time, difflib, unicodedata
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

args = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(args[0]) if args else HERE.parent/"대림데이터"/"KakaoTalk_20260707_184409459.jpg"
REC_DIR = None
if "--rec_dir" in sys.argv:
    REC_DIR = sys.argv[sys.argv.index("--rec_dir")+1]
NO_TITLE = "--no_title" in sys.argv               # 청구기호 경로만 (광각 A/B용)

def nn(s):  # ㄱ-ㅎ 자모 보존 필수: 저자기호 말미가 자모(라57ㅍ 등)
    return re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ.]", "", unicodedata.normalize("NFC", str(s)))
def ntitle(s): return re.sub(r"[^0-9A-Za-z가-힣]", "", unicodedata.normalize("NFC", str(s))).lower()

# ── 카탈로그 ──
cat = []
for r in csv.DictReader(open(HERE/"daelim_catalog.csv", encoding="utf-8-sig")):
    call = r["call_number"].strip()
    parts = call.split("-")
    if len(parts) < 2: continue
    cls, author = parts[0].strip(), parts[1].strip()
    m = re.match(r"^[가-힣A-Z]*([\d.]+)$", cls)
    cat.append({"call": call, "cls": m.group(1) if m else cls, "author": nn(author),
                "title": r["title"], "t": ntitle(r["title"].split(":")[0]), "status": r["status"]})
by_cls = {}
for c in cat: by_cls.setdefault(c["cls"], []).append(c)

# OCR이 저자기호 말미 자모를 완성형/숫자로 읽는 혼동 보정 (예: 라57피→라57ㅍ, 라570→라57ㅇ)
JAMO_FIX = {"0": "ㅇ", "O": "ㅇ", "o": "ㅇ", "Q": "ㅇ", "으": "ㅇ", "이": "ㅇ",
            "피": "ㅍ", "디": "ㄷ", "기": "ㄱ", "니": "ㄴ", "리": "ㄹ", "미": "ㅁ",
            "비": "ㅂ", "시": "ㅅ", "지": "ㅈ", "치": "ㅊ", "키": "ㅋ", "티": "ㅌ", "히": "ㅎ",
            "프": "ㅍ", "표": "ㅍ", "드": "ㄷ", "그": "ㄱ", "느": "ㄴ", "르": "ㄹ", "므": "ㅁ",
            "브": "ㅂ", "스": "ㅅ", "즈": "ㅈ", "츠": "ㅊ", "크": "ㅋ", "트": "ㅌ", "흐": "ㅎ"}

def match(txt):
    """분류번호 바로 뒤에 붙은 저자기호만 신뢰(앞 단어와 붙은 가짜 토큰 배제).
       변형 정확일치 → 동일 분류 내 퍼지(0.75, 2위와 근접하면 기권해 제목 패스로)."""
    t = nn(txt)
    # 분류번호는 정규식이 아니라 카탈로그 등재 여부로 판정 → 어떤 분류 대역이든 자동 대응
    # (오독 숫자 조각이 앞에 있을 수 있으므로 카탈로그에 있는 분류가 나올 때까지 전체 순회)
    m = None
    for m2 in re.finditer(r"(\d{3}(?:\.\d+)?)([가-힣][0-9]{1,3}[가-힣ㄱ-ㅎ0Oo]?)", t):  # 말미 ㅇ이 0으로 읽히는 경우 포함
        if m2.group(1) in by_cls: m = m2; break
    if m:
        clsv, author = m.group(1), m.group(2)
        cands = by_cls[clsv]
    else:
        # 분류번호 줄을 det가 놓친 경우: 저자기호가 카탈로그 전체에서 유일하면 그것만으로 매칭
        best = None
        for a in re.findall(r"[가-힣][0-9]{2,3}[가-힣ㄱ-ㅎ]?", t):
            vs = {a} | ({a[:-1]+JAMO_FIX[a[-1]]} if a[-1] in JAMO_FIX else set())
            hits = [c for c in cat if c["author"] in vs]
            if len(hits) == 1 and len(a) >= 4: best = hits[0]   # 4자+ & 유일할 때만 (안전장치)
        return (best, 0.9) if best else (None, 0.0)
    variants = {author}
    if author[-1] in JAMO_FIX: variants.add(author[:-1] + JAMO_FIX[author[-1]])
    hits = [c for c in cands if c["author"] in variants]
    if len(hits) > 1:                              # 동일 저자기호 복수 = 권차/복본 → 읽힌 권차로 선택
        mv = re.search(r"[vV]\.?(\d+)", txt)
        if mv:
            vhits = [c for c in hits if re.match(r"^[vV]?\.?0*%s$" % mv.group(1), c["call"].split("-")[-1])]
            if len(vhits) == 1: return vhits[0], 1.0
        if len({c["call"] for c in hits}) == 1:    # 서로 다른 책이 같은 청구기호(목록 중복) → 기호는 확정 가능
            return hits[0], 1.0
        return None, 1.0                           # 구분 불가 → 제목 패스에 위임
    if len(hits) == 1: return hits[0], 1.0
    def digit_ok(c):
        da, dc = re.sub(r"\D", "", author), re.sub(r"\D", "", c["author"])
        return not (len(da) == len(dc) and da != dc)  # 숫자부 길이 같은데 값 다름 = 다른 책 (숫자는 오독 드묾)
    scored = sorted(((max(difflib.SequenceMatcher(None, v, c["author"]).ratio()
                          for v in variants), c) for c in cands
                     if c["author"][:1] == author[:1] and digit_ok(c)),  # 성씨 글자·숫자부 불일치 퍼지 차단
                    key=lambda x: x[0])
    if not scored or scored[-1][0] < 0.75: return None, scored[-1][0] if scored else 0.0
    if len(scored) > 1 and scored[-1][0] - scored[-2][0] < 0.05: return None, scored[-1][0]
    return scored[-1][1], scored[-1][0]

def match_title(text, thr=0.62):
    full = ntitle(text)
    han = re.sub(r"[a-z0-9]", "", full)     # 책등의 원서명·저자 라틴 노이즈 제거 버전
    best, bs = None, 0.0
    for t in {full, han}:
        if len(t) < 3: continue
        for c in cat:
            if not c["t"]: continue
            lm = difflib.SequenceMatcher(None, t, c["t"]).find_longest_match(0, len(t), 0, len(c["t"]))
            p = lm.size/max(4, min(len(t), len(c["t"])))   # 한 글자 제목('숨') 오탐 방지 하한
            s = 0.6*p + 0.4*difflib.SequenceMatcher(None, t, c["t"]).ratio()
            if s > bs: best, bs = c, s
    return (best, bs) if bs >= thr else (None, bs)

# ── 밴드 탐지 (라벨 색·축소 스케일 자동 선택) ──
# 색깔 라벨은 분류 대역마다 다름(800번대=파랑, 700번대 등은 타색) → 색상 후보별로 밴드 구조를
# 찾아보고 숫자 앵커가 가장 많이 검증되는 색을 채택
im = ImageOps.exif_transpose(Image.open(SRC).convert("RGB"))
bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
H, W = bgr.shape[:2]
HUES = {"파랑": (90, 135), "초록": (35, 85), "노랑": (18, 35),
        "보라": (135, 168), "빨강": [(0, 12), (168, 180)]}

def hue_mask(hsv, hue):
    rng = HUES[hue]
    if isinstance(rng, list):
        hm = np.zeros(hsv.shape[:2], bool)
        for h0, h1 in rng: hm |= (hsv[:, :, 0] >= h0) & (hsv[:, :, 0] <= h1)
    else:
        hm = (hsv[:, :, 0] >= rng[0]) & (hsv[:, :, 0] <= rng[1])
    return hm & (hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 60)

def find_bands(small, hue):
    """행 프로파일로 라벨줄 후보 검출 (축소 스케일 좌표)."""
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    rowfrac = hue_mask(hsv, hue).mean(axis=1)
    thr = max(0.04, float(np.percentile(rowfrac, 90)) * 0.5)
    on = rowfrac > thr
    bands_, st = [], None
    for i, g in enumerate(list(on) + [False]):
        if g and st is None: st = i
        elif not g and st is not None:
            if bands_ and st - bands_[-1][1] < 12: bands_[-1] = (bands_[-1][0], i)
            elif 10 <= i - st <= 90: bands_.append((st, i))
            st = None
    return [b for b in bands_ if 10 <= b[1]-b[0] <= 110]

def digit_blobs(by0, by1, hue):
    """밴드 내 색 스티커 위 밝은 숫자(분류 첫자리) 블롭 x중심 목록 — 책 1권당 1개."""
    bh = by1 - by0
    if bh < 8: return []
    hsvb = cv2.cvtColor(bgr[by0:by1], cv2.COLOR_BGR2HSV)
    bmask = hue_mask(hsvb, hue).astype(np.uint8)
    wmask = ((hsvb[:, :, 1] < 90) & (hsvb[:, :, 2] > 130)).astype(np.uint8)
    band_d = cv2.dilate(bmask, np.ones((9, 9), np.uint8), iterations=2)
    ncc, _, stats, cent = cv2.connectedComponentsWithStats((wmask & band_d), 8)
    out = []
    for i in range(1, ncc):
        x, y, w, h, area = stats[i]
        if 0.25*bh <= h <= 0.8*bh and 0.08*bh <= w <= 0.6*bh and area >= 0.02*bh*bh:
            out.append(float(cent[i][0]))
    out.sort()
    # 획 조각 병합은 숫자 폭(~0.2bh) 수준만 — 얇은 책은 이웃 숫자 간격이 0.35bh까지 좁아짐
    return [d for j, d in enumerate(out) if j == 0 or d-out[j-1] >= bh*0.25]

def validate(bands_o, hue):
    """밴드 검증 3중: ①숫자 앵커 3개↑ ②상단 절단 아님 ③유효 최대 높이의 30%↑."""
    bd = {b: digit_blobs(*b, hue) for b in bands_o}
    ok = [b for b in bands_o if len(bd[b]) >= 3 and b[0] >= (b[1]-b[0])]
    if ok:
        hmax = max(b-a for a, b in ok)
        ok = [b for b in ok if b[1]-b[0] >= hmax*0.3]
    return ok, bd

best = (None, None, [], {}, -1)                    # (hue, scale, bands, digits, score)
for hue in HUES:
    for s in (1.0, 0.45, 0.35, 0.25):              # 1.0=광각, 0.25~0.45=근접
        small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else bgr
        cand = [(int(a/s), int(b/s)) for a, b in find_bands(small, hue)]
        ok, bd = validate(cand, hue)
        score = sum(len(bd[b]) for b in ok)        # 검증된 숫자 앵커 총수 = 색·스케일 적합도
        if score > best[4]: best = (hue, s, ok, bd, score)
HUE_SEL, SCALE, bands, band_digits, _ = best
print(f"[밴드] 라벨색={HUE_SEL} scale={SCALE} → 라벨줄 {len(bands)}개 {[(b, len(band_digits[b])) for b in bands]}")

# ── OCR (이원화) ──
# 라벨 스트립 = 저해상 특화 파인튜닝 rec (작은 청구기호 글자에 강함)
# 제목 기둥   = 범용 기존 rec (파인튜닝은 큰 글자에서 퇴화 → 제목은 원본 모델이 나음)
from paddleocr import PaddleOCR
# det·rec 모두 명시 고정 — paddleocr 3.7은 모델명 일부만 명시하면 lang을 무시하고
# 중국어 기본 rec로 폴백함 (한글이 한자로 읽히는 사고 방지)
def build_ocr(rec_dir=None):
    kw = dict(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
              use_doc_unwarping=False, use_textline_orientation=False,
              text_detection_model_name="PP-OCRv5_server_det",
              text_recognition_model_name="korean_PP-OCRv5_mobile_rec")
    if rec_dir: kw["text_recognition_model_dir"] = rec_dir
    return PaddleOCR(**kw)

ocr_label = build_ocr(REC_DIR)                              # 라벨 = 파인튜닝(있으면)
ocr_title = build_ocr(None) if (REC_DIR and not NO_TITLE) else ocr_label  # 제목 = 항상 기존 rec

def _ocr_once(img, ocr):
    res = ocr.predict(img)
    out = []
    if res:
        r = res[0]
        for txt, poly in zip(r.get("rec_texts", []), r.get("rec_polys", [])):
            p = np.array(poly)
            out.append((txt, float(p[:, 0].mean()), float(p[:, 1].mean())))
    return out

def ocr_tokens(img, ocr, chunk=1280, ov=120, maxh=1000):
    """(text, xc, yc) 리스트. 큰 이미지는 축소·가로 청크 분할(CPU 메모리 세그폴트 회피)."""
    h, w = img.shape[:2]
    if h < 320: f = min(3.0, 960/h)                # 광각 저해상 스트립은 업스케일 (rec 입력 확보)
    else: f = min(1.0, maxh/h)
    if f != 1.0:
        interp = cv2.INTER_LANCZOS4 if f > 1 else cv2.INTER_AREA
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=interp)
        h, w = img.shape[:2]
    out = []
    if max(h, w) <= chunk + ov:
        out = _ocr_once(img, ocr)
    else:
        x = 0
        while x < w:
            piece = img[:, x:min(w, x+chunk+ov)]
            for txt, xc, yc in _ocr_once(piece, ocr):
                if x > 0 and xc < ov*0.5: continue   # 겹침 영역 중복 제거
                out.append((txt, xc+x, yc))
            x += chunk
    return [(t, x/f, y/f) for t, x, y in out]

t0 = time.time()
suffix = (SRC.stem.split("459")[-1] or "_00") + ("_ft" if REC_DIR else "")
out = HERE/"out_ondevice"; out.mkdir(exist_ok=True)
CACHE = out/f"closeup{suffix}_tokens.json"
tok_cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}
rows_out = []
for bi, (by0, by1) in enumerate(bands):
    bh = by1 - by0
    sy0 = max(0, by0 - int(bh*3.5))               # 흰 스티커는 밴드 위 ~2-3배 높이
    key = f"{sy0}_{by1}"
    if key in tok_cache:
        toks = [tuple(t) for t in tok_cache[key]]
    else:
        strip = bgr[sy0:by1, :]
        toks = ocr_tokens(strip, ocr_label)        # 라벨 = 파인튜닝 rec
        toks = [(t, x, y+sy0) for t, x, y in toks]
        tok_cache[key] = toks
        json.dump(tok_cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[줄{bi}] 스티커 토큰 {len(toks)}개")
    if not toks: continue
    digits = band_digits[(by0, by1)]               # 숫자 앵커 = 책 1권 (밴드 검증 시 계산됨)
    # ── 주 신호: 토큰 간격 클러스터링 + 분류번호 앵커 재분리 (검증된 방식) ──
    toks.sort(key=lambda t: t[1])
    GAP = max(16, bh*0.35)                         # 밴드 높이 비례 (광각~16px, 근접~77px)
    clusters = [[toks[0]]]
    for t in toks[1:]:
        if t[1] - clusters[-1][-1][1] > GAP: clusters.append([t])
        else: clusters[-1].append(t)
    resplit = []
    for cl in clusters:
        # 분할 앵커는 카탈로그 검사 없이 3자리 숫자면 인정 — 오독된 분류번호도 '라벨 존재' 신호로 유효
        anchors = [t for t in cl if re.fullmatch(r"\d{3}(\.\d+)?", nn(t[0]))]
        if len(anchors) >= 2 and max(a[1] for a in anchors) - min(a[1] for a in anchors) > GAP*0.8:
            parts = {a[1]: [] for a in anchors}
            for t in cl:
                ax = min(parts, key=lambda x: abs(t[1]-x))
                parts[ax].append(t)
            # 저자기호 없는 조각(분류번호 중복 읽기 등)은 가장 가까운 정상 조각에 재합류
            good = {x: p for x, p in parts.items()
                    if any(re.search(r"[가-힣][0-9]{1,3}", nn(t[0])) for t in p)}
            if good:
                for x, p in parts.items():
                    if x not in good:
                        gx = min(good, key=lambda g: abs(g-x))
                        good[gx] = good[gx] + p
                resplit += list(good.values())
            else:
                resplit += [p for p in parts.values() if p]
        else:
            resplit.append(cl)
    clusters = resplit
    # 숫자 앵커 2개 이상을 품은 클러스터 = 책 2권 이상이 합쳐진 것 → 앵커 중간점에서 분할
    digit_split = []
    for cl in clusters:
        xs = [t[1] for t in cl]
        lo, hi = min(xs)-40, max(xs)+40
        ins = [d for d in digits if lo <= d <= hi]
        if len(ins) >= 2:
            parts = {d: [] for d in ins}
            for t in cl:
                dx = min(parts, key=lambda d: abs(t[1]-d))
                parts[dx].append(t)
            digit_split += [p for p in parts.values() if p]
        else:
            digit_split.append(cl)
    clusters = digit_split
    spans = []
    for cl in clusters:
        cl.sort(key=lambda t: (t[2], t[1]))
        txt = " ".join(t[0] for t in cl)
        row, sc = match(txt)
        xs = [t[1] for t in cl]
        x0, x1 = int(min(xs))-40, int(max(xs))+40
        spans.append((x0, x1))
        rows_out.append({"box": [max(0, x0), sy0, min(W, x1), by1], "band": bi,
                         "read": txt, "call": row["call"] if row else None,
                         "title": row["title"][:20] if row else None,
                         "how": "청구기호" if row else None, "score": round(sc, 2)})
    # 글자 클러스터가 전혀 없는 숫자 앵커 = 글자 미판독 책 → '자리'만 권수에 반영
    # (폭 넓은 책은 숫자와 라벨 글자의 x가 어긋나므로, 범위 포함이 아니라 최근접 중심 거리로 판정)
    n_ghost = 0
    dgaps = [b-a for a, b in zip(digits, digits[1:])]
    half = (float(np.median(dgaps))*0.55 if dgaps else bh*0.5)
    centers = [(x0+x1)/2 for x0, x1 in spans]
    for xc in digits:
        if centers and min(abs(xc-c) for c in centers) <= half: continue
        rows_out.append({"box": [max(0, int(xc-half)), sy0, min(W, int(xc+half)), by1],
                         "band": bi, "read": "", "call": None, "title": None,
                         "how": None, "score": 0.0})
        n_ghost += 1
    print(f"[줄{bi}] 숫자 앵커 {len(digits)}개 · 글자 미판독 책 자리 +{n_ghost}권")
n_call = sum(1 for r in rows_out if r["call"])
print(f"[청구기호 매칭] {n_call}/{len(rows_out)} · {time.time()-t0:.0f}s")

# ── 제목 복구 (미매칭 클러스터) ──
# 책 폭 추정은 '해당 줄'의 숫자 앵커 간격으로 (여러 줄의 클러스터가 x축에서 섞이면 전역 간격은 붕괴)
bspac = {}
for bi2, b in enumerate(bands):
    dg = band_digits[b]
    gaps = [y-x for x, y in zip(dg, dg[1:])]
    if gaps: bspac[bi2] = float(np.median(gaps))
    else:
        xc2 = sorted((r["box"][0]+r["box"][2])/2 for r in rows_out if r["band"] == bi2)
        g2 = [y-x for x, y in zip(xc2, xc2[1:])]
        bspac[bi2] = float(np.median(g2)) if g2 else W/15
for r in rows_out:
    if NO_TITLE or r["call"]: continue
    x0, y0s, x1, y1s = r["box"]
    xc = (x0+x1)/2
    spac = bspac.get(r["band"], W/15)
    tx0, tx1 = int(xc - spac*0.45), int(xc + spac*0.45)   # 책 폭 기준(스티커 폭은 좁을 수 있음)
    by0 = bands[r["band"]][0]
    prev_end = max([b[1] for b in bands if b[1] <= by0-10], default=0)   # 윗줄 밴드 하단
    ty0 = max(0, prev_end, by0 - int(H*0.55)); ty1 = y0s + 20
    tc = bgr[ty0:ty1, max(0, tx0):min(W, tx1)]
    if not tc.size: continue
    # 책등 제목은 세로쓰기(회전 필요)와 가로쓰기 혼재 → 둘 다 읽고 높은 점수 채택
    best_row, best_sc, best_txt = None, 0.0, ""
    for rot in (cv2.rotate(tc, cv2.ROTATE_90_COUNTERCLOCKWISE), tc):
        txt = " ".join(t[0] for t in ocr_tokens(rot, ocr_title))   # 제목 = 기존 rec
        trow, sc = match_title(txt)
        if sc > best_sc: best_row, best_sc, best_txt = trow, sc, txt
    r["ttext"] = best_txt
    if best_row:
        r["call"] = best_row["call"]; r["title"] = best_row["title"][:20]
        r["how"] = "제목복구"; r["score"] = round(best_sc, 2)
# 중복 배정 제거: 같은 청구기호가 카탈로그 등록 수보다 많이 배정되면 초과분(주로 제목복구 오지정) 해제
from collections import Counter
cat_n = Counter(c["call"] for c in cat)
by_call = {}
for r in rows_out:
    if r["call"]: by_call.setdefault(r["call"], []).append(r)
n_drop = 0
for call, rs in by_call.items():
    allow = max(1, cat_n.get(call, 1))
    if len(rs) > allow:
        rs.sort(key=lambda r: (r.get("how") == "청구기호", r.get("score", 0)), reverse=True)
        for r in rs[allow:]:
            r["call"] = None; r["how"] = None; r["title"] = None; n_drop += 1
if n_drop: print(f"[중복 배정 해제] {n_drop}건")

matched = sum(1 for r in rows_out if r["call"])
uniq = len({r["call"] for r in rows_out if r["call"]})
print(f"[이중 인식] 매칭 {matched}/{len(rows_out)} ({matched/max(1,len(rows_out))*100:.0f}%) · 고유 {uniq}권")

# ── 행별 순서(LIS) ──
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
def hkey(ch):
    """도서관 배열 순서용 문자 키: 자모 단독(ㄴ)은 같은 초성 음절(나)보다 앞."""
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
    p = call.split("-"); cls = re.sub(r"^[가-힣A-Z]+", "", p[0])
    vol = 0
    if len(p) > 2:
        mv = re.search(r"\d+", p[2]); vol = int(mv.group(0)) if mv else 0
    return (float(cls) if re.match(r"^[\d.]+$", cls) else 999,
            authkey(nn(p[1])) if len(p) > 1 else (), vol)

import libar_ondevice as L
n_mis = 0
for bi in range(len(bands)):
    seq = [r for r in rows_out if r["band"] == bi and r["call"]]
    seq.sort(key=lambda r: r["box"][0])
    mis = L.lis_misplaced([sortkey(r["call"]) for r in seq])
    for j, r in enumerate(seq):
        r["mis"] = j in mis
        if j in mis: n_mis += 1
print(f"[오배열 의심] {n_mis}건")

# ── AR 렌더 ──
d = ImageDraw.Draw(im, "RGBA")
try: fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 44)
except Exception: fs = ImageFont.load_default()
for r in rows_out:
    x0, y0, x1, y1 = r["box"]
    if r["call"] is None: c = (150, 150, 150)
    elif r.get("mis"): c = (235, 60, 60)
    elif r["how"] == "제목복구": c = (50, 130, 240)
    else: c = (40, 190, 90)
    d.rectangle([x0, y0, x1, y1], outline=c+(255,), width=7)
    if r["call"]:
        tag = r["call"].split("-")[1][:5]
        d.rectangle([x0, y0-52, x0+len(tag)*30+12, y0-2], fill=c+(235,))
        d.text((x0+5, y0-52), tag, font=fs, fill=(255, 255, 255, 255))
p = out/f"closeup{suffix}_ar.jpg"
im.save(p, quality=87)
json.dump(rows_out, open(out/f"closeup{suffix}_result.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"[완료] {p} (초록=청구기호 · 파랑=제목복구 · 빨강=오배열 의심 · 회색=미인식)")
