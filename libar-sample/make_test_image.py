# -*- coding: utf-8 -*-
"""가상 서가 이미지 생성기 (실물 책 없이 파이프라인 즉시 검증용)
books.csv 의 책들을 청구기호 순으로 꽂되, 2권을 일부러 맞바꿔 오배열을 심는다.

사용법: python make_test_image.py [--damage N]
        --damage N : 왼쪽에서 N번째(1부터) 책의 라벨을 백지로 훼손
                     → 제목 매칭(이중 대조) 복구 검증용
출력  : test_shelf.jpg  (+ 콘솔에 '심어둔 오배열' 정답 출력)
"""
import argparse
import csv
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
SWAP = (2, 7)  # 이 두 자리(0부터)의 책을 맞바꿔 오배열 생성

PALETTE = [(96, 60, 20), (30, 70, 120), (120, 30, 40), (25, 90, 60), (70, 45, 110),
           (140, 90, 25), (40, 40, 45), (0, 100, 110), (110, 60, 80), (60, 80, 30)]


def callnum_key(cn: str):
    m = re.match(r"(\d{1,3}(?:\.\d+)?)[\s\-]*([가-힣ㄱ-ㅎㅏ-ㅣ][가-힣ㄱ-ㅎㅏ-ㅣ0-9]*)?", cn)
    return (float(m.group(1)), m.group(2) or "")


def split3(cn: str):
    m = re.match(r"(\d{1,3}(?:\.\d+)?)[\s\-]*([가-힣ㄱ-ㅎㅏ-ㅣ][가-힣ㄱ-ㅎㅏ-ㅣ0-9]*)?[\s\-]*([vV]\.?\d+)?", cn)
    return [p for p in m.groups() if p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--damage", type=int, default=0,
                    help="왼쪽에서 N번째(1부터) 라벨을 백지로 훼손")
    args = ap.parse_args()

    rng = random.Random(42)
    rows = list(csv.DictReader(open(HERE / "books.csv", encoding="utf-8-sig")))
    rows.sort(key=lambda r: callnum_key(r["call_number"]))

    order = list(range(len(rows)))
    a, b = SWAP
    order[a], order[b] = order[b], order[a]
    shelf = [rows[i] for i in order]

    W, H = 1800, 1000
    img = Image.new("RGB", (W, H), (232, 226, 214))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 880, W, 920], fill=(150, 120, 90))  # 선반

    font_t = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 26)
    font_l1 = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 30)
    font_l2 = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 28)

    x = 80
    for i, row in enumerate(shelf):
        w = rng.randint(105, 150)
        h = rng.randint(660, 800)
        y1, y2 = 880 - h, 880
        color = PALETTE[i % len(PALETTE)]
        d.rectangle([x, y1, x + w, y2], fill=color, outline=(20, 20, 20), width=2)

        # 책등 제목(세로 텍스트 흉내 — 회전)
        title = row["title"][:10]
        timg = Image.new("RGBA", (400, 40), (0, 0, 0, 0))
        ImageDraw.Draw(timg).text((0, 0), title, font=font_t, fill=(240, 240, 235))
        timg = timg.rotate(-90, expand=True)
        img.paste(timg, (x + (w - timg.width) // 2, y1 + 30), timg)

        # 청구기호 라벨 (책등 하단 흰 스티커)
        lw, lh = w - 18, 108
        lx, ly = x + 9, y2 - 128
        d.rectangle([lx, ly, lx + lw, ly + lh], fill="white", outline=(90, 90, 90), width=2)
        if i + 1 != args.damage:  # --damage 지정 책은 백지 라벨(훼손 시뮬레이션)
            ty = ly + 8
            for j, line in enumerate(split3(row["call_number"])):
                f = font_l1 if j == 0 else font_l2
                bb = d.textbbox((0, 0), line, font=f)
                d.text((lx + (lw - (bb[2] - bb[0])) // 2, ty), line, font=f, fill="black")
                ty += bb[3] + 4
        x += w + 10

    out = HERE / "test_shelf.jpg"
    img.save(out, quality=93)
    print(f"[OK] {out} 생성")
    print(f"[정답] 오배열로 심어둔 책: 왼쪽에서 {a+1}번째 ↔ {b+1}번째")
    print(f"  {a+1}번째 자리 ← {shelf[a]['call_number']} ({shelf[a]['title']})")
    print(f"  {b+1}번째 자리 ← {shelf[b]['call_number']} ({shelf[b]['title']})")
    if args.damage:
        i = args.damage - 1
        print(f"[훼손] {args.damage}번째 라벨 백지 처리: {shelf[i]['call_number']} ({shelf[i]['title']})"
              f" → 제목 매칭으로 복구돼야 함")


if __name__ == "__main__":
    main()
