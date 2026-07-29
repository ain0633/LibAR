# -*- coding: utf-8 -*-
"""변환기 테스트용 샘플 수신함 zip — 앱 업로드 포맷 그대로 (demo1 직독 크롭)."""
import io, json, zipfile
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
img = cv2.imdecode(np.fromfile(str(HERE/"webdemo/demo/demo1.jpg"), dtype=np.uint8), 1)
rows = json.load(io.open(HERE/"webdemo/demo/demo1.json", encoding="utf-8"))
(HERE/"수집조각").mkdir(exist_ok=True)

z = zipfile.ZipFile(HERE/"수집조각/libar_crops_sample.zip", "w", zipfile.ZIP_DEFLATED)
manifest = []
k = 0
for r in rows:
    if not (r["call"] and r.get("how") == "청구기호"): continue
    x0, y0, x1, y1 = [int(v) for v in r["box"]]
    crop = img[max(0,y0):y1, max(0,x0):x1]
    if crop.size == 0: continue
    name = f"crop_{k:04d}.jpg"
    z.writestr(name, cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes())
    manifest.append({"file": name, "call": r["call"], "how": r["how"], "box": [x0,y0,x1,y1], "scan": 1})
    k += 1
z.writestr("manifest.json", json.dumps({"source": "LibAR webdemo", "crops": manifest}, ensure_ascii=False))
z.close()
print(f"샘플 zip: 크롭 {k}개")
