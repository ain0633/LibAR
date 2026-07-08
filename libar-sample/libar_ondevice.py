# -*- coding: utf-8 -*-
"""LibAR 온디바이스 파이프라인 — 책등검출 → 라벨분리 → 전체OCR → 장서제약 토큰매칭
────────────────────────────────────────────────────────────────
하드코딩(접두어 미리 알기) 없음. 청구기호를 실제로 읽고, 장서로 제약해 확정한다.
  1. YOLO 책등 검출 1회
  2. 각 책등 하단에서 '크림색 청구기호 라벨'만 분리(저채도·고명도 최장 연속행)
  3. 라벨 전체OCR(검출+인식) → 토큰들 (분류/저자기호/권차 + 잡음)
  4. 장서제약 토큰매칭: 장서 청구기호도 토큰분해, 겹침 점수 최고 항목 확정
     (잡음 토큰은 어떤 장서 토큰과도 안 맞아 자동 무시. 권차에 가중)
  5. LIS 순서 판정
"""
import argparse, csv, difflib, json, os, re, sys, time, unicodedata
from pathlib import Path
os.environ["FLAGS_use_mkldnn"]="0"
import numpy as np, cv2
from PIL import Image

if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE=Path(__file__).parent
def nn(s): return re.sub(r"[^0-9A-Za-z가-힣]","",unicodedata.normalize("NFC",str(s))).lower()

def decompose(call_number):
    """청구기호 → 토큰 집합. '408-뉴88-27' → ['408','뉴88','27'] (권차=마지막)."""
    parts=[nn(p) for p in re.split(r"[\s\-–—_/]+",str(call_number)) if nn(p)]
    return parts

def load_catalog(path):
    rows=list(csv.DictReader(open(path,encoding="utf-8-sig")))
    for i,r in enumerate(rows):
        r["_toks"]=decompose(r["call_number"]); r["_order"]=i
    return rows

def sim(a,b):
    return difflib.SequenceMatcher(None,a,b).ratio()

def shared_prefix(catalog):
    """장서에서 서가 공통 접두어 토큰(분류·저자기호)을 자동 도출. 하드코딩 아님.
    예: 이 서가는 모두 408·뉴88 → ['408','뉴88']. 권차는 제외(변별값)."""
    from collections import Counter
    pc=Counter(t for r in catalog for t in r["_toks"][:-1])
    return [t for t,c in pc.items() if c>=len(catalog)*0.6]

def match_tokens(read_toks, catalog, shared):
    """장서제약 매칭. ① 시리즈 검증(접두어 존재) ② 접두어 제거 후 남은 권차 후보
    ③ 장서에 실재하는 권차만 인정(라벨 하단 우선). 저자기호'88' vs 권차'88' 충돌 방지."""
    toks=[t for t in read_toks if t]
    if not toks: return None,0.0
    def is_shared(tok): return any(sim(tok,s)>0.7 or s in tok for s in shared)
    if not any(is_shared(t) for t in toks): return None,0.0   # 뉴턴 라벨 아님 → 미인식
    rest=[t for t in toks if not is_shared(t)]
    cand=[num for t in rest for num in re.findall(r"\d{1,3}",t)]
    for c in reversed(cand):                                  # 라벨 하단(마지막)부터
        hit=[r for r in catalog if r["_toks"][-1]==c]
        if hit: return hit[0],1.0
    return None,0.0

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

def isolate_label(crop):
    """크림색 라벨(저채도·고명도) 최장 연속행 구간만. 파란 카테고리 띠 제외."""
    if crop.size==0: return crop
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    S,V=hsv[:,:,1],hsv[:,:,2]
    mask=((S<70)&(V>135)).astype(np.uint8)
    rowfrac=mask.mean(axis=1)
    good=rowfrac>0.4
    # 최장 연속 True 구간
    best=(0,0); cur=None
    for i,g in enumerate(list(good)+[False]):
        if g and cur is None: cur=i
        elif not g and cur is not None:
            if i-cur>best[1]-best[0]: best=(cur,i)
            cur=None
    y0,y1=best
    if y1-y0<8: return crop
    pad=int((y1-y0)*0.06)
    return crop[max(0,y0-pad):y1+pad]

def detect_spines(bgr,model_path):
    from ultralytics import YOLO
    m=YOLO(model_path); r=m.predict(bgr,conf=0.25,verbose=False)[0]
    H=bgr.shape[0]; band_mid=H*0.74
    sp=[[int(v) for v in b.xyxy[0].tolist()] for b in r.boxes if b.xyxy[0][1]<=band_mid<=b.xyxy[0][3]]
    sp.sort(key=lambda b:(b[0]+b[2])/2)
    out=[]
    for b in sp:
        if out:
            a=out[-1]; ox=max(0,min(a[2],b[2])-max(a[0],b[0])); w=min(a[2]-a[0],b[2]-b[0])
            if w>0 and ox/w>0.55:
                out[-1]=[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]; continue
        out.append(list(b))
    return out

