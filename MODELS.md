# LibAR 모델 카드

LibAR가 스마트폰 브라우저 안에서 실행하는 모델 3종(+ 학습 원본 가중치)입니다.
가중치는 저장소가 아니라 **GitHub Release 자산**으로 배포합니다 → <https://github.com/ain0633/LibAR/releases/tag/v1.0>

| 파일 | 역할 | 베이스 | 학습 | 크기 |
| :--- | :--- | :--- | :--- | ---: |
| `libar_yolo26n_label_det.pt` | 청구기호 라벨 위치 검출 — 학습 원본(PyTorch) | Ultralytics YOLO26n | 실증관 서가 사진 206장 · 자체 라벨링 7,039박스 | 5.5 MB |
| `libar_yolo26n_label_det.onnx` | 위와 동일, 브라우저 배포용 변환본 | — | — | 11 MB |
| `det_mobile_db.onnx` | 라벨 내부 텍스트 줄 검출 (DB) | PaddleOCR mobile det | 재학습 없음 (공개 모델 그대로) | 4.7 MB |
| `libar_rec_ppocrv5_v4_fp16.onnx` | 청구기호 글자 인식 | PaddleOCR korean PP-OCRv5 rec | 현장 라벨 702줄(사람 검증) 층화 파인튜닝 v4 · fp16 압축 손실 0 검증 | 48 MB |
| `rec_charset.json` | 인식기 문자표 | — | — | 83 KB |

`SHA256SUMS.txt`가 릴리스에 함께 있습니다.

## 실측 성능 (공식 채점, 실증관 현장)

- 걷기 스캔 판독 정확도 **99%** (86/87권) — `libar-sample/walk_grade.py`
- 도서 위치 추정 **273/273** — `libar-sample/order_infer_validate.py`
- fp16 압축 손실 **0** (평가셋 전수) — `libar-sample/eval_fp16_full.py`
- Python↔JS 판정 골든 파리티 144/144 — `libar-sample/webdemo/tests/run_all.mjs`

## 파이프라인에서의 위치

```
카메라 프레임 → [YOLO26n] 라벨 박스 → [DB det] 글자 줄 → [PP-OCRv5 rec] 문자열 → 장서 대조 + LIS 순서 판정 (libar_rec.js)
```

전 과정이 ONNX Runtime Web(WebGPU/WASM)으로 폰 안에서 실행되며, 촬영 화면은 기기 밖으로 전송되지 않습니다.

## 사용법

```python
# ONNX (onnxruntime만 필요)
import onnxruntime as ort
det = ort.InferenceSession("libar_yolo26n_label_det.onnx")
rec = ort.InferenceSession("libar_rec_ppocrv5_v4_fp16.onnx")
# 전처리·후처리는 libar-sample/webdemo/test_det_onnx.py, test_rec_onnx.py 참조

# PyTorch 원본 (ultralytics 필요)
from ultralytics import YOLO
model = YOLO("libar_yolo26n_label_det.pt")
```

웹데모에 직접 넣으려면 `libar-sample/webdemo/`에 `det_mobile.onnx`, `rec_v4_fp16.onnx`, `rec_charset.json`,
`libar-sample/call_label_yolo3/best.onnx` 이름으로 배치하면 `app.html`이 그대로 로드합니다.

## 학습 데이터

- 검출: 실증관(영등포구립 대림도서관) 서가 촬영 206장, 라벨 박스 7,039개 자체 라벨링 (`build_yolo_labelset*.py`, `train_label_yolo*_colab.ipynb`)
- 인식: 현장 라벨 조각 5,200여 개 → 사람 검증 정답 788줄 중 702줄로 파인튜닝 (`drive_crops_to_pairs.py`, `ocr_finetune*_colab.ipynb`)
- 촬영물은 책등·라벨만 담고 있으며 인물·이용자 정보는 포함하지 않습니다.

## 라이선스

- 본 저장소와 배포 가중치: **AGPL-3.0** — [LICENSE](LICENSE) · Copyright (c) 2026 Ain Lee (ain0633)
- `libar_yolo26n_*`: Ultralytics YOLO(AGPL-3.0) 파생 가중치 — AGPL 조건이 그대로 적용됩니다
- `det_mobile_db.onnx`, `libar_rec_ppocrv5_*`: PaddleOCR(Apache-2.0) 파생 — 원 저작권 고지를 유지합니다
- 사용·수정·재배포 시 저작권 표시를 유지하고, 파생 소프트웨어(네트워크 서비스 포함)의 소스를 AGPL-3.0으로 공개해야 합니다
