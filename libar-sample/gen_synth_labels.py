# -*- coding: utf-8 -*-
"""합성 저해상 청구기호 라인 생성기 — OCR 인식기(rec) 파인튜닝용.
  원리: 실제 라벨의 텍스트 줄(분류 '843' / 저자기호 '바66ㄷ' / 권차 'v.2')을
        라벨 서식으로 렌더링 → 대림 광각 수준으로 열화(축소→블러→JPEG→노이즈)
        → 추론 파이프라인과 동일하게 h=48로 업스케일 → (이미지, 정답) 쌍
  출력: synth_rec/{train,val}/images/*.jpg + rec_gt_{train,val}.txt (PaddleOCR SimpleDataSet 형식)
"""
import sys, random, io, csv, zipfile
import numpy as np, cv2
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
OUT = HERE/"synth_rec"
random.seed(42); np.random.seed(42)

FONTS = ["C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf",
         "C:/Windows/Fonts/gulim.ttc", "C:/Windows/Fonts/batang.ttc"]

# ── 텍스트 소스: 실제 카탈로그 + 무작위 변형 ──
CHO = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허고노도로모보소오조초코토포호구누두루무부수우주추쿠투푸후그느드르므브스으즈츠크트프흐기니디리미비시이지치키티피히"
JAMO = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"
texts = set()
for r in csv.DictReader(open(HERE/"daelim_catalog.csv", encoding="utf-8-sig")):
    parts = r["call_number"].strip().split("-")
    for p in parts:
        p = p.strip()
        if p: texts.add(p)
real = list(texts)
def rand_author():
    return random.choice(CHO) + str(random.randint(1, 999)) + (random.choice(JAMO) if random.random() < 0.8 else "")
def rand_class():
    c = str(random.randint(0, 999))
    if random.random() < 0.15: c += "." + str(random.randint(1, 99))
    if random.random() < 0.08: c = random.choice(["양", "큰"]) + c
    return c
def rand_vol():
    return random.choice([f"v.{random.randint(1,20)}", str(random.randint(1,99)), f"c.{random.randint(2,3)}"])

pool = real * 3
pool += [rand_author() for _ in range(2500)]
pool += [rand_class() for _ in range(1500)]
pool += [rand_vol() for _ in range(500)]
random.shuffle(pool)
print(f"[텍스트] 실제 {len(real)} · 총 샘플 {len(pool)}")

def render(text):
    font = ImageFont.truetype(random.choice(FONTS), 44)
    pad = random.randint(4, 14)
    dummy = Image.new("RGB", (10, 10)); d = ImageDraw.Draw(dummy)
    bb = d.textbbox((0, 0), text, font=font)
    w, h = bb[2]-bb[0]+pad*2, bb[3]-bb[1]+pad*2
    # 스티커 배경: 흰~크림 + 약한 얼룩
    bg = random.randint(225, 252)
    im = Image.new("RGB", (w, h), (bg, bg, max(200, bg-random.randint(0, 12))))
    d = ImageDraw.Draw(im)
    ink = random.randint(10, 70)
    d.text((pad-bb[0], pad-bb[1]), text, font=font, fill=(ink, ink, ink))
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

def degrade(img):
    h0 = img.shape[0]
    # 실제 관측 스펙트럼: 광각(줄높이 7~16px) 위주 + 중간(17~30px)
    th = random.choice([random.randint(7, 16)]*3 + [random.randint(17, 30)])
    s = th/h0
    img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    if random.random() < 0.8:
        img = cv2.GaussianBlur(img, (3, 3), random.uniform(0.3, 1.1))
    if random.random() < 0.5:                       # 원근 기울임 약간
        h, w = img.shape[:2]; dx = random.uniform(-0.06, 0.06)*w
        M = np.float32([[1, dx/max(1,h), 0], [0, 1, 0]])
        img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    # JPEG 열화 (카톡 압축 모사)
    q = random.randint(28, 75)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if random.random() < 0.4:
        img = img.astype(np.int16) + np.random.normal(0, random.uniform(2, 7), img.shape).astype(np.int16)
        img = np.clip(img, 0, 255).astype(np.uint8)
    # 추론과 동일: h=48 업스케일
    h = img.shape[0]
    img = cv2.resize(img, None, fx=48/h, fy=48/h, interpolation=cv2.INTER_LANCZOS4)
    return img

import shutil
if OUT.exists(): shutil.rmtree(OUT)
for sp in ["train", "val"]: (OUT/sp/"images").mkdir(parents=True)
gt = {"train": [], "val": []}
for i, text in enumerate(pool):
    sp = "val" if i % 12 == 0 else "train"
    img = degrade(render(text))
    name = f"{i:05d}.jpg"
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    (OUT/sp/"images"/name).write_bytes(buf.tobytes())
    gt[sp].append(f"images/{name}\t{text}")
for sp in ["train", "val"]:
    (OUT/sp/f"rec_gt_{sp}.txt").write_text("\n".join(gt[sp]), encoding="utf-8")
print(f"[생성] train {len(gt['train'])} · val {len(gt['val'])}")

with zipfile.ZipFile(HERE/"synth_rec.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in OUT.rglob("*"):
        if p.is_file(): z.write(p, p.relative_to(HERE))
print(f"[완료] synth_rec.zip")
