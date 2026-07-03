# -*- coding: utf-8 -*-
"""OCR 엔진 비교: EasyOCR vs korean PP-OCRv5
같은 서가 이미지의 라벨 크롭들을 두 엔진으로 읽고, 기준표 매칭 성공률·신뢰도를 비교.
→ 원고 "OCR 정확도 비교" 실측 표 자료 생성.

사용법: python compare_ocr.py test_shelf.jpg
출력  : 콘솔 비교표 + out/ocr_compare.csv
"""
import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import pipeline as P

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent


def run_engine(adapter, label_boxes, bgr, catalog):
    rows = []
    for lb in label_boxes:
        x1, y1, x2, y2 = lb
        crop = bgr[max(0, y1 - 4):y2 + 4, max(0, x1 - 4):x2 + 4]
        text, conf = adapter.read(crop)
        row, score = P.match_catalog(text, catalog)
        rows.append({"ocr": text, "conf": conf,
                     "matched": row["call_number"] if row else None})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--books", default=str(HERE / "books.csv"))
    args = ap.parse_args()

    catalog = list(csv.DictReader(open(args.books, encoding="utf-8-sig")))
    for r in catalog:
        r["_norm"] = P.norm(r["call_number"])
        r["_parsed"] = P.parse_callnum(r["call_number"])

    bgr = cv2.cvtColor(np.array(Image.open(args.image).convert("RGB")), cv2.COLOR_RGB2BGR)
    label_boxes = P.detect_labels_cv(bgr)
    print(f"[탐지] 라벨 후보 {len(label_boxes)}개\n")

    engines = {}
    for key in ("easyocr", "ppocr"):
        try:
            engines[key] = P.make_ocr(key)
        except Exception as e:
            print(f"[{key}] 사용 불가: {e}")

    results = {k: run_engine(a, label_boxes, bgr, catalog) for k, a in engines.items()}

    print("\n" + "=" * 78)
    hdr = f'{"#":>2} | ' + " | ".join(f'{k:^32}' for k in results)
    print(hdr)
    print("-" * 78)
    n = len(label_boxes)
    tallies = {k: {"conf": 0.0, "match": 0} for k in results}
    for i in range(n):
        cells = []
        for k in results:
            r = results[k][i]
            ok = "O" if r["matched"] else "X"
            cells.append(f'{ok} {str(r["matched"] or r["ocr"])[:20]:<20} c={r["conf"]:.2f}')
            tallies[k]["conf"] += r["conf"]
            tallies[k]["match"] += 1 if r["matched"] else 0
        print(f'{i+1:>2} | ' + " | ".join(f'{c:^32}' for c in cells))

    print("-" * 78)
    print("[요약]")
    for k in results:
        t = tallies[k]
        print(f"  {k:10s}: 매칭 성공 {t['match']}/{n} ({100*t['match']/n:.0f}%), "
              f"평균 신뢰도 {t['conf']/n:.3f}")

    out = HERE / "out"; out.mkdir(exist_ok=True)
    with open(out / "ocr_compare.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["label_idx"] + [f"{k}_ocr" for k in results]
                   + [f"{k}_conf" for k in results] + [f"{k}_matched" for k in results])
        for i in range(n):
            w.writerow([i + 1]
                       + [results[k][i]["ocr"] for k in results]
                       + [f'{results[k][i]["conf"]:.3f}' for k in results]
                       + [results[k][i]["matched"] or "" for k in results])
    print(f"\n[저장] {out / 'ocr_compare.csv'}")


if __name__ == "__main__":
    main()
