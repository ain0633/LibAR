# -*- coding: utf-8 -*-
"""LibAR 온디바이스 아키텍처 파이프라인 — 검출 1회 + 배치 rec-only
────────────────────────────────────────────────────────────────
per-crop 검출 재실행(56분) 대신: YOLO 1회 → 크롭 배치 인식(수초).

동작:
  1. YOLO(best.pt) 1회 forward → 'call_label'(청구기호 라벨) + 'title'(제목) 박스
     · 2클래스 모델이면 클래스명으로 분리
     · 1클래스/COCO 폴백이면 책등 박스에서 하단=라벨, 상단=제목 영역을 기하학적으로 크롭
  2. 모든 라벨크롭 + 제목크롭을 TextRecognition(korean rec)에 '배치 1회' 투입
  3. 장서 대조: 라벨 우선, 접두어 모호 시 제목으로 해소 (808.91 vs 808.912)
  4. LIS 순서 판정 + 배열 위치 정렬

사용:
  python libar_batch.py shelf_4558.jpg --catalog books_4558.csv [--search "제목|청구기호"]

★ 2클래스 검출기(best.pt)를 넣으면 정확도 완성. 지금은 기하학 크롭 폴백으로 아키텍처·속도 시연.
"""
import argparse, csv, difflib, json, os, re, sys, time, unicodedata
from pathlib import Path
os.environ.setdefault("FLAGS_use_mkldnn", "0")
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

# ───────── 매칭·판정 유틸 ─────────
def norm(s): return re.sub(r"[\s\-–—_/·.]+","",unicodedata.normalize("NFC",str(s))).lower()
def norm_title(s): return re.sub(r"[^0-9A-Za-z가-힣]","",unicodedata.normalize("NFC",str(s))).lower()

def load_catalog(path):
    rows=list(csv.DictReader(open(path,encoding="utf-8-sig")))
    for i,r in enumerate(rows):
        r["_norm"]=norm(r["call_number"]); r["_tnorm"]=norm_title(r["title"]); r["_order"]=i
    return rows

def match_label(text, catalog):
    """청구기호 조각 → 장서 대조. 정확/접두어 후보 반환.
    반환: (unique_row 또는 None, 후보리스트) — 후보 다수면 접두어 모호 = 제목으로 해소 필요."""
    n=norm(text)
    if not n: return None, []
    exact=[r for r in catalog if r["_norm"]==n]
    if len(exact)==1: return exact[0], exact
    # 접두어(잘림) 후보: 읽은 조각이 장서 청구기호의 접두어
    pref=[r for r in catalog if r["_norm"].startswith(n) or n.startswith(r["_norm"])]
    if len(pref)==1: return pref[0], pref
    return None, pref   # 0개=미등록, 다수=모호

def match_title(text, catalog, thr=0.5):
    t=norm_title(text)
    if len(t)<2: return None,0.0
    best,bs=None,0.0
    for r in catalog:
        c=r["_tnorm"]
        if not c: continue
        lm=difflib.SequenceMatcher(None,t,c).find_longest_match(0,len(t),0,len(c))
        p=lm.size/min(len(t),len(c)) if min(len(t),len(c)) else 0
        s=0.6*p+0.4*difflib.SequenceMatcher(None,t,c).ratio()
        if s>bs: best,bs=r,s
    return (best,round(bs,2)) if bs>=thr else (None,round(bs,2))

def lis_misplaced(keys):
    n=len(keys)
    if n==0: return set()
    L=[1]*n; P=[-1]*n
    for i in range(n):
        for j in range(i):
            if keys[j]<=keys[i] and L[j]+1>L[i]: L[i]=L[j]+1; P[i]=j
    e=max(range(n),key=lambda i:L[i]); keep=set()
    while e!=-1: keep.add(e); e=P[e]
    return set(range(n))-keep

# ───────── 검출 (2클래스 우선, 폴백 기하학) ─────────
def detect(bgr):
    """YOLO best.pt로 검출. 2클래스면 클래스로 분리, 아니면 책등→기하학 크롭.
    반환: books=[{spine, label_box, title_box}] (좌→우)"""
    from ultralytics import YOLO
    model=None
    for name in [str(HERE/"best.pt"),"yolo26n.pt","yolo11n.pt"]:
        try: model=YOLO(name); print(f"[YOLO] {Path(name).name}"); break
        except Exception: continue
    res=model.predict(bgr,conf=0.2,verbose=False)[0]
    names={i:n for i,n in model.names.items()}
    H=bgr.shape[0]; band_mid=H*0.74
    label_boxes=[b for b in res.boxes if names.get(int(b.cls),"")=="call_label"]
    title_boxes=[b for b in res.boxes if names.get(int(b.cls),"")=="title"]
    if label_boxes:  # ── 2클래스 모델 ──
        books=[]
        for lb in sorted(label_boxes,key=lambda b:float(b.xyxy[0][0])):
            lx=[int(v) for v in lb.xyxy[0].tolist()]
            cx=(lx[0]+lx[2])/2
            # 같은 x의 제목 박스 연결
            tb=min(title_boxes,key=lambda b:abs((float(b.xyxy[0][0])+float(b.xyxy[0][2]))/2-cx),
                   default=None)
            tbox=[int(v) for v in tb.xyxy[0].tolist()] if tb else None
            books.append({"label_box":lx,"title_box":tbox,"spine":lx})
        return books, "2class"
    # ── 폴백: 책등 박스 → 기하학 크롭 ──
    spines=[[int(v) for v in b.xyxy[0].tolist()] for b in res.boxes]
    main=[b for b in spines if b[1]<=band_mid<=b[3]]
    main.sort(key=lambda b:(b[0]+b[2])/2)
    books=[]
    for b in main:
        x0,y0,x1,y1=b; h=y1-y0
        books.append({"spine":b,
                      "label_box":[x0,max(0,y1-int(h*0.18)),x1,y1],
                      "title_box":[x0,y0+int(h*0.08),x1,y0+int(h*0.52)]})
    return books, "fallback"

