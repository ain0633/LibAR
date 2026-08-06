# -*- coding: utf-8 -*-
"""v9 증강 3종 (멘토 제안 260730): ①빛번짐(라벨 코팅 반사) ②화각(원근 왜곡) ③필터 처리본 병행.
학습셋 빌드에서 원본 1장당 증강본 N장을 생성. --preview 로 육안 검수 시트 생성.
사용: py -3.12 aug_v9.py --preview   (libar-sample 안에서)
"""
import argparse, glob, random
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
rng = random.Random(260730)                     # 재현성

# ── ① 빛번짐: 밝은 타원 블롭 + 가로 스트릭 (라벨 비닐 반사 재현) ──
def aug_glare(img):
    h, w = img.shape[:2]
    out = img.astype(np.float32)
    mask = np.zeros((h, w), np.float32)
    kind = rng.random()
    if kind < 0.5:                              # 타원 블롭 반사
        cx, cy = rng.randint(0, w - 1), rng.randint(0, h - 1)
        ax = rng.randint(max(4, w // 6), max(6, w // 2))
        ay = rng.randint(max(2, h // 4), max(3, h))
        cv2.ellipse(mask, (cx, cy), (ax, ay), rng.randint(0, 180), 0, 360, 1.0, -1)
    else:                                       # 가로 스트릭 (형광등 반사)
        y0 = rng.randint(0, max(1, h - 1))
        th = rng.randint(max(2, h // 6), max(3, h // 2))
        cv2.rectangle(mask, (0, y0), (w, min(h, y0 + th)), 1.0, -1)
    sigma = max(4, min(h, w) // 2)
    mask = cv2.GaussianBlur(mask, (0, 0), sigma)
    if mask.max() > 0: mask /= mask.max()
    strength = rng.uniform(40, 110)             # 반사 강도 — 글자가 살아남는 선 (과하면 정답 오염)
    out = out + mask[..., None] * strength
    return np.clip(out, 0, 255).astype(np.uint8)

# ── ② 화각: 원근 왜곡 + 미세 회전 ──
def aug_perspective(img):
    h, w = img.shape[:2]
    j = rng.uniform(0.04, 0.14)                 # 모서리 이동 비율
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + np.float32([[rng.uniform(-j, j) * w, rng.uniform(-j, j) * h] for _ in range(4)])
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(img, M, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)
    ang = rng.uniform(-4, 4)
    R = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    return cv2.warpAffine(out, R, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)

# ── ③ 필터 처리본: eval_filters_ab의 대표 3종 (강한 조합은 제외 — 학습 분포 확장용) ──
_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
def _clahe_bgr(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = _clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
def _gauss_psf(sigma):
    size = int(sigma * 6) | 1
    ax = np.arange(size) - size // 2
    xx, yy = np.meshgrid(ax, ax)
    k = np.exp(-(xx ** 2 + yy ** 2) / (2 * sigma ** 2))
    return (k / k.sum()).astype(np.float64)
def _rl(img, sigma=1.0, iters=10):
    psf = _gauss_psf(sigma); psf_m = psf[::-1, ::-1]
    obs = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float64) / 255.0 + 1e-6
    est = obs.copy()
    for _ in range(iters):
        conv = cv2.filter2D(est, -1, psf, borderType=cv2.BORDER_REPLICATE) + 1e-6
        est = est * cv2.filter2D(obs / conv, -1, psf_m, borderType=cv2.BORDER_REPLICATE)
    return cv2.cvtColor((np.clip(est, 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
def aug_filter(img):
    return rng.choice([
        lambda x: cv2.resize(x, (x.shape[1] * 2, x.shape[0] * 2), interpolation=cv2.INTER_LANCZOS4),
        _clahe_bgr,
        _rl,
    ])(img)

AUGS = [('glare', aug_glare), ('persp', aug_perspective), ('filter', aug_filter)]

def expand(img):
    """학습셋 빌드용: 원본 1장 → [(태그, 이미지)] 증강본 목록 (원본 포함은 호출부에서)"""
    outs = []
    for tag, fn in AUGS:
        outs.append((tag, fn(img)))
    # 복합 1종: 화각+빛번짐 (현장에서 흔한 조합)
    outs.append(('persp+glare', aug_glare(aug_perspective(img))))
    return outs

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', action='store_true')
    a = ap.parse_args()
    if a.preview:
        from PIL import Image, ImageDraw, ImageFont
        files = sorted(glob.glob(str(HERE / 'real_rec_data_v8/crops/*.jpg')))[:4]
        font = ImageFont.truetype('malgun.ttf', 18)
        S = 3; PAD = 16
        cols = ['원본', '빛번짐', '화각', '필터', '화각+빛번짐']
        rows_img = []
        for f in files:
            img = cv2.imdecode(np.fromfile(f, np.uint8), 1)
            variants = [('원본', img)] + expand(img)
            rows_img.append(variants)
        cell_w = max(v[1].shape[1] for r in rows_img for v in r) * S + 20
        cell_h = max(v[1].shape[0] for r in rows_img for v in r) * S + 26
        W = PAD * 2 + cell_w * len(cols)
        H = PAD * 2 + 30 + cell_h * len(rows_img)
        sheet = Image.new('RGB', (W, H), (20, 24, 20))
        d = ImageDraw.Draw(sheet)
        for ci, c in enumerate(cols):
            d.text((PAD + ci * cell_w, PAD), c, fill=(230, 240, 230), font=font)
        for ri, variants in enumerate(rows_img):
            for ci, (tag, im) in enumerate(variants):
                rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
                p = Image.fromarray(rgb)
                p = p.resize((p.width * S, p.height * S), Image.NEAREST)
                sheet.paste(p, (PAD + ci * cell_w, PAD + 30 + ri * cell_h))
        out = HERE.parent / '원고사진후보' / 'v9증강_검수시트.png'
        sheet.save(str(out))
        print('preview saved:', out)
