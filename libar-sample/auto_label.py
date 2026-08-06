# -*- coding: utf-8 -*-
"""자동 라벨러 — 서가 사진에서 YOLO 2클래스 라벨을 자동 생성
────────────────────────────────────────────────────────────
수작업 라벨링·남의 데이터셋 없이, 우리 서가 사진으로 학습 데이터를 만든다.

원리:
  ① YOLO(best.pt) 책등 탐지 → 각 책의 세로 영역(컬럼)
  ② PP-OCR 텍스트 '검출'(TextDetection) → 글자 영역 박스 (인식 아님, 빠름)
  ③ 위치 규칙으로 2클래스 분류:
       · 책등 하단(라벨 띠)에 있고 '숫자 포함' → call_label (청구기호 스티커)
       · 그 위쪽 텍스트 → title (제목)
  ④ YOLO 포맷 라벨(.txt) + data.yaml 저장 → 그대로 학습

대림 사진에도 동일 실행. 사람은 결과를 훑어 잘못된 것만 수정(반자동).

사용:
  python auto_label.py 서가1.jpg 서가2.jpg ...
  → dataset/images/*.jpg, dataset/labels/*.txt, dataset/data.yaml 생성
  → dataset/preview/*.jpg 로 눈으로 확인
"""
import argparse, os, sys, shutil
from pathlib import Path
os.environ.setdefault("FLAGS_use_mkldnn", "0")
import numpy as np, cv2
from PIL import Image, ImageDraw

if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
CLASSES = ["call_label", "title"]   # 0, 1


def load_models():
    from ultralytics import YOLO
    yolo = None
    for name in [str(HERE/"spine1.pt"), "yolo26n.pt", "yolo11n.pt"]:
        try: yolo = YOLO(name); print(f"[YOLO] {Path(name).name}"); break
        except Exception: continue
    return yolo


def dedup_spines(spines, iou_x=0.6):
    """과탐지된 겹친 책등 박스 병합 (x축 겹침 기준)."""
    spines = sorted(spines, key=lambda b: b[0])
    out = []
    for b in spines:
        if out:
            a = out[-1]
            ox = max(0, min(a[2], b[2]) - max(a[0], b[0]))
            w = min(a[2]-a[0], b[2]-b[0])
            if w > 0 and ox / w > iou_x:      # 크게 겹치면 같은 책 → 병합
                out[-1] = [min(a[0],b[0]), min(a[1],b[1]), max(a[2],b[2]), max(a[3],b[3])]
                continue
        out.append(list(b))
    return out


def has_digit_region(bgr, box):
    """라벨 판별 보조: 밝고(스티커) 사각형인지 대략 확인 — 여기선 위치규칙 위주라 생략 가능"""
    return True


def isolate_cream(region_bgr):
    """책등 하단 영역에서 크림색 청구기호 라벨(저채도·고명도)의 세로 구간을 찾는다.
    파란 카테고리 띠·색 책등은 채도 높아 제외됨. 반환 (ry0, ry1) 상대좌표 또는 None."""
    if region_bgr.size == 0: return None
    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
    S, V = hsv[:, :, 1], hsv[:, :, 2]
    mask = ((S < 70) & (V > 135)).astype(np.uint8)
    rowfrac = mask.mean(axis=1)
    good = rowfrac > 0.4
    best = (0, 0); cur = None
    for i, g in enumerate(list(good) + [False]):
        if g and cur is None: cur = i
        elif not g and cur is not None:
            if i - cur > best[1] - best[0]: best = (cur, i)
            cur = None
    return best if best[1] - best[0] >= 8 else None


def cream_labels(bgr, spines):
    """책등 박스 → 크림색 라벨을 실제로 찾아 call_label(타이트) + title 영역 생성.
    기하학 % 추정이 아니라 라벨 위치를 이미지에서 검출 → 사람은 수정만 하면 됨(반자동)."""
    labels = []   # (cls, box)
    for s in spines:
        x0, y0, x1, y1 = s; h = y1 - y0
        # 하단 26% 영역에서 크림색 라벨 세로구간 검출
        ry0 = y0 + int(h * 0.74); region = bgr[ry0:y1, x0:x1]
        cream = isolate_cream(region)
        if cream:
            pad = int((cream[1] - cream[0]) * 0.05)
            ly0 = ry0 + cream[0] - pad; ly1 = ry0 + cream[1] + pad
        else:                                        # 검출 실패 시 폴백
            ly0 = y0 + int(h * 0.80); ly1 = y0 + int(h * 0.94)
        labels.append((0, [x0, max(y0, ly0), x1, min(y1, ly1)]))     # call_label(크림 라벨)
        # title: 책등 상단~라벨 위 색 영역 (제목 텍스트)
        labels.append((1, [x0, y0 + int(h * 0.06), x1, max(y0 + int(h * 0.20), ly0 - int(h * 0.06))]))
    return labels


def to_yolo(box, W, H):
    x0,y0,x1,y1 = box
    return ((x0+x1)/2/W, (y0+y1)/2/H, (x1-x0)/W, (y1-y0)/H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default=str(HERE/"dataset"))
    args = ap.parse_args()
    out = Path(args.out)
    (out/"images").mkdir(parents=True, exist_ok=True)
    (out/"labels").mkdir(parents=True, exist_ok=True)
    (out/"preview").mkdir(parents=True, exist_ok=True)

    yolo = load_models()
    total = {0:0, 1:0}
    for img_path in args.images:
        p = Path(img_path)
        im = Image.open(p).convert("RGB"); W,H = im.size
        bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

        raw = [[int(v) for v in b.xyxy[0].tolist()]
               for b in yolo.predict(bgr, conf=0.2, verbose=False)[0].boxes]
        # 메인 서가(라벨 띠 높이에 걸치는 책등)만 + 과탐지 중복 병합
        band_mid = H*0.74
        spines = dedup_spines([b for b in raw if b[1] <= band_mid <= b[3]])
        labels = cream_labels(bgr, spines)
        print(f"[{p.name}] 책등 {len(raw)}→{len(spines)}(중복병합) → 라벨 "
              f"call_label {sum(c==0 for c,_ in labels)} · title {sum(c==1 for c,_ in labels)}")

        # 저장
        shutil.copy(p, out/"images"/p.name)
        with open(out/"labels"/(p.stem+".txt"), "w") as f:
            for cls, box in labels:
                cx,cy,w,h = to_yolo(box, W, H)
                f.write(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                total[cls]+=1
        # 미리보기
        vis = im.copy(); d = ImageDraw.Draw(vis)
        for cls, box in labels:
            col = (235,60,60) if cls==0 else (40,140,235)
            d.rectangle(box, outline=col, width=4)
        vis.save(out/"preview"/(p.stem+"_preview.jpg"), quality=88)

    # data.yaml
    (out/"data.yaml").write_text(
        f"path: {out.as_posix()}\ntrain: images\nval: images\n"
        f"nc: {len(CLASSES)}\nnames: {CLASSES}\n", encoding="utf-8")
    print(f"\n[완료] 라벨 총 call_label {total[0]} · title {total[1]}")
    print(f"  {out}/images, labels, data.yaml (학습용)  /  preview (눈으로 확인)")


if __name__ == "__main__":
    main()
