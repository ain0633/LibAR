# -*- coding: utf-8 -*-
"""페어 정렬 수확기 — 같은 단의 근접(정답) ↔ 광각(문제) 크롭 이식.

원리: 근접샷에서 카탈로그로 확정한 책 순서(답안지)를, 광각샷 같은 단의 슬롯 순서(문제집)에
     이식한다. 양쪽에서 모두 읽힌 청구기호(고유값)를 고정점 삼아 순서를 정렬하고,
     고정점 사이 슬롯 수가 정확히 일치하는 구간만 1:1 이식(모호 구간은 버림 — 정밀도 우선).

산출: 광각의 "모델이 못 읽은 저해상 크롭 + 확실한 정답" 학습쌍 (진짜 hard 샘플)
"""
import json, re, sys, io, glob, os
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

def imread(p): return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), 1)

def stem_800_close(s):
    return "KakaoTalk_20260707_184409459" + ("" if s == "_00" else s)

# (섹션, result 폴더, 사진 폴더, 파일명 복원)
CFG = [
    ("600", HERE/"out_ondevice", HERE.parent/"대림데이터/600번대", lambda s: s),
    ("700", HERE/"out_ondevice", HERE.parent/"대림데이터/700번대", lambda s: s),
    ("800w", HERE/"daelim_v3_results/out_ondevice", HERE.parent/"대림데이터", lambda s: s),
    ("800c", HERE/"out_ondevice", HERE.parent/"대림데이터", stem_800_close),
]

def load_frames():
    frames = {}   # stem → dict(sec, photo, bands={bi: [rows sorted by x]})
    for sec, rd, pd, restore in CFG:
        for rf in sorted(glob.glob(str(rd/"*_ft_result.json"))):
            stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
            photo = pd/f"{restore(stem)}.jpg"
            if not photo.exists(): continue
            key = f"{sec[:3]}:{stem}"
            if any(k.endswith(":"+stem) for k in frames): continue   # 같은 사진 중복 소스 방지
            rows = json.load(open(rf, encoding="utf-8"))
            bands = {}
            for r in rows: bands.setdefault(r["band"], []).append(r)
            for b in bands.values(): b.sort(key=lambda r: r["box"][0])
            m = sum(1 for r in rows if r["call"])
            frames[key] = dict(sec=sec[:3], photo=photo, bands=bands,
                               rate=m/max(1, len(rows)), n=len(rows))
    return frames

def lis_pairs(pairs):
    """(i_truth, i_target) 쌍에서 양쪽 모두 증가하는 최장 부분열 (고정점 정합, O(n²))."""
    pairs = sorted(pairs)
    if not pairs: return []
    n = len(pairs); dp = [1]*n; prev = [-1]*n
    for i in range(n):
        for j in range(i):
            if pairs[j][0] < pairs[i][0] and pairs[j][1] < pairs[i][1] and dp[j]+1 > dp[i]:
                dp[i] = dp[j]+1; prev[i] = j
    i = max(range(n), key=lambda k: dp[k]); out = []
    while i != -1: out.append(pairs[i]); i = prev[i]
    return out[::-1]

def text_lines(crop):
    """흰 라벨 영역 안의 텍스트 줄 분리 — 저해상(광각) 크롭용 완화판.
       (근접 수확기보다 임계 완화: 어두운 구석·40px급 라벨에서도 줄이 잡히도록)"""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    white = (hsv[:, :, 1] < 100) & (hsv[:, :, 2] > 135)
    wrow = white.mean(axis=1)
    H, W = crop.shape[:2]
    runs, st = [], None
    for i, g in enumerate(list(wrow > 0.25) + [False]):
        if g and st is None: st = i
        elif not g and st is not None: runs.append((st, i)); st = None
    if not runs: return []
    wy0, wy1 = max(runs, key=lambda r: r[1]-r[0])
    if wy1 - wy0 < 16: return []
    dark = hsv[:, :, 2] < 120
    drow = dark[wy0:wy1].sum(axis=1)
    on = drow > W*0.04
    lines, st = [], None
    for i, g in enumerate(list(on) + [False]):
        if g and st is None: st = i
        elif not g and st is not None:
            if lines and st - lines[-1][1] <= 2: lines[-1] = (lines[-1][0], i)
            elif i - st >= 4: lines.append((st, i))
            st = None
    out = []
    for a, b in lines:
        if b - a < 5: continue
        seg = dark[wy0+a:wy0+b]
        cols = np.where(seg.any(axis=0))[0]
        if len(cols) < 5 or (cols[-1]-cols[0]) < W*0.15: continue
        out.append((wy0+a, wy0+b))
    # 3줄 이상이면 위 2줄만 (아래 줄은 복본 스티커·바코드일 확률)
    return out[:2] if len(out) >= 2 else out