# ───────── 배치 rec-only ─────────
def batch_recognize(bgr, boxes, rec, rotate=False):
    """박스 크롭들을 모아 rec.predict(리스트) 한 번. rotate=제목 세로쓰기 대응."""
    crops=[]
    for b in boxes:
        if b is None: crops.append(np.zeros((8,8,3),np.uint8)); continue
        x0,y0,x1,y1=b
        c=bgr[max(0,y0):y1, max(0,x0):x1]
        if c.size==0: c=np.zeros((8,8,3),np.uint8)
        if rotate and (y1-y0)>(x1-x0)*1.4:   # 세로로 길면 제목=세로쓰기 → 1회전
            c=cv2.rotate(c, cv2.ROTATE_90_COUNTERCLOCKWISE)
        crops.append(c)
    res=rec.predict(crops)
    res=res if isinstance(res,list) else [res]
    out=[]
    for r in res:
        out.append((str(r.get("rec_text","")), float(r.get("rec_score",0))))
    return out

# ───────── 메인 ─────────
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("image"); ap.add_argument("--catalog",default=str(HERE/"books_4558.csv"))
    ap.add_argument("--search",default=None); ap.add_argument("--out",default=str(HERE/"out_batch"))
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(exist_ok=True)

    catalog=load_catalog(args.catalog)
    im=Image.open(args.image).convert("RGB"); bgr=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR)
    print(f"[장서] {len(catalog)}권")

    books, mode = detect(bgr)
    print(f"[검출] {len(books)}권 (mode={mode})")

    from paddleocr import TextRecognition
    rec=TextRecognition(model_name="korean_PP-OCRv5_mobile_rec")

    t=time.time()
    label_reads=batch_recognize(bgr,[b["label_box"] for b in books],rec)
    title_reads=batch_recognize(bgr,[b["title_box"] for b in books],rec,rotate=True)
    print(f"[배치 rec-only] {len(books)*2}크롭 → {time.time()-t:.1f}s")

    # 결합: 라벨 우선, 접두어 모호 → 제목으로 해소
    for b,(lt,lc),(tt,tc) in zip(books,label_reads,title_reads):
        b["label_text"],b["title_text"]=lt,tt
        row,cands=match_label(lt,catalog)
        if row is None and len(cands)>1:            # 접두어 모호 → 제목
            trow,ts=match_title(tt,catalog)
            row=trow if trow in cands else (match_title(tt,catalog)[0])
            b["how"]="제목해소"
        elif row is None:                           # 라벨 실패 → 제목 복구
            row,ts=match_title(tt,catalog); b["how"]="제목복구" if row else "미인식"
        else:
            b["how"]="라벨"
        b["call_number"]=row["call_number"] if row else None
        b["title_matched"]=row["title"] if row else None
        b["order"]=row["_order"] if row else None

    matched=[b for b in books if b["call_number"]]
    mis=lis_misplaced([b["order"] for b in matched])
    for b in books: b["status"]="unknown" if b["call_number"] is None else "ok"
    for i,b in enumerate(matched):
        if i in mis: b["status"]="misplaced"

    if args.search:
        q=norm_title(args.search); qc=norm(args.search)
        for b in books:
            if b["call_number"] and (q and q in norm_title(b["title_matched"] or "") or qc and qc in norm(b["call_number"])):
                b["status"]="found"; break

    n_ok=sum(b["status"]=="ok" for b in books); n_mis=sum(b["status"]=="misplaced" for b in books)
    print(f"\n[결과] 정상 {n_ok} · 오배열 {n_mis} · 미인식 {sum(b['status']=='unknown' for b in books)}")
    for b in books[:60]:
        print(f'  [{b["status"]:9s}] {b["call_number"] or "-":14s} ({b["how"]:6s}) 라벨"{b["label_text"]}" 제목"{b["title_text"][:12]}"')
    json.dump([{k:v for k,v in b.items() if k not in ("spine",)} for b in books],
              open(out/"result.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"[완료] {out/'result.json'}")

if __name__=="__main__":
    main()
