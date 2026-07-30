# -*- coding: utf-8 -*-
"""고전 신호처리 필터 A/B (멘토 제안 260730): 블러가 병목이라면 디컨볼루션·대비 강화로 회복되는지.
Lanczos ×4 / CLAHE / Richardson-Lucy 디컨볼루션을 배포 rec(v4 onnx)에 전처리로 걸어 채점.
킬 기준(사전 명시): low 또는 human76에서 +3줄 이상 상승 시에만 채택 검토, 아니면 기각 기록.
사용: .venv 파이썬으로 libar-sample 안에서 실행 (한글 경로 함정)
"""
import io, json, unicodedata
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent

def nfc(s): return unicodedata.normalize("NFC", str(s)).replace(" ", "")

# ── val 셋: 공식 채점과 동일 (eval_v8_ab.py와 같은 로드) ──
sets = {"close": [], "low": [], "human76": []}
for l in io.open(HERE/"real_rec_data_v3/meta_val.txt", encoding="utf-8").read().splitlines():
    f, gt, g = l.split("\t")
    sets["close" if g == "close" else "low"].append(("real_rec_data_v3/"+f, gt))
for l in io.open(HERE/"real_rec_data_human/meta_human_val.txt", encoding="utf-8").read().splitlines():
    f, gt, g = l.split("\t")
    sets["human76"].append(("real_rec_data_human/"+f, gt))

imgs = {}
for g, items in sets.items():
    for f, gt in items:
        imgs[f] = cv2.imdecode(np.fromfile(str(HERE/f), np.uint8), 1)

# ── 배포 rec (v4 onnx) — eval_v8_ab.py와 동일 하니스 ──
import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
rsess = ort.InferenceSession(str(HERE/"webdemo/rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
rin = rsess.get_inputs()[0].name
chars = json.load(io.open(HERE/"webdemo/rec_charset.json", encoding="utf-8"))
def rec_v4(img):
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

# ── 전처리 변형들 ──
def f_raw(img): return img

def f_lanczos(img):
    return cv2.resize(img, (img.shape[1]*4, img.shape[0]*4), interpolation=cv2.INTER_LANCZOS4)

_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
def f_clahe_lanczos(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = _clahe.apply(lab[:, :, 0])
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return f_lanczos(out)

def _gauss_psf(sigma, size=None):
    if size is None: size = int(sigma*6) | 1
    ax = np.arange(size) - size//2
    xx, yy = np.meshgrid(ax, ax)
    k = np.exp(-(xx**2 + yy**2)/(2*sigma**2))
    return (k / k.sum()).astype(np.float64)

def _rl(img, sigma, iters):
    """Richardson-Lucy 디컨볼루션 (가우시안 PSF 가정) — cv2.filter2D 직접 구현"""
    psf = _gauss_psf(sigma)
    psf_m = psf[::-1, ::-1]
    obs = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float64)/255.0 + 1e-6
    est = obs.copy()
    for _ in range(iters):
        conv = cv2.filter2D(est, -1, psf, borderType=cv2.BORDER_REPLICATE) + 1e-6
        est = est * cv2.filter2D(obs/conv, -1, psf_m, borderType=cv2.BORDER_REPLICATE)
    de = (np.clip(est, 0, 1)*255).astype(np.uint8)
    return cv2.cvtColor(de, cv2.COLOR_GRAY2BGR)

def f_rl10(img):  return f_lanczos(_rl(img, 1.0, 10))
def f_rl30(img):  return f_lanczos(_rl(img, 1.5, 30))
def f_rl_clahe(img):
    out = _rl(img, 1.0, 10)
    lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = _clahe.apply(lab[:, :, 0])
    return f_lanczos(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR))

VARIANTS = [("raw(기준)", f_raw), ("Lanczos×4", f_lanczos), ("CLAHE+Lz", f_clahe_lanczos),
            ("RL σ1 i10+Lz", f_rl10), ("RL σ1.5 i30+Lz", f_rl30), ("RL+CLAHE+Lz", f_rl_clahe)]

print(f"{'변형':16s} " + "  ".join(f"{g:>10s}" for g in sets))
base = {}
for name, fn in VARIANTS:
    row = []
    for g, items in sets.items():
        ok = sum(1 for f, gt in items if rec_v4(fn(imgs[f])) == nfc(gt))
        row.append((ok, len(items)))
    if name.startswith("raw"): base = {g: r[0] for g, r in zip(sets, row)}
    marks = "  ".join(f"{ok:3d}/{n:<3d}{'▲' if ok > base[g] else '▼' if ok < base[g] else '='}"
                      for g, (ok, n) in zip(sets, row))
    print(f"{name:16s} {marks}")

print("킬 기준: low/human76 +3 이상 상승 시 채택 검토, 미달이면 기각 기록")
# 실측 결과(260730): 6변형 전부 기준 이하 — Lanczos 19/38, CLAHE+Lz 18/26, RL(1.0,10) 19/37,
# RL(1.5,30) 16/31, RL+CLAHE 14/24 vs 기준 20/38. 해석: ①필터는 새 획 정보를 만들지 못하고
# ②배포 rec(v4)가 열화 도메인 자체를 학습한 모델이라 전처리가 입력 분포만 흔들어 역효과.
# SR(FSRCNN, 260707)에 이어 고전 신호처리도 기각 — "정보 소실 대역" 진단 유지.
