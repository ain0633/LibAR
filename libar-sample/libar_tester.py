# -*- coding: utf-8 -*-
"""LibAR 통합 샘플 테스터 — 장서데이터(청구기호) 기반
────────────────────────────────────────────────────────────
장서데이터 + YOLO(책등 이미지) + OCR(청구기호 라벨) 이중인식
  → 오배열 판정 + 도서 검색

★ 식별 기준은 좌표가 아니라 '청구기호'다. 좌표(x)는 화면에 그릴 때만 쓴다.
★ 장서데이터(--catalog)만 대림 솔로몬 export로 교체하면 그대로 완성된다.

파이프라인:
  1. YOLO best.pt        → 책등 박스        (이미지 인식)
  2. 라벨 OCR            → 청구기호 텍스트   (라벨 인식)   ← 이중인식
  3. match_catalog(청구기호, 장서데이터)
        → 장서에 있는 책만 확정. 장서에 없는 판독값은 '미등록'(노이즈)으로 폐기
  4. 물리적 배열(좌→우) vs 장서데이터 KDC 정렬 → LIS 오배열 판정
  5. --search "청구기호|제목" → 장서에서 찾아 서가에서 하이라이트
  6. 오버레이: 초록=정상 · 빨강=오배열 · 회색=미등록 · 청록=검색도서

사용:
  python libar_tester.py shelf_4558.jpg --catalog books_4558.csv
  python libar_tester.py shelf_4558.jpg --catalog books_4558.csv --search "408-뉴88-55"
  python libar_tester.py shelf_4558.jpg --catalog books_4558.csv --search "기하학"
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import pipeline as P

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

# 라벨 스티커 세로 위치(서가 사진 기준 비율) — 렌더/밴드에만 사용
BAND_Y0, BAND_Y1 = 0.695, 0.79


# ───────────── 장서데이터 (청구기호 인터페이스) ─────────────

def load_catalog(path):
    """장서데이터 로드. 파일은 청구기호 KDC 정렬 순서로 저장돼 있다고 가정
    (대림 솔로몬 export도 청구기호로 정렬해 넣으면 됨).
    각 행의 _order = 올바른 배열 위치. 이 순서가 오배열 판정의 기준."""
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    for i, r in enumerate(rows):
        r["_norm"] = P.norm(r["call_number"])
        r["_order"] = i
    return rows


def match_reading(call_number, catalog):
    """판독한 청구기호를 장서데이터와 대조. 정확 일치 우선 → 장서에 있는 책만 확정.
    장서에 없으면 None(미등록/노이즈). ★ 이것이 노이즈를 걸러내는 장서데이터의 역할."""
    n = P.norm(call_number)
    for row in catalog:
        if row["_norm"] == n:
            return row
    return None


# ───────────── 라벨 판독 (캐시 우선, 없으면 밴드-타일 OCR) ─────────────

def read_labels(image_path, cache_path, refresh=False):
    """서가에서 청구기호 라벨을 읽어 [{x, call_number, conf}] 반환.
    ★ 반환 식별자는 'call_number'(청구기호). x는 렌더 위치용."""
    if cache_path.exists() and not refresh:
        raw = json.load(open(cache_path, encoding="utf-8"))
        print(f"[OCR] 캐시 사용 ({cache_path.name}, {len(raw)}건)")
        return raw

    print("[OCR] 밴드-타일 PP-OCR 실행 (최초 1회, 수 분 소요)…")
    import os
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    from paddleocr import PaddleOCR
    import re
    im = Image.open(image_path).convert("RGB"); W, H = im.size
    band = im.crop((0, int(H * BAND_Y0), W, int(H * BAND_Y1))); bw, bh = band.size
    ocr = PaddleOCR(lang="korean", use_textline_orientation=True, enable_mkldnn=False)
    ntile, ov, step = 3, int(bw * 0.05), bw // 3
    toks = []
    for i in range(ntile):
        x0 = max(0, i * step - ov); x1 = min(bw, (i + 1) * step + ov)
        tile = band.crop((x0, 0, x1, bh))
        tile = tile.resize((tile.width * 2, tile.height * 2), Image.LANCZOS)
        r0 = ocr.predict(cv2.cvtColor(np.array(tile), cv2.COLOR_RGB2BGR))[0]
        for t, s, poly in zip(r0.get("rec_texts", []), r0.get("rec_scores", []),
                              r0.get("rec_polys", [])):
            xc = x0 + (sum(p[0] for p in poly) / len(poly)) / 2
            m = re.fullmatch(r"\d{1,3}", t.strip())
            if m and int(t) not in (408, 40, 80, 0, 8, 10, 88, 884, 108, 100):
                # 이 서가는 408 뉴88 시리즈 → 청구기호 재구성 (실서비스는 전체 청구기호 OCR)
                toks.append({"x": int(xc), "call_number": f"408-뉴88-{int(t)}",
                             "conf": round(float(s), 3)})
    toks.sort(key=lambda d: d["x"])
    json.dump(toks, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OCR] {len(toks)}건 판독 → 캐시 저장")
    return toks


# ───────────── YOLO 책등 (이미지 인식) ─────────────

def detect_spines(bgr):
    boxes = P.detect_books_yolo(bgr)
    H = bgr.shape[0]
    # 메인 서가 라벨 띠에 걸치는 책등만 (상/하단 서가 제외)
    band_mid = H * (BAND_Y0 + BAND_Y1) / 2
    main = [b for b in boxes if b[1] <= band_mid <= b[3]]
    return boxes, main


def spine_for(x, spines):
    for b in spines:
        if b[0] <= x <= b[2]:
            return b
    return None


# ───────────── 핵심: 장서 대조 + 이중인식 + 판정 ─────────────

def build_books(readings, catalog, spines, img_h):
    """각 라벨 판독을 장서데이터와 대조. 장서에 없으면 미등록(노이즈).
    ★ 배열 순서 판정은 장서데이터의 정렬 순서(_order)를 기준으로 한다 (청구기호 기반)."""
    books = []
    for r in readings:
        row = match_reading(r["call_number"], catalog)     # ★ 청구기호로 장서 대조
        spine = spine_for(r["x"], spines)                  # 이미지(책등)와 연결 → 이중인식
        books.append({
            "x": r["x"], "conf": r["conf"], "ocr": r["call_number"],
            "call_number": row["call_number"] if row else None,
            "title": row["title"] if row else None,
            "order": row["_order"] if row else None,
            "spine": spine, "has_spine": spine is not None,
        })
    books.sort(key=lambda b: b["x"])

    # 겹친 타일에서 나온 같은 청구기호 중복 제거 (같은 책이면 신뢰도 높은 쪽만)
    dedup = []
    for b in books:
        if dedup and b["call_number"] and b["call_number"] == dedup[-1]["call_number"] \
                and abs(b["x"] - dedup[-1]["x"]) < 130:
            if b["conf"] > dedup[-1]["conf"]:
                dedup[-1] = b
            continue
        dedup.append(b)
    books = dedup

    for b in books:
        if b["call_number"] is None:
            b["status"] = "unknown"                        # 장서에 없음 = 노이즈 (회색)
    matched = [b for b in books if b["call_number"]]

    # 하향 스파이크(양옆보다 순서가 훨씬 앞) = 오독 → 미등록 처리
    for i, b in enumerate(matched):
        prev = matched[i - 1]["order"] if i > 0 else None
        nxt = matched[i + 1]["order"] if i < len(matched) - 1 else None
        if prev is not None and nxt is not None and prev <= nxt \
                and b["order"] < prev - 1 and b["order"] < nxt - 1:
            b["status"] = "unknown"
    clean = [b for b in matched if b.get("status") != "unknown"]

    # LIS: 장서 정렬 순서 위배 = 오배열
    mis = P.lis_misplaced([b["order"] for b in clean])
    for i, b in enumerate(clean):
        b["status"] = "misplaced" if i in mis else "ok"
    return books


# ───────────── 렌더 ─────────────

COLORS = {"ok": (40, 190, 90), "misplaced": (235, 60, 60),
          "unknown": (150, 150, 150), "found": (0, 200, 220)}
KO = {"ok": "정상", "misplaced": "오배열!", "unknown": "미등록", "found": "찾는 책"}


def render(im, books, img_h, banner, out_path):
    y0, y1 = int(img_h * BAND_Y0), int(img_h * BAND_Y1)
    vis = im.copy(); d = ImageDraw.Draw(vis, "RGBA")
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 46)
    fsm = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 30)
    for b in books:
        st = b["status"]; c = COLORS[st]
        if b["has_spine"]:
            x0, sy0, x1, sy1 = b["spine"]
        else:
            x0, sy0, x1, sy1 = b["x"] - 42, y0, b["x"] + 42, y1
        w = 8 if st in ("misplaced", "found") else 5
        d.rectangle([x0, sy0, x1, sy1], outline=c + (255,), width=w)
        if st in ("misplaced", "found"):
            d.rectangle([x0, sy0, x1, sy1], fill=c + (70,))
        # 태그: 권차(짧게)
        tag = b["call_number"].split("-")[-1] if b["call_number"] else "?"
        d.rectangle([x0, y0 - 56, x0 + 78, y0 - 6], fill=c + (235,))
        d.text((x0 + 6, y0 - 54), tag, font=fsm, fill=(255, 255, 255, 255))
    d.rectangle([0, 0, im.width, 150], fill=(20, 30, 60, 225))
    d.text((40, 30), banner, font=font, fill=(255, 255, 255, 255))
    vis.save(out_path, quality=90)


# ───────────── 메인 ─────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--catalog", default=str(HERE / "books_4558.csv"))
    ap.add_argument("--ocr-cache", default=None, help="라벨 판독 캐시 json")
    ap.add_argument("--refresh-ocr", action="store_true")
    ap.add_argument("--search", default=None, help="청구기호 또는 제목")
    ap.add_argument("--out", default=str(HERE / "out_tester"))
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(exist_ok=True)
    img_path = Path(args.image)
    cache = Path(args.ocr_cache) if args.ocr_cache else img_path.with_suffix(".labels.json")

    catalog = load_catalog(args.catalog)
    print(f"[장서데이터] {len(catalog)}권 ({Path(args.catalog).name}) ← 대림 데이터로 교체 지점")

    im = Image.open(img_path).convert("RGB")
    bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

    all_spines, main_spines = detect_spines(bgr)
    print(f"[YOLO] 책등 {len(all_spines)}개 (메인 서가 {len(main_spines)}개)")

    readings = read_labels(img_path, cache, refresh=args.refresh_ocr)
    books = build_books(readings, catalog, main_spines, bgr.shape[0])

    # 검색: 청구기호(정규화 부분일치) 또는 제목(부분일치)로 장서에서 찾아 서가에서 표시
    found = None
    if args.search:
        q = P.norm(args.search)
        for b in books:
            if not b["call_number"]:
                continue
            if q in P.norm(b["call_number"]) or (b["title"] and q in P.norm(b["title"])):
                b["status"] = "found"; found = b; break

    # 집계
    cnt = {k: sum(1 for b in books if b["status"] == k) for k in COLORS}
    dual = sum(1 for b in books if b["has_spine"] and b["call_number"])
    if args.search:
        banner = (f"LibAR 도서 검색  |  '{args.search}'  →  "
                  + (f"찾음: {found['call_number']} ({found['title']})" if found else "서가에 없음"))
    else:
        banner = (f"LibAR 서가 점검  |  장서 대조 {cnt['ok']+cnt['misplaced']}권 "
                  f"(정상 {cnt['ok']} · 오배열 {cnt['misplaced']}) · 미등록 {cnt['unknown']}")

    tag = "search" if args.search else "inspect"
    render(im, books, bgr.shape[0], banner, out / f"{img_path.stem}_{tag}.jpg")

    # 결과 출력 (청구기호 기준)
    print(f"\n──── 결과 (좌→우, 청구기호 기준) ────")
    for b in books:
        cn = b["call_number"] or f'({b["ocr"]} 미등록)'
        dm = "책등✓" if b["has_spine"] else "책등✗"
        print(f'  [{KO[b["status"]]:5s}] {cn:14s} {dm} conf={b["conf"]:.2f}'
              f'  {b["title"] or ""}')
    print(f'\n[요약] 이중인식(책등+라벨) {dual}권 · 정상 {cnt["ok"]} · 오배열 {cnt["misplaced"]}'
          f' · 미등록(장서에 없음) {cnt["unknown"]}')
    print(f'[완료] {out / f"{img_path.stem}_{tag}.jpg"}')

    json.dump({"banner": banner,
               "books": [{k: v for k, v in b.items() if k not in ("parsed", "spine")}
                         for b in books]},
              open(out / f"{img_path.stem}_{tag}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
