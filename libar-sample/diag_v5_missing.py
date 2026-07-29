# -*- coding: utf-8 -*-
"""v3만 잡은 박스(v5 누락)를 빨강으로 렌더 + conf 완화 시 회수 여부."""
import io, sys
import cv2, numpy as np
from pathlib import Path
from ultralytics import YOLO

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
img = cv2.imdecode(np.fromfile(str(HERE/"webdemo/demo/demo1.jpg"), np.uint8), 1)
H, W = img.shape[:2]

v3 = YOLO(HERE/"call_label_yolo3/best.pt").predict(img, imgsz=1280, conf=0.25, verbose=False)[0]
m5 = YOLO(HERE/"call_label_yolo_v5/best.pt")
v5 = m5.predict(img, imgsz=1280, conf=0.25, verbose=False)[0]
v5lo = m5.predict(img, imgsz=1280, conf=0.10, verbose=False)[0]

b3 = v3.boxes.xyxy.cpu().numpy()
b5 = v5.boxes.xyxy.cpu().numpy()
b5lo = v5lo.boxes.xyxy.cpu().numpy()
c5lo = v5lo.boxes.conf.cpu().numpy()

def cx(b): return ((b[0]+b[2])/2, (b[1]+b[3])/2)
def near(b, arr, tol):   # 중심 거리로 대응 (기하가 달라 IoU 부적합)
    x, y = cx(b)
    return any(abs(x-cx(a)[0]) < tol and abs(y-cx(a)[1]) < tol*2 for a in arr)

tol = np.median(b3[:, 2]-b3[:, 0]) * 0.6
miss = [b for b in b3 if not near(b, b5, tol)]
rec_lo = [b for b in miss if near(b, b5lo, tol)]
print(f"v3만 잡음 {len(miss)}개 / 그중 conf 0.10로 낮추면 회수 {len(rec_lo)}개")
print(f"v5 conf0.10 총 박스 {len(b5lo)}개 (0.25에선 {len(b5)}개)")

vis = img.copy()
for x0, y0, x1, y1 in b5.astype(int):
    cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0), 5)
for x0, y0, x1, y1 in np.array(miss).astype(int):
    cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 0, 255), 10)
sc = 1400/W
vis = cv2.resize(vis, (1400, int(H*sc)))
cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(str(HERE/"diag_demo1_miss.jpg"))
print("렌더: diag_demo1_miss.jpg (빨강 = v5 누락)")