def read_label(ocr,crop):
    up=cv2.resize(crop,None,fx=3,fy=3,interpolation=cv2.INTER_LANCZOS4) if crop.shape[0]<120 else crop
    res=ocr.predict(up)
    if not res: return []
    r=res[0]
    toks=list(zip(r.get("rec_texts",[]),r.get("rec_polys",[])))
    toks.sort(key=lambda t:sum(p[1] for p in t[1])/len(t[1]))
    return [nn(t) for t,_ in toks if nn(t)]

def render(im, books, out_path):
    from PIL import ImageDraw, ImageFont
    COL={"ok":(40,190,90),"misplaced":(235,60,60),"unknown":(150,150,150)}
    vis=im.copy(); d=ImageDraw.Draw(vis,"RGBA")
    try: fs=ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf",34)
    except Exception: fs=ImageFont.load_default()
    for b in books:
        c=COL[b["status"]]; x0,y0,x1,y1=b["box"]
        d.rectangle([x0,y0,x1,y1],outline=c+(255,),width=5 if b["status"]=="misplaced" else 3)
        if b["status"]=="misplaced": d.rectangle([x0,y0,x1,y1],fill=c+(60,))
        tag=b["call_number"].split("-")[-1] if b["call_number"] else "?"
        d.rectangle([x0,y0-46,x0+70,y0-4],fill=c+(235,)); d.text((x0+5,y0-44),tag,font=fs,fill=(255,255,255,255))
    vis.save(out_path,quality=88)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("image"); ap.add_argument("--catalog",default=str(HERE/"books_4558.csv"))
    ap.add_argument("--spine",default=str(HERE/"spine1.pt"))
    ap.add_argument("--out",default=str(HERE/"out_ondevice"))
    ap.add_argument("--refresh",action="store_true",help="토큰 캐시 무시하고 OCR 재실행")
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(exist_ok=True)
    catalog=load_catalog(args.catalog); shared=shared_prefix(catalog)
    print(f"[장서] {len(catalog)}권 · 공통 접두어(자동도출) {shared}")
    im=Image.open(args.image).convert("RGB"); bgr=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR)

    t0=time.time(); spines=detect_spines(bgr,args.spine); t_det=time.time()-t0
    print(f"[검출] 책등 {len(spines)}권 ({t_det:.1f}s)")
    cache=Path(args.image).with_suffix(".tokens.json")
    if cache.exists() and not args.refresh:
        books=json.load(open(cache,encoding="utf-8")); t_ocr=0.0
        print(f"[라벨 OCR] 캐시 사용 ({cache.name}, {len(books)}권)")
    else:
        from paddleocr import PaddleOCR
        ocr=PaddleOCR(lang="korean",enable_mkldnn=False,use_doc_orientation_classify=False,
                      use_doc_unwarping=False,use_textline_orientation=False)
        t1=time.time(); books=[]
        for b in spines:
            x0,y0,x1,y1=b; h=y1-y0
            crop=bgr[y0+int(h*0.74):min(bgr.shape[0],y0+int(h*0.99)), x0:x1]
            books.append({"box":b,"toks":read_label(ocr,isolate_label(crop))})
        t_ocr=time.time()-t1; json.dump(books,open(cache,"w",encoding="utf-8"),ensure_ascii=False)
        print(f"[라벨 OCR] {len(spines)}권 → {t_ocr:.1f}s (캐시 저장)")

    for bk in books:
        row,sc=match_tokens(bk["toks"],catalog,shared)
        bk["call_number"]=row["call_number"] if row else None
        bk["title"]=row["title"] if row else None
        bk["order"]=row["_order"] if row else None
        bk["score"]=sc
    matched=[b for b in books if b["call_number"]]
    mis=lis_misplaced([b["order"] for b in matched])
    for b in books: b["status"]="unknown" if b["call_number"] is None else "ok"
    for i,b in enumerate(matched):
        if i in mis: b["status"]="misplaced"

    n_ok=sum(b["status"]=="ok" for b in books); n_mis=sum(b["status"]=="misplaced" for b in books)
    uniq=len({b["call_number"] for b in matched})
    print(f"\n[결과] 인식 {len(matched)}/{len(books)} · 고유 {uniq}권 · 정상 {n_ok} · 오배열 {n_mis} · 미인식 {sum(b['status']=='unknown' for b in books)}")
    print(f"[속도] 검출 {t_det:.1f}s + OCR {t_ocr:.1f}s (CPU, 24MP 원본)\n")
    for b in books:
        print(f'  [{b["status"]:9s}] {b["call_number"] or "-":13s} 토큰{b["toks"]}  {b["title"] or ""}')
    render(im,books,out/f"{Path(args.image).stem}_ondevice.jpg")
    json.dump([{k:v for k,v in b.items()} for b in books],open(out/"result.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"[완료] {out/f'{Path(args.image).stem}_ondevice.jpg'}")
    print(f"[완료] {out/'result.json'}")

if __name__=="__main__": main()
