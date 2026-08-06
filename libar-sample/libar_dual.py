# -*- coding: utf-8 -*-
"""LibAR 이중 인식 데모 v2 — 청구기호(라벨)+제목 동시 인식, 둘 다 박스 표시
  · call_label: 2클래스 검출기 박스 (하단, 빨강/상태색)
  · title: 라벨 위 세로 기둥(실제 제목 위치)을 title 영역으로 (상단, 파랑)
  · 속도: 제목 크롭을 축소 후 OCR (큰 크롭이 병목이었음). call/title 패스 시간 분리 측정
"""
import os,sys,time,json,difflib,unicodedata,re
os.environ["FLAGS_use_mkldnn"]="0"
import cv2,numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
import libar_ondevice as L
if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")

def ntitle(s): return re.sub(r"[^0-9A-Za-z가-힣]","",unicodedata.normalize("NFC",str(s))).lower()
def match_title(text, catalog, thr=0.45):
    t=ntitle(text)
    if len(t)<2: return None,0.0
    best,bs=None,0.0
    for r in catalog:
        c=ntitle(r["title"])
        if not c: continue
        lm=difflib.SequenceMatcher(None,t,c).find_longest_match(0,len(t),0,len(c))
        p=lm.size/min(len(t),len(c)) if min(len(t),len(c)) else 0
        s=0.6*p+0.4*difflib.SequenceMatcher(None,t,c).ratio()
        if s>bs: best,bs=r,s
    return (best,round(bs,2)) if bs>=thr else (None,round(bs,2))

def read_scaled(ocr, crop, maxside=1100):
    """긴 변을 maxside로 축소 후 OCR (큰 제목 크롭 속도 대폭↓)."""
    if crop.size==0: return ""
    h,w=crop.shape[:2]; s=maxside/max(h,w)
    if s<1: crop=cv2.resize(crop,(int(w*s),int(h*s)),interpolation=cv2.INTER_AREA)
    res=ocr.predict(crop)
    return "".join(res[0].get("rec_texts",[])) if res else ""

def main():
    catalog=L.load_catalog("books_4558.csv"); shared=L.shared_prefix(catalog)
    im=Image.open("shelf_4558.jpg").convert("RGB"); bgr=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR); H,W=bgr.shape[:2]
    m=YOLO("best.pt"); r=m.predict(bgr,conf=0.5,iou=0.45,agnostic_nms=True,verbose=False)[0]
    labs=sorted([[int(v) for v in b.xyxy[0].tolist()] for b in r.boxes if m.names[int(b.cls)]=="call_label"],
                key=lambda b:(b[0]+b[2])/2)
    print(f"[검출] call_label {len(labs)}권")
    from paddleocr import PaddleOCR
    ocr=PaddleOCR(lang="korean",enable_mkldnn=False,use_doc_orientation_classify=False,
                  use_doc_unwarping=False,use_textline_orientation=False)
    ytop=int(H*0.36)
    books=[]
    # ── 패스1: 청구기호(작은 라벨 크롭) ──
    t1=time.time()
    for b in labs:
        x0,y0,x1,y1=b; py=int((y1-y0)*0.15); px=int((x1-x0)*0.05)
        books.append({"box":b,"ctoks":L.read_label(ocr,bgr[max(0,y0-py):min(H,y1+py),max(0,x0-px):x1+px])})
    t_call=time.time()-t1
    # ── 패스2: 제목(라벨 위 세로기둥, 좁게+축소) ──
    t2=time.time()
    for bk in books:
        x0,y0,x1,y1=bk["box"]; cw=x1-x0; cx=(x0+x1)//2
        tx0=cx-int(cw*0.35); tx1=cx+int(cw*0.35)   # 좁게 → 옆 책 겹침↓
        ty1=y0-int((y1-y0)*0.4)
        tbox=[tx0,ytop,tx1,max(ytop+10,ty1)]; bk["tbox"]=tbox
        tc=bgr[tbox[1]:tbox[3], max(0,tx0):tx1]
        if tc.size: tc=cv2.rotate(tc,cv2.ROTATE_90_COUNTERCLOCKWISE)
        bk["ttext"]=read_scaled(ocr,tc)
    t_title=time.time()-t2
    print(f"[청구기호 OCR] {len(labs)}권 → {t_call:.0f}s ({t_call/len(labs):.1f}s/권)")
    print(f"[제목 OCR(축소)] {len(labs)}권 → {t_title:.0f}s ({t_title/len(labs):.1f}s/권)")

    for bk in books:
        crow,_=L.match_tokens(bk["ctoks"],catalog,shared)
        trow,_=match_title(bk["ttext"],catalog)
        if crow and trow and crow["call_number"]==trow["call_number"]: row=crow; how="이중확정✓"
        elif crow: row=crow; how="청구기호"
        elif trow: row=trow; how="제목복구"
        else: row=None; how="미인식"
        bk.update(call=row["call_number"] if row else None,title=row["title"] if row else None,
                  order=row["_order"] if row else None,how=how)
    matched=[b for b in books if b["call"]]
    mis=L.lis_misplaced([b["order"] for b in matched])
    for b in books: b["status"]="unknown" if b["call"] is None else "ok"
    for i,b in enumerate(matched):
        if i in mis: b["status"]="misplaced"
    n_ok=sum(b["status"]=="ok" for b in books); n_mis=sum(b["status"]=="misplaced" for b in books)
    n_dual=sum(b["how"]=="이중확정✓" for b in books)
    print(f"\n[결과] 인식 {len(matched)}/{len(books)} · 정상 {n_ok} · 오배열 {n_mis} · 이중확정 {n_dual}")

    COL={"ok":(40,190,90),"misplaced":(235,60,60),"unknown":(150,150,150)}
    d=ImageDraw.Draw(im,"RGBA")
    fb=ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf",30); bf=ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf",42)
    for b in books:
        c=COL[b["status"]]; x0,y0,x1,y1=b["box"]; tx0,ty0,tx1,ty1=b["tbox"]
        d.rectangle([tx0,ty0,tx1,ty1],outline=(50,130,240,255),width=3)          # 제목=파랑
        d.rectangle([x0,y0,x1,y1],outline=c+(255,),width=5 if b["status"]=="misplaced" else 3)  # 청구기호=상태색
        if b["status"]=="misplaced": d.rectangle([x0,y0,x1,y1],fill=c+(70,))
        tag=b["call"].split("-")[-1] if b["call"] else "?"
        d.rectangle([x0,y0-40,x0+62,y0-2],fill=c+(235,)); d.text((x0+4,y0-38),tag,font=fb,fill=(255,255,255,255))
    d.rectangle([0,0,W,150],fill=(20,30,60,235))
    d.text((40,24),f"LibAR 이중 인식  |  파랑=제목영역 · 초록/빨강=청구기호  |  정상 {n_ok}·오배열 {n_mis}·이중확정 {n_dual}",font=bf,fill=(255,255,255,255))
    d.text((40,86),f"속도(CPU): 청구기호 {t_call:.0f}s + 제목 {t_title:.0f}s = {t_call+t_title:.0f}s",font=fb,fill=(180,210,255,255))
    Path("out_ondevice").mkdir(exist_ok=True); im.save("out_ondevice/shelf_4558_dual.jpg",quality=86)
    print("[완료] out_ondevice/shelf_4558_dual.jpg")

if __name__=="__main__": main()
