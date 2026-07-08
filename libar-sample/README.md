# LibAR 샘플 — 집 책 10권으로 돌려보는 오배열 탐지 데모

> **[안내]** 이 문서는 초기 검증(집 책 데모) 단계 기준입니다. 아래에서 참조하는
> `make_test_image.py` · `make_labels.py` · `compare_ocr.py`는 역할을 다해 제거되었습니다
> (git 히스토리에 보존). 현재 실증 파이프라인 사용법은 바로 아래 섹션 참고.

## 현재 실증 파이프라인 — `daelim_closeup.py`

```
python daelim_closeup.py <서가사진.jpg> [--rec_dir korean_lowres_rec_infer] [--no_title]
```

- `--rec_dir`: 라벨 전용 파인튜닝 rec 모델 폴더 (없으면 기존 모델만 사용). 제목 OCR은 항상 기존 모델(이원화).
- `--no_title`: 제목 복구 생략 (라벨 직독만, 빠름)
- **필요 파일** (용량 문제로 저장소 미포함, 팀 드라이브 공유): 서가 사진, `daelim_catalog.csv`(장서 목록), `korean_lowres_rec_infer/`(파인튜닝 모델)
- **출력**: `out_ondevice/` 아래 AR 오버레이 이미지(`*_ar.jpg`), 결과 JSON, OCR 토큰 캐시(재실행 시 인식 생략하고 매칭 로직만 0초 재실험 가능)
- **주의**: paddle이 한글 절대경로를 못 읽으므로 `libar-sample` 폴더 안에서 상대경로로 실행할 것

광각 여러 컷 합산 측정과 ONNX 변환은 `daelim_multiframe_v3.ipynb`(Colab),
파인튜닝 학습은 `gen_synth_labels.py` + `ocr_finetune_colab.ipynb`(Colab GPU) 참고.

서가 사진 1장 + 책 목록(books.csv)만 넣으면 → **오배열(빨강)·찾는 책(초록)·판독불가(회색)** 를 표시한 이미지가 나옵니다.
대림도서관 적용 시 books.csv를 장서데이터로 교체하면 그대로 동작합니다 ("데이터만 넣으면").

## 0. 설치 (최초 1회)

```
cd libar-sample
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> 최초 실행 시 YOLO 모델(자동)과 EasyOCR 한국어 모델(~100MB)이 자동 다운로드됩니다.

## 1. 실물 없이 즉시 검증 (가상 서가)

```
.venv\Scripts\python make_test_image.py     → test_shelf.jpg 생성 (오배열 2권 심어둠)
.venv\Scripts\python pipeline.py test_shelf.jpg
```

`out/annotated.jpg` 에서 심어둔 2권이 빨갛게 표시되면 파이프라인 정상.

## 2. 우리집 책 10권으로 실물 데모

1. **books.csv 수정** — 집 책 10권의 제목·저자 입력, 청구기호는 KDC 대분류로 직접 부여
   (예: 컴퓨터 005, 심리 181, 경제 325, 한국소설 813.7, 영미소설 843, 역사 911)
2. **라벨 인쇄·부착** — `python make_labels.py` → `labels_print.png` 100% 배율 인쇄 → 오려서 책등 하단에 부착
3. **책장에 꽂기** — 청구기호 순서대로 꽂되, **2권은 일부러 바꿔 꽂기**
4. **촬영** — 정면에서, 밝은 조명, 라벨이 선명하게, 가로 1500px 이상
5. **실행**
   ```
   .venv\Scripts\python pipeline.py 내사진.jpg                      # 사서 모드
   .venv\Scripts\python pipeline.py 내사진.jpg --search "813.7-김94ㅎ"  # 이용자 모드
   .venv\Scripts\python pipeline.py 내사진.jpg --ocr ppocr          # 한국어 PP-OCRv5로 실행
   ```
6. `out/annotated.jpg`, `out/result.json` 확인

## OCR 엔진 선택 & 비교

- `--ocr easyocr` (기본): 가벼운 다국어 OCR
- `--ocr ppocr`: **한국어 전용 PP-OCRv5**(korean_PP-OCRv5_mobile_rec). v3 대비 +30% 정확도.
  설치: `.venv\Scripts\pip install paddlepaddle==3.3.1 paddleocr`

**두 엔진 판독률 비교 (원고 실측 자료):**
```
.venv\Scripts\python compare_ocr.py test_shelf.jpg
```
→ 라벨별 두 엔진 결과·매칭 성공률·평균 신뢰도 표 + `out/ocr_compare.csv`

## 파이프라인 구조 (PRD §5.0 = 코드 그대로)

```
사진 → ①탐지(YOLO 책등 + CV 라벨) → ②OCR(EasyOCR, 어댑터 교체식)
     → ③신뢰도 게이트(미달=회색, 판정 제외) → ④기준표 대조+오토코렉트
     → ⑤LIS 오배열 판정 → ⑥오버레이(🔴🟢⚪🔵)
```

- **라벨 우선(Label-first):** 책 생김새로 식별하지 않음 → 판본·개정판·커버 문제 원천 회피
- **신뢰도 게이트:** 못 읽은 라벨은 '판독불가'로 분리 — 틀린 판정을 하지 않음
- **기준표 제약 오토코렉트:** OCR이 다소 틀려도 "그 서가에 있어야 할 책 목록" 안에서 보정
- **적용 범위:** spine-out 단행본 서가 (그림책·면출 배가는 대상 외, PRD §9.1)

## 파일

| 파일 | 역할 |
|---|---|
| `books.csv` | 정답 기준표 (= 도서관 장서데이터 자리) |
| `make_labels.py` | 청구기호 라벨 인쇄 시트 생성 |
| `make_test_image.py` | 가상 서가 생성 (실물 없이 검증) |
| `pipeline.py` | 메인 파이프라인 |
| `out/` | 결과 (annotated.jpg, result.json) |
