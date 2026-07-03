# -*- coding: utf-8 -*-
"""LibAR 샘플 파이프라인 v2.1 — 한 컷 스캔 모드
서가 사진 1장 + 정답 기준표(books.csv) → 오배열 판정 오버레이 이미지 + JSON

파이프라인 (PRD §5.0):
  ① 탐지: YOLO(책등) + CV(청구기호 라벨 스티커)   ← 라벨 우선(Label-first)
  ② 라벨 크롭 → OCR (EasyOCR, 어댑터 교체 가능)
  ③ 신뢰도 게이트: 미달 → '판독 불가(회색)' — 판정 제외
  ④ 기준표 대조 + 오토코렉트 (기준표가 OCR 출력 공간을 제약)
  ⑤ LIS 오배열 판정 (인접 비교 아님)
  ⑥ 오버레이: 🔴오배열 🟢검색도서 ⚪판독불가 🔵기준표 미등록

사용법:
  python pipeline.py test_shelf.jpg                     # 사서 모드
  python pipeline.py my_shelf.jpg --search "813.7-김94ㅎ"  # 이용자 모드
"""
import argparse
import csv
import difflib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

os.environ.setdefault("FLAGS_use_mkldnn", "0")  # paddle 3.3 oneDNN(PIR) 버그 회피 (import 전 설정)

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
CONF_GATE = 0.35  # ③ 신뢰도 게이트 임계값

# ────────────────────────── 공통 유틸 ──────────────────────────

def norm(s: str) -> str:
    """청구기호 정규화: 공백/구분자 제거 + NFC"""
    return re.sub(r"[\s\-–—_/·.]+", "", unicodedata.normalize("NFC", str(s))).lower()


def norm_title(s: str) -> str:
    """제목 정규화: 한글/영숫자만 남김"""
    return re.sub(r"[^0-9a-z가-힣]", "", unicodedata.normalize("NFC", str(s)).lower())


CALLNUM_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)[\s\-]*([가-힣ㄱ-ㅎㅏ-ㅣ][가-힣ㄱ-ㅎㅏ-ㅣ0-9]{0,8})?(?:[\s\-]*[vV]\.?\s*(\d+))?"
)


def parse_callnum(text: str):
    """OCR 텍스트에서 청구기호 구조 추출 → (분류번호, 저자기호, 권차) or None"""
    t = unicodedata.normalize("NFC", text)
    m = CALLNUM_RE.search(t)
    if not m or m.group(1) is None:
        return None
    return {
        "class": float(m.group(1)),
        "author": m.group(2) or "",
        "vol": int(m.group(3)) if m.group(3) else 0,
    }


def author_key(a: str):
    """저자기호 '김94ㅎ' → 가나다·숫자 혼합 정렬 키"""
    toks = []
    for run in re.finditer(r"\d+|\D", a):
        t = run.group()
        toks.append((0, int(t)) if t.isdigit() else (1, t))
    return tuple(toks)


def sort_key(p):
    return (p["class"], author_key(p["author"]), p["vol"])


# ────────────────── ① 탐지 (YOLO 책등 + CV 라벨) ──────────────────

def detect_labels_cv(bgr: np.ndarray):
    """청구기호 라벨(흰 스티커) 후보 탐지 — 밝고 채도 낮은 사각형"""
    H, W = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] < 70) & (hsv[:, :, 2] > 160)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area, img_area = w * h, H * W
        if not (0.0004 * img_area < area < 0.05 * img_area):
            continue
        if not (0.35 <= w / h <= 6):
            continue
        if cv2.contourArea(c) / area < 0.45:  # 채움비(비정형 반사광 제거)
            continue
        boxes.append([x, y, x + w, y + h])
    boxes.sort(key=lambda b: (b[0] + b[2]) / 2)  # 좌→우 (물리적 배열 순서)
    return boxes