def call_parts(call):
    m = re.match(r"^(.*?)-(.+?)(?:-(.+))?$", call)
    if not m or m.group(3): return None
    return [m.group(1), m.group(2)]

def band_line_gap(gf, gb):
    """밴드 전체 슬롯들의 토큰 행 간격 중앙값 — 한 줄짜리 슬롯의 분류/저자 판별 자로 사용."""
    key = ("_gap", gb)
    if key in gf: return gf[key]
    gaps = []
    for rg in gf["bands"][gb]:
        rows = _slot_rows(gf, rg)
        gaps += [b-a for a, b in zip(rows, rows[1:]) if 12 <= b-a <= 90]
    gf[key] = float(np.median(gaps)) if gaps else None
    return gf[key]

def _slot_cache(gk, gf):
    if "_cache" not in gf:
        stem = gk.split(":", 1)[1]
        cp = HERE/"out_ondevice"/f"closeup{stem}_ft_tokens.json"
        gf["_cache"] = json.load(open(cp, encoding="utf-8")) if cp.exists() else {}
    return gf["_cache"]

def _slot_rows(gf, rg):
    """슬롯의 스티커 위 토큰 행 y중심 목록 (아래쪽 최대 2행)."""
    cache = gf.get("_cache", {})
    x0, sy0, x1, by1 = rg["box"]
    key = f"{sy0}_{by1}"
    toks = cache.get(key)
    if toks is None:
        for k in cache:
            ks, ke = map(int, k.split("_"))
            if abs(ke - by1) <= 80 and ks <= sy0 + 40: toks = cache[k]; break
    if not toks: return []
    bh = (by1 - sy0) / 4.5
    by0_est = by1 - bh
    inside = [y for _, x, y in toks if x0 + 10 <= x <= x1 - 10 and y < by0_est - 5]
    if not inside: return []
    ys = sorted(inside)
    rows = [[ys[0]]]
    for y in ys[1:]:
        if y - rows[-1][-1] <= 18: rows[-1].append(y)
        else: rows.append([y])
    return [sum(r)/len(r) for r in rows][-2:]

def token_rows(gk, gf, rg, gb):
    """슬롯의 라벨 줄 위치·정체 복원 → [(y0, y1, 줄인덱스 0=분류 1=저자), ...]
       두 행이 보이면 위=분류/아래=저자. 한 행만 보이면 밴드 중앙값 간격으로
       스티커와의 거리를 재서 분류/저자를 판별 (한 줄짜리도 학습쌍으로 회수)."""
    _slot_cache(gk, gf)
    x0, sy0, x1, by1 = rg["box"]
    bh = (by1 - sy0) / 4.5
    by0_est = by1 - bh
    centers = _slot_rows(gf, rg)
    if not centers: return []
    if len(centers) == 2:
        g = centers[1] - centers[0]
        if not (12 <= g <= 90): return []
        if by0_est - centers[1] > g * 1.6: return []          # 저자 행이 스티커에서 너무 멀면 제목 꼬리 의심
        h = g * 0.55
        return [(int(c - h), int(c + h), i) for i, c in enumerate(centers)]
    g = band_line_gap(gf, gb)
    if not g: return []
    d = by0_est - centers[0]                                  # 스티커까지 거리
    if 0 < d <= g * 0.9: idx = 1                              # 스티커 바로 위 = 저자
    elif g * 1.5 <= d <= g * 2.3: idx = 0                     # 한 칸 위 = 분류
    else: return []                                           # 모호 구간·제목 꼬리 → 기각
    h = g * 0.55
    return [(int(centers[0] - h), int(centers[0] + h), idx)]

frames = load_frames()
truths = {k: f for k, f in frames.items() if f["rate"] >= 0.6}            # 근접급 정답 프레임
targets = {k: f for k, f in frames.items() if f["rate"] < 0.5 and f["n"] >= 30}  # 광각급 문제 프레임
print(f"[프레임] 정답 {len(truths)}개 · 문제 {len(targets)}개")

