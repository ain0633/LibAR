# -*- coding: utf-8 -*-
"""train_2class_colab.ipynb 생성기 (2클래스: call_label + title)."""
import json, sys
if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
def md(s): return {"cell_type":"markdown","metadata":{},"source":s.splitlines(keepends=True)}
def code(s): return {"cell_type":"code","metadata":{},"execution_count":None,"outputs":[],"source":s.strip("\n").splitlines(keepends=True)}

cells=[]
cells.append(md(r"""# LibAR 2클래스 검출기 학습 (call_label + title)

온디바이스 아키텍처의 마지막 조각: **청구기호 라벨 + 제목 영역**을 탐지하는 YOLO.
auto_label.py로 자동 생성한 데이터셋(`dataset.zip`)으로 학습.

## 사용법
1. 런타임 → 런타임 유형 변경 → **T4 GPU**
2. 셀 순서대로 실행. 업로드 요청 시 **`dataset.zip`** 올리기
3. 마지막 셀에서 `best.pt`(2클래스) 다운로드 → libar-sample/ 에 넣으면 libar_batch.py가 자동 사용

⚠ 지금 데이터셋은 삼송도서관 15장(자동 라벨 초안)이라 **개념검증(PoC)** 수준.
   정확도↑ 하려면: 라벨 다듬기 + 서가 사진/영상 더 추가 + 대림 데이터로 파인튜닝.
"""))

cells.append(code(r"""
# 1. 설치
!pip install -q ultralytics
import torch; print("CUDA:", torch.cuda.is_available())
"""))

cells.append(code(r"""
# 2. dataset.zip 업로드 & 압축 해제
from google.colab import files
up = files.upload()   # dataset.zip 선택
import zipfile, os
os.makedirs("dataset", exist_ok=True)
with zipfile.ZipFile("dataset.zip") as z: z.extractall("dataset")
# Colab 경로로 data.yaml 재작성
open("dataset/data.yaml","w",encoding="utf-8").write(
  "path: /content/dataset\ntrain: images\nval: images\nnc: 2\nnames: ['call_label','title']\n")
print("이미지:", len(os.listdir("dataset/images")))
"""))

cells.append(code(r"""
# 3. 학습 (YOLO26n, 2클래스). 소규모라 증강 강하게 + epoch 넉넉히
from ultralytics import YOLO
model = YOLO("yolo26n.pt")
model.train(data="dataset/data.yaml", epochs=120, imgsz=960, batch=8, patience=30,
            degrees=5, translate=0.1, scale=0.3, fliplr=0.0,  # 서가는 좌우반전 X
            hsv_v=0.4, project="libar2", name="detect2")
"""))

cells.append(code(r"""
# 4. 검증 (클래스별 mAP)
m = model.val()
print(f"전체 mAP@0.5      = {m.box.map50:.3f}")
print(f"클래스별 mAP@0.5  : call_label={m.box.maps[0]:.3f}, title={m.box.maps[1]:.3f}"
      if hasattr(m.box,'maps') else "")
"""))

cells.append(code(r"""
# 5. 내보내기 & 다운로드
onnx = model.export(format="onnx", imgsz=960)
best = str(model.trainer.best)
print("best:", best)
from google.colab import files
files.download(best)        # best.pt (2클래스) → libar-sample/ 에 배치
files.download(str(onnx))   # 온디바이스용
"""))

cells.append(md(r"""---
## 다음
- `best.pt`를 `libar-sample/`에 넣으면 **libar_batch.py가 자동으로 2클래스 모드**로 동작
  (검출 1회 → 라벨/제목 크롭 → 배치 rec-only → 장서 대조)
- 대림 사진 확보 시: `python auto_label.py 대림*.jpg` → dataset에 추가 → 이 노트북 재학습(파인튜닝)
"""))

nb={"cells":cells,"metadata":{"accelerator":"GPU","colab":{"gpuType":"T4","provenance":[]},
    "kernelspec":{"display_name":"Python 3","name":"python3"},"language_info":{"name":"python"}},
    "nbformat":4,"nbformat_minor":0}
json.dump(nb,open("train_2class_colab.ipynb","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("생성:", len(cells),"셀")
