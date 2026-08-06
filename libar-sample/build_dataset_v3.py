# -*- coding: utf-8 -*-
"""dataset_v3 생성 — 검출기 재학습용 밀집 라벨.
  문제: 기존 dataset_v2는 원거리 1080p 프레임에 장당 ~14박스만 라벨(수백 권 미라벨)
        → 미라벨 책이 학습 때 오답 처리 → mAP50 0.50에 정체 + 박스 걸침
  해결: shelf_4558(24MP, 실제 타깃 도메인)에서 spine 58개 기준으로
        call_label/title 박스를 '빠짐없이' 생성 → 타일 분할로 10장+ 학습 이미지화
  라벨 규칙(걸침 방지): 박스 x범위 = spine 폭 안쪽 8% 인셋 (이웃 스티커 배제)
"""
import json, sys, shutil, zipfile
import numpy as np, cv2
from pathlib import Path
from PIL import Image
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
OUT = HERE/"dataset_v3"

spines = json.load(open(HERE/"shelf_4558.tokens.json", encoding="utf-8"))
spines.sort(key=lambda s: (s["box"][0]+s["box"][2])/2)
bgr = cv2.cvtColor(np.array(Image.open(HERE/"shelf_4558.jpg").convert("RGB")), cv2.COLOR_RGB2BGR)
H, W = bgr.shape[:2]

def sticker_yrange(x0, y0, x1, y1):
    """spine 하단 밴드에서 크림색 스티커의 정확한 y범위 (isolate_label 로직)."""
    h = y1 - y0
    by0 = y0 + int(h*0.70)
    crop = bgr[by0:min(H, y1), x0:x1]
    if crop.size == 0: return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] < 70) & (hsv[:, :, 2] > 135)).astype(np.uint8)
    rowfrac = mask.mean(axis=1)
    good = rowfrac > 0.4
    best = (0, 0); cur = None
    for i, g in enumerate(list(good)+[False]):
        if g and cur is None: cur = i
        elif not g and cur is not None:
            if i-cur > best[1]-best[0]: best = (cur, i)
            cur = None
    if best[1]-best[0] < 10: return None
    pad = int((best[1]-best[0])*0.05)
    return by0+max(0, best[0]-pad), by0+best[1]+pad

# ── spine별 스티커 y범위 (1차) ──
raw = []
for s in spines:
    x0, y0, x1, y1 = s["box"]
    raw.append(sticker_yrange(x0, y0, x1, y1))
# 스티커는 같은 선반이라 절대 y가 비슷 → 중앙값에서 크게 벗어난 오탐(분홍책 등) 교정
valid = [r for r in raw if r]
med0 = int(np.median([r[0] for r in valid])); med1 = int(np.median([r[1] for r in valid]))
fixed = 0
for i, r in enumerate(raw):
    if r is None or abs((r[0]+r[1])/2 - (med0+med1)/2) > 180:
        raw[i] = (med0, med1); fixed += 1
print(f"[스티커] 중앙값 y=({med0},{med1}) · 이상치 교정 {fixed}건")

# ── spine별 박스 생성 ──
boxes = []   # (cls, x0,y0,x1,y1)
for s, sy in zip(spines, raw):
    x0, y0, x1, y1 = s["box"]; w = x1-x0; h = y1-y0
    ix0, ix1 = x0+int(w*0.08), x1-int(w*0.08)          # 걸침 방지 인셋
    boxes.append((0, ix0, sy[0], ix1, sy[1]))            # call_label
    ty1 = sy[0] - int(h*0.01)
    ty0 = y0 + int(h*0.02)
    if ty1 - ty0 > h*0.2:
        boxes.append((1, ix0, ty0, ix1, ty1))            # title
print(f"[라벨] spine {len(spines)} → 박스 {len(boxes)} (call {sum(1 for b in boxes if b[0]==0)} / title {sum(1 for b in boxes if b[0]==1)})")

# ── 타일 분할 ──
ymin = max(0, min(b[2] for b in boxes) - 120)
ymax = min(H, max(b[4] for b in boxes) + 120)
TILE_W, STRIDE = 2000, 1200
tiles = []
x = 0
while x < W:
    tiles.append((x, ymin, min(W, x+TILE_W), ymax))
    if x + TILE_W >= W: break
    x += STRIDE
# 전체 축소본 1장 추가
tiles.append((0, ymin, W, ymax))
print(f"[타일] {len(tiles)}장 (마지막 1장은 전체 뷰)")

if OUT.exists(): shutil.rmtree(OUT)
for sub in ["images/train", "images/val", "labels/train", "labels/val"]:
    (OUT/sub).mkdir(parents=True)

VAL_IDX = {1, 3}   # 홀드아웃 타일
n_img = 0
for ti, (tx0, ty0, tx1, ty1) in enumerate(tiles):
    tw, th = tx1-tx0, ty1-ty0
    crop = bgr[ty0:ty1, tx0:tx1]
    lines = []
    for cls, bx0, by0, bx1, by1 in boxes:
        ox0, oy0 = max(bx0, tx0), max(by0, ty0)
        ox1, oy1 = min(bx1, tx1), min(by1, ty1)
        if ox1 <= ox0 or oy1 <= oy0: continue
        area_in = (ox1-ox0)*(oy1-oy0); area = (bx1-bx0)*(by1-by0)
        if area_in/area < 0.6: continue                    # 60% 미만 걸친 박스 제외
        cx = ((ox0+ox1)/2 - tx0)/tw; cy = ((oy0+oy1)/2 - ty0)/th
        bw = (ox1-ox0)/tw; bh = (oy1-oy0)/th
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    if len(lines) < 4: continue
    split = "val" if ti in VAL_IDX else "train"
    name = f"shelf4558_t{ti:02d}"
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])   # 한글 경로: imwrite 불가
    (OUT/f"images/{split}/{name}.jpg").write_bytes(buf.tobytes())
    open(OUT/f"labels/{split}/{name}.txt", "w").write("\n".join(lines))
    n_img += 1
    print(f"  {name} [{split}] 박스 {len(lines)}")

(OUT/"data.yaml").write_text(
    "path: .\ntrain: images/train\nval: images/val\nnames:\n  0: call_label\n  1: title\n", encoding="utf-8")

with zipfile.ZipFile(HERE/"dataset_v3.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in OUT.rglob("*"):
        if p.is_file(): z.write(p, p.relative_to(HERE))
print(f"\n[완료] dataset_v3/ ({n_img}장) + dataset_v3.zip")
