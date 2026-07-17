# -*- coding: utf-8 -*-
"""사람 라벨링 배치 생성: 무정답 크롭 → v4 판독·선명도 → 상위 N개를 후보와 함께 JSON으로.
사람 눈이 정답을 붙이면 소급 매칭의 선택 편향(모델이 읽는 것만 재료화)이 끊긴다.
출력: webdemo/label_batch.json — label.html이 로드, 제출은 드라이브 수신함(POST).
사용: py -3.12 make_label_batch.py [--top 600]
"""
import io, sys, json, glob, re, zipfile, hashlib, base64, difflib, unicodedata, csv
import cv2, numpy as np
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
TOP = int(sys.argv[sys.argv.index("--top")+1]) if "--top" in sys.argv else 600

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
rsess = ort.InferenceSession(str(HERE/"webdemo/rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
dsess = ort.InferenceSession(str(HERE/"webdemo/det_mobile.onnx"), so, providers=["CPUExecutionProvider"])
rin, din = rsess.get_inputs()[0].name, dsess.get_inputs()[0].name
chars = json.load(io.open(HERE/"webdemo/rec_charset.json", encoding="utf-8"))
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)

def nfc(s): return unicodedata.normalize("NFC", str(s))

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

# 카탈로그: 후보 제시용 (call → title)
CALL_TITLE = {}
CLS_AUTH = defaultdict(set)
for row in csv.DictReader(io.open(HERE/"catalog_full.csv", encoding="utf-8-sig")):
    call = nfc(row["call_number"])
    CALL_TITLE.setdefault(call, row["title"])
    parts = call.split("-")
    if len(parts) >= 2 and parts[0] and parts[1]:
        CLS_AUTH[parts[0]].add(parts[1])
CLS_LIST = sorted(CLS_AUTH)

def cands_from(reads):
    """판독 줄들 → 후보 청구기호 상위 5 (느슨 — 사람이 고르는 용도라 오답 후보 무해)."""
    scored = {}
    for r1 in reads:
        for cls in difflib.get_close_matches(r1, CLS_LIST, n=3, cutoff=0.55):
            base = difflib.SequenceMatcher(None, r1, cls).ratio()
            for r2 in reads:
                if r2 is r1: continue
                for a in CLS_AUTH[cls]:
                    s = difflib.SequenceMatcher(None, r2, a).ratio()
                    if s < 0.45: continue
                    call = f"{cls}-{a}"
                    scored[call] = max(scored.get(call, 0), base + s)
    return [c for c, _ in sorted(scored.items(), key=lambda kv: -kv[1])[:5]]

# 정답 이미 있는 크롭 제외
done = set()
for l in io.open(HERE/"real_rec_data_field_v6/meta_field.txt", encoding="utf-8"):
    p = l.split("\t")[0].split("/")[1].rsplit(".", 1)[0].split("_")
    done.add((p[0], f"{p[1]}_{p[2]}"))

# 선명도(라플라시안)는 글자 없는 쨍한 모서리에도 점수를 준다(1차 배치의 1번 조각 사고) —
# 글자 줄(det)이 실제로 잡히는 조각만 라벨링 대상, 줄 0개는 하드 네거티브 후보로 분리.
seen, pool = set(), []
for zp in sorted(glob.glob(str(HERE/"수집조각/libar_crops_*.zip"))):
    ztag = Path(zp).stem.replace("libar_crops_", "")
    with zipfile.ZipFile(zp) as z:
        man = json.loads(z.read("manifest.json").decode("utf-8"))
        if "Windows" in man.get("device", ""): continue
        for c in man.get("crops", []):
            raw = z.read(c["file"]); h = hashlib.md5(raw).hexdigest()
            if h in seen: continue
            seen.add(h)
            stem = c["file"].rsplit(".", 1)[0]
            if (ztag, stem) in done or c.get("call"): continue
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
            if img is None or img.shape[0] < 60: continue
            sharp = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
            if sharp < 80: continue                     # 사람도 못 읽을 뭉개짐은 제외
            pool.append((sharp, ztag, stem, img))
pool.sort(key=lambda t: -t[0])
print(f"[풀] {len(pool)}개 — 글자 줄 유무 판별 중…")

out, hardneg = [], []
for k, (sharp, ztag, stem, img) in enumerate(pool):
    if len(out) >= TOP: break
    big = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
    lines = det_lines(big)
    if not lines:                                       # 글자 줄 0 = 오탐/빈 조각 → 검출기 재료
        hardneg.append(f"{ztag}_{stem}")
        continue
    reads = [r for _, line in lines if len(r := rec_line(line)) >= 2]
    h, w = img.shape[:2]
    disp = cv2.resize(img, (int(w*260/h), 260)) if h > 260 else img
    jpg = cv2.imencode(".jpg", disp, [cv2.IMWRITE_JPEG_QUALITY, 82])[1]
    out.append({"id": f"{ztag}_{stem}", "img": "data:image/jpeg;base64," + base64.b64encode(jpg).decode(),
                "reads": reads, "nl": len(lines),
                "cands": [{"call": c, "title": CALL_TITLE.get(c, "")[:28]} for c in cands_from(reads)]})
    if (k+1) % 200 == 0: print(f"  훑음 {k+1} → 채택 {len(out)}")
# 글자 줄 많은 조각(온전한 라벨일 확률↑)부터 — 라벨링 체감 속도용 2차 정렬
out.sort(key=lambda it: (-it["nl"], -len(it["reads"])))
for it in out: it.pop("nl")
io.open(HERE/"hardneg_candidates.txt", "w", encoding="utf-8").write("\n".join(hardneg) + "\n")
print(f"[분리] 하드 네거티브 후보 {len(hardneg)}개 → hardneg_candidates.txt (검출기 v4 재료)")

path = HERE/"webdemo/label_batch.json"
json.dump({"made": "260717", "n": len(out), "items": out},
          io.open(path, "w", encoding="utf-8"), ensure_ascii=False)
print(f"[출력] {path} — {path.stat().st_size//1024}KB · {len(out)}개")