def detect_books_yolo(bgr: np.ndarray):
    """YOLO로 책등 탐지.
    우선순위: best.pt(파인튜닝, train_spine_colab.ipynb 산출물) → YOLO26n → YOLO11n"""
    from ultralytics import YOLO
    model, name = None, None
    candidates = ["yolo26n.pt", "yolo11n.pt"]
    if (HERE / "best.pt").exists():
        candidates.insert(0, str(HERE / "best.pt"))
    for name in candidates:
        try:
            model = YOLO(name)
            print(f"[YOLO] {name} 로드")
            break
        except Exception as e:
            print(f"[YOLO] {name} 실패({type(e).__name__}) → 폴백 시도")
    if model is None:
        return []
    # COCO 사전학습이면 'book' 클래스만, 파인튜닝 모델이면 전체 클래스 허용
    book_ids = [i for i, n in model.names.items() if n == "book"]
    if not book_ids:
        book_ids = list(model.names)
    res = model.predict(source=bgr, conf=0.2, verbose=False)[0]
    boxes = []
    for b in res.boxes:
        if int(b.cls) in book_ids:
            boxes.append([int(v) for v in b.xyxy[0].tolist()])
    return boxes


def spine_box_for(label_box, book_boxes, img_h):
    """라벨 → 소속 책등 박스 연결. YOLO가 못 찾으면 라벨 위로 확장 추정"""
    lx = (label_box[0] + label_box[2]) / 2
    ly = (label_box[1] + label_box[3]) / 2
    for bb in book_boxes:
        if bb[0] <= lx <= bb[2] and bb[1] <= ly <= bb[3]:
            return bb, True
    lw = label_box[2] - label_box[0]
    lh = label_box[3] - label_box[1]
    return [label_box[0] - int(lw * 0.08), max(0, label_box[1] - lh * 6),
            label_box[2] + int(lw * 0.08), min(img_h, label_box[3] + int(lh * 0.2))], False


# ────────────────────── ② OCR (어댑터 계층) ──────────────────────
# 모든 어댑터는 read(crop_bgr) -> (text, confidence) 계약을 지킨다.
# 엔진 교체는 이 계층에서만 일어나므로 파이프라인 나머지는 영향 없음.

def _upscale(crop_bgr: np.ndarray, min_h: int = 90) -> np.ndarray:
    h = crop_bgr.shape[0]
    if h < min_h:
        s = min_h / h
        return cv2.resize(crop_bgr, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    return crop_bgr


class EasyOCRAdapter:
    """기본 OCR — 설치가 가벼움. 다국어."""

    name = "easyocr"

    def __init__(self):
        import easyocr
        self.reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)

    def read(self, crop_bgr: np.ndarray):
        results = self.reader.readtext(_upscale(crop_bgr), detail=1, paragraph=False)
        if not results:
            return "", 0.0
        texts = [r[1] for r in results]
        confs = [float(r[2]) for r in results]
        return " ".join(texts), float(np.mean(confs))


class PaddleOCRv5Adapter:
    """한국어 전용 PP-OCRv5 (korean_PP-OCRv5_mobile_rec), PaddleOCR 3.x API.
    청구기호처럼 짧은 한글+숫자 인식에서 EasyOCR 대비 신뢰도 우위."""

    name = "ppocrv5-ko"

    def __init__(self):
        # paddle 3.3 + paddleocr 3.7 CPU: oneDNN(PIR) 미구현 버그 회피 → mkldnn 비활성화
        import os
        os.environ.setdefault("FLAGS_use_mkldnn", "0")
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(lang="korean", use_textline_orientation=True,
                             enable_mkldnn=False)

    def read(self, crop_bgr: np.ndarray):
        res = self.ocr.predict(_upscale(crop_bgr))
        if not res:
            return "", 0.0
        r0 = res[0]
        texts = list(r0.get("rec_texts", []))
        scores = list(r0.get("rec_scores", []))
        if not texts:
            return "", 0.0
        conf = float(np.mean(scores)) if scores else 0.0
        return " ".join(str(t) for t in texts), conf


def make_ocr(engine: str):
    """--ocr 플래그로 엔진 선택. 실패 시 EasyOCR로 폴백."""
    if engine in ("ppocr", "paddle", "ppocrv5"):
        try:
            a = PaddleOCRv5Adapter()
            print(f"[OCR] PP-OCRv5(korean) 로드")
            return a
        except Exception as e:
            print(f"[OCR] PP-OCRv5 로드 실패({type(e).__name__}: {e}) → EasyOCR 폴백")
    a = EasyOCRAdapter()
    print(f"[OCR] EasyOCR 로드")
    return a


