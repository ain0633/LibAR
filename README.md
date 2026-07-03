# LibAR — 도서관 빅데이터 × 책등 인식 기반 실시간 AR 서가 관리·탐색 시스템

스마트폰 카메라로 서가를 비추면, AI가 책등을 탐지하고 청구기호를 판독하여
**사서에게는 오배열 도서(빨강)를, 이용자에게는 찾는 책(초록)을** 화면에 실시간 표시하는 웹 서비스.
축적된 오배열 로그를 전국 대출 빅데이터와 결합 분석해 서가 운영을 최적화한다.

> **2026 도서관 데이터 활용 공모전** 출품작 (서비스 아이디어 제안 부문) · 실증 대상: 영등포구립 대림도서관

---

## 파이프라인 (한 컷 스캔 모드)

```
사진 → ① 책등/라벨 탐지 (YOLO26) → ② 청구기호 OCR (한국어 PP-OCRv5)
     → ③ 신뢰도 게이트(판독불가 분리) → ④ 기준표 대조 + 제목 이중 대조
     → ⑤ LIS 오배열 판정 → ⑥ 오버레이(🔴오배열 🟢검색 ⚪판독불가)
```

- **라벨 우선(Label-first):** 책 생김새가 아니라 청구기호 라벨을 읽음 → 판본·개정판·커버 변수 회피
- **이중 대조:** 라벨이 잘리거나 훼손돼도 책등 제목 OCR로 복구
- **LIS 판정:** 인접 비교가 아닌 최소 오배열 집합만 지목 (이웃 오탐 방지)
- **적용 범위:** spine-out 단행본 서가 (그림책·비정형 배가는 향후 과제)

## 저장소 구성

| 경로 | 내용 |
| :--- | :--- |
| `Library_AR_Book_Detection_PRD.md` | 제품 요구사항 정의서 (설계·일정·데이터·심사 대응) |
| `LibAR_기술해설서_공유용.md` | 비개발자(사서 팀원)용 기술 해설서 |
| `libar-sample/` | 동작하는 샘플 파이프라인 (아래) |

### `libar-sample/`
| 파일 | 역할 |
| :--- | :--- |
| `pipeline.py` | 메인 파이프라인 (탐지→OCR→판정→오버레이) |
| `books.csv` | 정답 기준표 (= 도서관 장서데이터 자리) |
| `make_test_image.py` | 가상 서가 생성 (실물 없이 검증, `--damage`로 라벨 훼손 시뮬) |
| `make_labels.py` | 청구기호 라벨 인쇄 시트 생성 |
| `compare_ocr.py` | EasyOCR vs 한국어 PP-OCRv5 판독률 비교 |
| `train_spine_colab.ipynb` | 책등 탐지 모델(YOLO26) 학습 노트북 (Colab) |

## 빠른 시작

```bash
cd libar-sample
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

python make_test_image.py            # 가상 서가 생성 (오배열 2권 심음)
python pipeline.py test_shelf.jpg    # 사서 모드: 오배열 탐지
python pipeline.py test_shelf.jpg --search "863-생72ㅇ"   # 이용자 모드: 도서 검색
```

자세한 사용법은 [`libar-sample/README.md`](libar-sample/README.md) 참고.

## 기술 스택

Next.js PWA · YOLO26 (onnxruntime-web) · 한국어 PP-OCRv5 · Supabase · 도서관 정보나루/국립중앙도서관 Open API · 솔로몬 장서·대출 데이터

## 진행 현황

- [x] 파이프라인 설계·구현 (탐지·OCR·LIS 판정·이중 대조·오버레이)
- [x] 두 모드(사서/이용자) 동작 검증
- [x] OCR 엔진 비교 (EasyOCR 0.71 → PP-OCRv5 0.97 평균 신뢰도)
- [x] 책등 탐지 모델 1차 학습 (YOLO26, baseline mAP@0.5 0.47 — 개선 중)
- [ ] 세그멘테이션 학습 전환 / 증강 / 대림 현장 데이터 파인튜닝
- [ ] 실제 서가 촬영 테스트
- [ ] 정보나루/솔로몬 데이터 연동
