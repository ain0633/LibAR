# -*- coding: utf-8 -*-
"""call_label YOLO26n ONNX 로컬 검증 — val 5장 P/R + 각도 사진 일반화 + CPU 속도."""
import sys, io, glob, os, time
import cv2, numpy as np
import onnxruntime as ort

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
SESS = ort.InferenceSession("call_label_yolo/best.onnx", providers=["CPUExecutionProvider"])
SZ = 1280

def imread(p): return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), 1)

def letterbox(im):
    h, w = im.shape[:2]
    r = SZ / max(h, w)
    nh, nw = int(h*r), int(w*r)
    canvas = np.full((SZ, SZ, 3), 114, np.uint8)
    canvas[:nh, :nw] = cv2.resize(im, (nw, nh))
    return canvas, r

def detect(im, conf=0.3):
    lb, r = letterbox(im)
    x = lb[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    t0 = time.time()
    out = SESS.run(None, {"images": x})[0][0]     # (300, 6) = x0,y0,x1,y1,conf,cls
    dt = time.time() - t0
    boxes = [(b[:4] / r, float(b[4])) for b in out if b[4] >= conf]
    return boxes, dt

def iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1-ix0) * max(0, iy1-iy0)
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0

# ── 1) val 5장 P/R@IoU0.5 ──
tp = fp = fn = 0; times = []
for imgp in sorted(glob.glob("yolo_labelset/images/val/*.jpg")):
    im = imread(imgp)
    H, W = im.shape[:2]
    gts = []
    for ln in io.open(imgp.replace("images", "labels").replace(".jpg", ".txt"), encoding="utf-8"):
        _, cx, cy, bw, bh = map(float, ln.split())
        gts.append([(cx-bw/2)*W, (cy-bh/2)*H, (cx+bw/2)*W, (cy+bh/2)*H])
    dets, dt = detect(im); times.append(dt)
    used = set()
    for db, c in sorted(dets, key=lambda d: -d[1]):
        j = max(range(len(gts)), key=lambda k: iou(db, gts[k]) if k not in used else -1, default=None)
        if j is not None and j not in used and iou(db, gts[j]) >= 0.5:
            used.add(j); tp += 1
        else: fp += 1
    fn += len(gts) - len(used)
    print(f"  {os.path.basename(imgp)}: GT {len(gts)} · 검출 {len(dets)} · 일치 {len(used)}")
prec = tp/max(1, tp+fp); rec = tp/max(1, tp+fn)
print(f"[val 5장] P {prec:.2f} · R {rec:.2f} (IoU0.5, conf0.3) · CPU {np.mean(times)*1000:.0f}ms/장")

# ── 2) 각도 사진 (학습 제외 프레임) ──
for name in ["KakaoTalk_20260708_164051931_11", "KakaoTalk_20260708_164051931_10"]:
    im = imread(f"../대림데이터/700번대/{name}.jpg")
    dets, dt = detect(im)
    vis = im.copy()
    for (x0, y0, x1, y1), c in dets:
        cv2.rectangle(vis, (int(x0), int(y0)), (int(x1), int(y1)), (0, 220, 0), 6)
    vis = cv2.resize(vis, (1500, int(im.shape[0]*1500/im.shape[1])))
    cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(f"out_ondevice/yolo_angle_{name[-2:]}.jpg")
    print(f"[각도 {name[-2:]}] 검출 {len(dets)}개 · {dt*1000:.0f}ms → out_ondevice/yolo_angle_{name[-2:]}.jpg")