def ocr_spine_title(ocr, bgr: np.ndarray, spine_box, label_box):
    """책등 제목 영역(라벨 위쪽) OCR — 세로쓰기 대응으로 3방향 시도 후 최선 채택"""
    x1, y1, x2, y2 = [int(v) for v in spine_box]
    ly1 = int(label_box[1])
    crop = bgr[y1 + 4:max(y1 + 5, ly1 - 6), max(0, x1 + 2):x2 - 2]
    if crop.shape[0] < 40 or crop.shape[1] < 15:
        return "", 0.0
    variants = [crop,
                cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE),
                cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)]
    best_text, best_conf, best_score = "", 0.0, 0.0
    for v in variants:
        text, conf = ocr.read(v)
        score = conf * min(len(norm_title(text)), 12)  # 읽힌 양 × 신뢰도
        if score > best_score:
            best_text, best_conf, best_score = text, conf, score
    return best_text, best_conf


# ──────────────── ④ 기준표 대조 + 오토코렉트 ────────────────

def match_catalog(ocr_text: str, catalog: list):
    """OCR 결과를 기준표와 대조. 기준표(그 서가에 꽂혀야 할 책 목록)가
    OCR 출력 공간을 제약하는 구조.
    현장 조건 반영: 라벨이 감기거나 가려져 청구기호가 '부분만' 보여도,
    부분 문자열 점수로 매칭. 여러 책과 비슷하게 겹치면(모호) 매칭 포기 → 회색."""
    n = norm(ocr_text)
    if not n:
        return None, 0.0

    def partial_score(a: str, b: str) -> float:
        """최장 공통 부분문자열 / 짧은 쪽 길이 — 부분 판독에 관대한 점수"""
        if not a or not b:
            return 0.0
        m = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
        return m.size / min(len(a), len(b))

    # 1) 포함 매칭 — 단, 기준표에서 '유일'할 때만 인정 (813.7처럼 여러 책과
    #    겹치는 조각은 모호 → 매칭 포기해야 오탐이 없다)
    containing = [row for row in catalog if (row["_norm"] in n) or (n in row["_norm"])]
    if len(containing) == 1:
        return containing[0], 1.0
    if len(containing) > 1:
        return None, 0.5  # 모호(여러 책과 일치) → 판독불가 처리

    # 2) 구조 인지 매칭 — 분류번호가 읽혔다면 그 번호의 책들로 후보를 좁힌다.
    #    (저자기호가 오독돼도 분류번호가 유일하면 확정 가능)
    p = parse_callnum(ocr_text)
    if p is not None:
        same_class = [row for row in catalog
                      if row["_parsed"] and row["_parsed"]["class"] == p["class"]]
        if len(same_class) == 1:
            return same_class[0], 0.9
        if len(same_class) > 1:
            if not p["author"]:
                return None, 0.5  # 분류번호만으론 구분 불가 → 모호
            scored = []
            for row in same_class:
                a, b = p["author"], row["_parsed"]["author"]
                s = 0.6 * partial_score(a, b) + 0.4 * difflib.SequenceMatcher(None, a, b).ratio()
                scored.append((s, row))
            scored.sort(key=lambda x: -x[0])
            if scored[0][0] >= 0.5 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.15):
                return scored[0][1], round(0.6 + 0.3 * scored[0][0], 2)
            return None, scored[0][0]

    # 3) 전체 퍼지 매칭 (분류번호조차 못 읽은 경우의 최후 수단)
    scored = []
    for row in catalog:
        c = row["_norm"]
        s = 0.6 * partial_score(n, c) + 0.4 * difflib.SequenceMatcher(None, n, c).ratio()
        scored.append((s, row))
    scored.sort(key=lambda x: -x[0])
    best_s, best = scored[0]
    second_s = scored[1][0] if len(scored) > 1 else 0.0

    if best_s < 0.60:
        return None, best_s
    if best_s < 0.95 and best_s - second_s < 0.08:  # 모호성 게이트: 2위와 박빙이면 포기
        return None, best_s
    return best, best_s