OUT = HERE/"real_rec_data_v3"; (OUT/"crops").mkdir(parents=True, exist_ok=True)
pairs_out = []; photo_cache = {}
for tk, tf in truths.items():
    for tb, tseq in tf["bands"].items():
        tcalls = [r["call"] for r in tseq]
        t_uniq = {c: i for i, c in enumerate(tcalls) if c and tcalls.count(c) == 1}
        for gk, gf in targets.items():
            if gf["sec"] != tf["sec"]: continue
            for gb, gseq in gf["bands"].items():
                gcalls = [r["call"] for r in gseq]
                g_uniq = {c: i for i, c in enumerate(gcalls) if c and gcalls.count(c) == 1}
                common = [(t_uniq[c], g_uniq[c]) for c in t_uniq if c in g_uniq]
                anchors = lis_pairs(common)
                if len(anchors) < 3: continue                       # 고정점 3개↑만 신뢰
                n_new = 0
                xc = lambda r: (r["box"][0] + r["box"][2]) / 2
                for (a0, b0), (a1, b1) in zip(anchors, anchors[1:]):
                    gap_t = tseq[a0+1:a1]; gap_g = gseq[b0+1:b1]
                    if not gap_t or not gap_g: continue
                    if len(gap_t) == len(gap_g):
                        matched = list(zip(gap_t, gap_g))
                    else:
                        # 슬롯 수 불일치 갭: 고정점 사이 x좌표 비례 투영 + 상호 최근접만 (검출 누락분 회수)
                        tx0, tx1 = xc(tseq[a0]), xc(tseq[a1])
                        gx0, gx1 = xc(gseq[b0]), xc(gseq[b1])
                        if tx1 - tx0 < 1 or gx1 - gx0 < 1: continue
                        proj = lambda rt: gx0 + (xc(rt) - tx0) / (tx1 - tx0) * (gx1 - gx0)
                        pitch = (gx1 - gx0) / (max(len(gap_t), len(gap_g)) + 1)
                        matched = []
                        for rt in gap_t:
                            px = proj(rt)
                            bg = min(gap_g, key=lambda r2: abs(xc(r2) - px))
                            if abs(xc(bg) - px) > pitch * 0.4: continue
                            bt = min(gap_t, key=lambda r2: abs(proj(r2) - xc(bg)))
                            if bt is not rt: continue                    # 상호 최근접이 아니면 모호 → 버림
                            matched.append((rt, bg))
                    for rt, rg in matched:
                        if not rt["call"]: continue
                        if rg["call"] == rt["call"]: continue            # 이미 읽힌 건 기존 수확에 있음
                        if not rg.get("read"): continue                  # 유령 슬롯(위치 추정 박스)은 라벨 위치 불확실 → 제외
                        parts = call_parts(rt["call"])
                        if not parts: continue
                        lines = token_rows(gk, gf, rg, gb)               # det가 글자를 본 실제 y좌표 (+줄 정체)
                        if not lines: continue
                        if gk not in photo_cache: photo_cache[gk] = imread(gf["photo"])
                        photo = photo_cache[gk]
                        x0, _, x1, _ = rg["box"]
                        for (ly0, ly1, idx) in lines:
                            txt = parts[idx]
                            li = photo[max(0, ly0):ly1, max(0, x0):x1]
                            if li.size == 0 or li.shape[0] < 10 or li.shape[1] < 32: continue
                            hsvl = cv2.cvtColor(li, cv2.COLOR_BGR2HSV)
                            if (hsvl[:, :, 2] < 60).mean() > 0.25: continue  # 검정 스티커가 섞인 크롭 → 기각
                            name = f"pair_{gk.split(':')[1]}_{gb}_{rg['box'][0]}_{txt}.jpg"
                            cv2.imencode(".jpg", li, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(OUT/"crops"/name))
                            pairs_out.append((f"crops/{name}", txt))
                            n_new += 1
                if n_new:
                    print(f"  {tk}(줄{tb}) → {gk}(줄{gb}): 고정점 {len(anchors)} · 이식 줄 {n_new}")

print(f"[페어 수확] 신규 학습 줄 {len(pairs_out)}개")
io.open(OUT/"pairs.txt", "w", encoding="utf-8").write("".join(f"{p}\t{t}\n" for p, t in pairs_out))
