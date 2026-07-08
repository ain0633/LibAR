# -*- coding: utf-8 -*-
"""ONNX rec 모델 검증: paddle 원본 rec vs onnxruntime rec을 동일 크롭에서 비교."""
import io, json, sys, time
import numpy as np
import cv2
import yaml

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# libar-sample 폴더에서 실행 — paddle C++가 한글 절대경로를 못 열어 상대경로 필수
ONNX = "../korean_lowres_rec.onnx"
REC_DIR = "korean_lowres_rec_infer"
PHOTO = "../대림데이터/KakaoTalk_20260707_184409459.jpg"

# --- 문자 사전 (blank + dict + space) ---
pp = yaml.safe_load(open(REC_DIR + r"\inference.yml", encoding="utf-8"))["PostProcess"]
CHARS = ["blank"] + list(pp["character_dict"]) + [" "]

def ctc_decode(logits):
    idx = logits.argmax(axis=-1)
    prob = logits.max(axis=-1)
    txt, confs, prev = [], [], 0
    for i, p in zip(idx, prob):
        if i != 0 and i != prev:
            txt.append(CHARS[i] if i < len(CHARS) else "?")
            confs.append(p)
        prev = i
    return "".join(txt), (float(np.mean(confs)) if confs else 0.0)

def rec_preprocess(img, h=48, max_w=1200):
    ratio = img.shape[1] / img.shape[0]
    w = min(max_w, max(16, int(round(h * ratio / 8)) * 8))
    im = cv2.resize(img, (w, h)).astype("float32")
    im = (im / 255.0 - 0.5) / 0.5
    return im.transpose(2, 0, 1)[None]

# --- 1) paddle 전체 파이프라인으로 라벨 영역 det + rec (기준값) ---
from paddleocr import PaddleOCR
ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_server_det",
    text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
    text_recognition_model_dir=REC_DIR,
    use_doc_orientation_classify=False, use_doc_unwarping=False,
    use_textline_orientation=False, lang="korean", enable_mkldnn=False)

bgr = cv2.imdecode(np.fromfile(PHOTO, dtype=np.uint8), cv2.IMREAD_COLOR)
H = bgr.shape[0]
strip = bgr[int(H * 0.55):, :]  # 하단 라벨 영역
if strip.shape[1] > 2200:
    strip = cv2.resize(strip, (2200, int(strip.shape[0] * 2200 / strip.shape[1])))

res = ocr.predict(strip)[0]
texts = res["rec_texts"]; polys = res["rec_polys"]; scores = res["rec_scores"]

# --- 2) 동일 크롭을 ONNX로 인식 ---
import onnxruntime as ort
sess = ort.InferenceSession(ONNX, providers=["CPUExecutionProvider"])

import re
LABELPAT = re.compile(r"^\d{3}(\.\d+)?$|^[가-힣][0-9]{1,3}[가-힣ㄱ-ㅎ]?$|^\d$")

pairs = []; t_onnx = 0.0
print(f"{'paddle':<24}{'onnx':<24}일치")
for txt, poly, sc in zip(texts, polys, scores):
    p = np.array(poly).astype(int)
    x0, y0 = p[:, 0].min(), p[:, 1].min()
    x1, y1 = p[:, 0].max(), p[:, 1].max()
    if x1 - x0 < 8 or y1 - y0 < 8:
        continue
    crop = strip[max(0, y0):y1, max(0, x0):x1]
    inp = rec_preprocess(crop)
    t0 = time.time()
    out = sess.run(None, {"x": inp})[0][0]
    t_onnx += time.time() - t0
    otxt, oconf = ctc_decode(out)
    ok = (otxt == txt)
    is_label = bool(LABELPAT.fullmatch(txt))
    pairs.append({"paddle": txt, "onnx": otxt, "ok": ok, "label": is_label,
                  "w": int(x1 - x0), "h": int(y1 - y0)})
    print(f"{txt:<24}{otxt:<24}{'O' if ok else 'X'}")

total = len(pairs); same = sum(p["ok"] for p in pairs)
lab = [p for p in pairs if p["label"]]; lab_ok = sum(p["ok"] for p in lab)
etc = [p for p in pairs if not p["label"]]; etc_ok = sum(p["ok"] for p in etc)
print(f"\n[결과] 전체 완전일치 {same}/{total} ({same/max(1,total)*100:.0f}%)")
print(f"[결과] 청구기호형 토큰 {lab_ok}/{len(lab)} ({lab_ok/max(1,len(lab))*100:.0f}%)")
print(f"[결과] 기타(제목 등)   {etc_ok}/{len(etc)} ({etc_ok/max(1,len(etc))*100:.0f}%)")
print(f"[속도] ONNX 크롭당 평균 {t_onnx/max(1,total)*1000:.0f}ms (CPU)")
json.dump(pairs, io.open("out_ondevice/onnx_validate_pairs.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