def match_title(title_text: str, catalog: list):
    """이중 대조의 2번째 축: 책등 '제목' OCR을 기준표 서명과 매칭.
    라벨이 잘리거나 훼손된 책을 제목으로 복구. 모호성 게이트 동일 적용."""
    t = norm_title(title_text)
    if len(t) < 2:
        return None, 0.0

    def partial_score(a, b):
        if not a or not b:
            return 0.0
        m = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
        return m.size / min(len(a), len(b))

    scored = []
    for row in catalog:
        c = norm_title(row["title"])
        s = 0.6 * partial_score(t, c) + 0.4 * difflib.SequenceMatcher(None, t, c).ratio()
        scored.append((s, row))
    scored.sort(key=lambda x: -x[0])
    best_s, best = scored[0]
    second_s = scored[1][0] if len(scored) > 1 else 0.0
    if best_s < 0.55:
        return None, best_s
    if best_s < 0.90 and best_s - second_s < 0.10:
        return None, best_s
    return best, best_s


# ────────────────────── ⑤ LIS 오배열 판정 ──────────────────────

def lis_misplaced(keys):
    """비내림차순 LIS에 속하지 않는 인덱스 = 오배열 (최소 집합)"""
    n = len(keys)
    if n == 0:
        return set()
    length = [1] * n
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if keys[j] <= keys[i] and length[j] + 1 > length[i]:
                length[i] = length[j] + 1
                prev[i] = j
    end = max(range(n), key=lambda i: length[i])
    in_lis = set()
    while end != -1:
        in_lis.add(end)
        end = prev[end]
    return set(range(n)) - in_lis


# ────────────────────── ⑥ 오버레이 렌더링 ──────────────────────

COLORS = {
    "misplaced": (235, 60, 60),    # 🔴 오배열
    "found": (40, 200, 90),        # 🟢 검색 도서
    "unreadable": (150, 150, 150), # ⚪ 판독 불가
    "unknown": (70, 130, 230),     # 🔵 기준표 미등록
    "ok": (250, 210, 60),          # 정상(얇은 노란 테두리만)
}
STATUS_KO = {"misplaced": "오배열!", "found": "찾는 책", "unreadable": "판독불가",
             "unknown": "미등록", "ok": "정상"}


