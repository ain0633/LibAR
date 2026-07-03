# -*- coding: utf-8 -*-
"""청구기호 라벨 인쇄 시트 생성기
books.csv 를 읽어 A4(300dpi) 라벨 시트 PNG를 만든다.
→ 100% 배율로 인쇄 → 오려서 각 책의 책등 하단에 부착

사용법: python make_labels.py
출력  : labels_print.png (라벨 1장 = 약 34 x 25 mm)
"""
import csv
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
FONT = "C:/Windows/Fonts/malgunbd.ttf"  # 맑은 고딕 볼드 (없으면 malgun.ttf)

# A4 @300dpi
PAGE_W, PAGE_H = 2480, 3508
LABEL_W, LABEL_H = 400, 300   # ≈ 34 x 25 mm
COLS, GAP = 5, 60


def split_callnum(cn: str):
    """'813.7-김94ㅎ-v.2' → ['813.7', '김94ㅎ', 'v.2'] (도서관 라벨 3단 형식)"""
    m = re.match(r"(\d{1,3}(?:\.\d+)?)[\s\-]*([가-힣ㄱ-ㅎㅏ-ㅣ][가-힣ㄱ-ㅎㅏ-ㅣ0-9]*)?[\s\-]*([vV]\.?\d+)?", cn.strip())
    if not m:
        return [cn]
    return [p for p in m.groups() if p]


def main():
    try:
        font_big = ImageFont.truetype(FONT, 72)
        font_mid = ImageFont.truetype(FONT, 60)
    except OSError:
        font_big = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 72)
        font_mid = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 60)

    rows = list(csv.DictReader(open(HERE / "books.csv", encoding="utf-8-sig")))
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(page)

    x0, y0 = 120, 120
    for i, row in enumerate(rows):
        col, r = i % COLS, i // COLS
        x = x0 + col * (LABEL_W + GAP)
        y = y0 + r * (LABEL_H + GAP)
        # 절취선 테두리
        d.rectangle([x, y, x + LABEL_W, y + LABEL_H], outline=(120, 120, 120), width=3)
        lines = split_callnum(row["call_number"])
        fonts = [font_big, font_big, font_mid]
        total_h = sum(fonts[min(j, 2)].getbbox(t)[3] for j, t in enumerate(lines)) + 10 * (len(lines) - 1)
        ty = y + (LABEL_H - total_h) // 2
        for j, t in enumerate(lines):
            f = fonts[min(j, 2)]
            bb = d.textbbox((0, 0), t, font=f)
            d.text((x + (LABEL_W - (bb[2] - bb[0])) // 2, ty), t, font=f, fill="black")
            ty += bb[3] + 10
        # 어떤 책 라벨인지 작은 안내(절취선 밖, 부착 시 잘려나감)
        d.text((x, y + LABEL_H + 6), f"→ {row['title'][:14]}", font=font_mid.font_variant(size=28), fill=(150, 150, 150))

    out = HERE / "labels_print.png"
    page.save(out, dpi=(300, 300))
    print(f"[OK] {out} 생성 — 100% 배율로 인쇄해 오려서 책등 하단에 부착하세요. ({len(rows)}권)")


if __name__ == "__main__":
    main()