def render(pil_img: Image.Image, items, out_path: Path):
    img = pil_img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    fsize = max(18, img.width // 70)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", fsize)
    except OSError:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", fsize)

    for it in items:
        box, st = it["spine_box"], it["status"]
        c = COLORS[st]
        if st == "ok":  # 정상은 얇은 테두리만 (문제 책이 눈에 띄도록)
            d.rectangle(box, outline=c + (180,), width=3)
            continue
        d.rectangle(box, fill=c + (60,), outline=c + (255,), width=5)
        tag = f'{STATUS_KO[st]} {it.get("call_number") or ""}'.strip()
        tb = d.textbbox((0, 0), tag, font=font)
        tx, ty = box[0], max(0, box[1] - (tb[3] - tb[1]) - 14)
        d.rectangle([tx, ty, tx + tb[2] + 12, ty + tb[3] + 10], fill=c + (230,))
        d.text((tx + 6, ty + 4), tag, font=font, fill=(255, 255, 255, 255))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(out_path, quality=92)


# ────────────────────────── 메인 ──────────────────────────

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="서가 사진 경로")
    ap.add_argument("--books", default=str(HERE / "books.csv"), help="정답 기준표 CSV")
    ap.add_argument("--search", default=None, help="이용자 모드: 찾을 청구기호")
    ap.add_argument("--out", default=str(HERE / "out"), help="출력 폴더")
    ap.add_argument("--ocr", default="easyocr", choices=["easyocr", "ppocr"],
                    help="OCR 엔진: easyocr(기본) | ppocr(korean PP-OCRv5)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)

    # 정답 기준표 로드 (대림도서관 적용 시: 솔로몬/OPAC 장서데이터로 교체)
    catalog = list(csv.DictReader(open(args.books, encoding="utf-8-sig")))
    for row in catalog:
        row["_norm"] = norm(row["call_number"])
        row["_parsed"] = parse_callnum(row["call_number"])
    print(f"[기준표] {len(catalog)}권 로드")

    pil_img = Image.open(args.image).convert("RGB")
    bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # ① 탐지
    label_boxes = detect_labels_cv(bgr)
    print(f"[탐지] 라벨 후보 {len(label_boxes)}개 (CV)")
    book_boxes = detect_books_yolo(bgr)
    print(f"[탐지] 책 객체 {len(book_boxes)}개 (YOLO)")

    # ② OCR (최초 실행 시 모델 자동 다운로드)
    ocr = make_ocr(args.ocr)

    items = []
    for lb in label_boxes:
        x1, y1, x2, y2 = lb
        pad = 4
        crop = bgr[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]
        text, conf = ocr.read(crop)
        spine, by_yolo = spine_box_for(lb, book_boxes, bgr.shape[0])
        items.append({"label_box": lb, "spine_box": spine, "yolo": by_yolo,
                      "ocr_text": text, "ocr_conf": round(conf, 3)})

    # ②' 이중 대조용 제목 OCR (책등 라벨 위쪽 영역)
    for it in items:
        t_text, t_conf = ocr_spine_title(ocr, bgr, it["spine_box"], it["label_box"])
        it["title_ocr"] = t_text
        it["title_conf"] = round(t_conf, 3)

    # 라벨에 숫자도 없고 제목도 못 읽은 후보 = 라벨 아님(흰 책등 등) → 제거
    items = [it for it in items
             if re.search(r"\d", it["ocr_text"]) or len(norm_title(it["title_ocr"])) >= 2]

    # ③ 신뢰도 게이트 → ④ 이중 대조 (청구기호 + 제목)
    for it in items:
        parsed = parse_callnum(it["ocr_text"])
        row, ratio = match_catalog(it["ocr_text"], catalog)
        trow, tscore = match_title(it["title_ocr"], catalog)

        if row is not None:
            evidence = "라벨+제목" if trow is row else "라벨"
        elif trow is not None:  # 라벨 실패/모호 → 제목으로 복구
            row, ratio, evidence = trow, tscore, "제목"
        else:
            evidence = None

        if row is not None:
            it.update(status="ok", call_number=row["call_number"], title=row["title"],
                      parsed=row["_parsed"], evidence=evidence, match_ratio=round(ratio, 2))
        elif (it["ocr_conf"] < CONF_GATE) or parsed is None:
            it.update(status="unreadable", call_number=None, title=None, parsed=None, evidence=None)
        else:
            it.update(status="unknown", call_number=it["ocr_text"], title=None,
                      parsed=parsed, evidence=None)

    # ⑤ LIS 오배열 판정 (판독된 책만 참여)
    judged = [it for it in items if it["status"] in ("ok", "unknown") and it["parsed"]]
    keys = [sort_key(it["parsed"]) for it in judged]
    for idx in lis_misplaced(keys):
        judged[idx]["status"] = "misplaced"

    # 이용자 모드: 검색 도서 하이라이트
    if args.search:
        target = norm(args.search)
        for it in items:
            if it.get("call_number") and norm(it["call_number"]) == target:
                it["status"] = "found"

    # ⑥ 렌더링 + 결과 저장
    render(pil_img, items, out_dir / "annotated.jpg")
    result = {
        "image": args.image, "mode": "user_search" if args.search else "librarian",
        "search": args.search,
        "summary": {s: sum(1 for i in items if i["status"] == s) for s in COLORS},
        "books": [{k: v for k, v in it.items() if k != "parsed"} for it in items],
    }
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n──── 판정 결과 (좌→우) ────")
    for i, it in enumerate(items, 1):
        ev = it.get("evidence") or "-"
        print(f'{i:2d}. [{STATUS_KO[it["status"]]:5s}] {it.get("call_number") or it["ocr_text"]:<20s}'
              f' 근거={ev:<6s} conf={it["ocr_conf"]:.2f} {it.get("title") or ""}')
    print(f'\n[완료] {out_dir / "annotated.jpg"}\n       {out_dir / "result.json"}')


if __name__ == "__main__":
    main()
