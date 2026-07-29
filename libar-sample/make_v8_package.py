# -*- coding: utf-8 -*-
"""v8 학습 패키지: 원샷 고해상 시대(0718~) 재료만 — human(오늘 라벨) + order(순서 추론 100% 게이트).
v5~v7 3연속 기각의 결론(48px 정보 한계) 이후 첫 재도전 — 재료가 중간 블러 대역이라 판이 다르다.
사용: py -3.12 make_v8_package.py
"""
import io, json, ast, random, shutil, zipfile
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DST = HERE / "real_rec_data_v8"
(DST / "crops").mkdir(parents=True, exist_ok=True)
SINCE = 1784350000000

# ── 1) 재료 수집: human(오늘분만) + order(전부 오늘분) ──
rows = []
for src, meta in [("real_rec_data_human", "meta_human.txt"), ("real_rec_data_order", "meta_order.txt")]:
    for l in io.open(HERE / src / meta, encoding="utf-8").read().splitlines():
        if not l.strip(): continue
        f, gt, tag = l.split("\t")
        if int(f.split("/")[1].split("_")[0]) < SINCE: continue
        shutil.copy(HERE / src / f, DST / f)
        rows.append((f, gt, tag))
print(f"[재료] {len(rows)}줄 (human {sum(1 for r in rows if r[2]=='human')} + order {sum(1 for r in rows if r[2]=='order')})")

# ── 2) GT 단위 train/val 분리 (val ~20% = 원샷 시대의 공정 현장 평가셋) ──
by_gt = defaultdict(list)
for r in rows: by_gt[r[1]].append(r)
gts = sorted(by_gt)
random.seed(28)
random.shuffle(gts)
val_gts, val_n = [], 0
for g in gts:
    if val_n >= len(rows) * 0.2: break
    val_gts.append(g); val_n += len(by_gt[g])
val_set = set(val_gts)
tr = [r for g in gts if g not in val_set for r in by_gt[g]]
va = [r for g in val_gts for r in by_gt[g]]
for name, part in [("meta_v8_train.txt", tr), ("meta_v8_val.txt", va)]:
    io.open(DST / name, "w", encoding="utf-8").write("\n".join("\t".join(r) for r in part) + "\n")
print(f"[분리] train {len(tr)}줄({len(gts)-len(val_gts)}책) / val {len(va)}줄({len(val_gts)}책)")

# ── 3) zip ──
zp = HERE / "real_rec_data_v8.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(DST.rglob("*")):
        if p.is_file(): z.write(p, f"real_rec_data_v8/{p.relative_to(DST)}")
print(f"[zip] {zp.name} {zp.stat().st_size//1024}KB")

# ── 4) 노트북: v7 복제 + 치환 ──
nb = json.load(io.open(HERE / "ocr_finetune7_colab.ipynb", encoding="utf-8"))
NL = chr(10)
nb["cells"][0]["source"] = [ln + NL for ln in f"""# 8차 파인튜닝 (v8) — 원샷 고해상 현장 조각 첫 투입
**v5~v7 3연속 기각의 결론 = 48px 저해상 조각은 정보 한계 밖.** v8은 재료가 다르다:
A안(고해상 원샷+크롭 패딩, 07-17 배포) 이후 수집분 — 조각 높이 중앙값 66→**257px(4배)**, 중간 블러(학습 유효) 대역.

**재료 {len(rows)}줄**: human(사람 라벨 {sum(1 for r in rows if r[2]=='human')}) + order(서가 순서 추론 {sum(1 for r in rows if r[2]=='order')} — 위치+카탈로그 유일 후보 게이트, LOO 정밀도 100%). 둘 다 모델 독립 GT.
**val {len(va)}줄 = 원샷 시대의 공정 현장 평가셋.** 채택: val 상승 + close/low 유지 → 로컬 A/B 통과.
**업로드:** `synth_rec.zip` + `real_rec_data_v3.zip` + `real_rec_data_v8.zip` (3개) · GPU(T4) · 셀1 후 세션 재시작""".splitlines()]

def swap(i, pairs):
    src = "".join(nb["cells"][i]["source"])
    for a, b in pairs:
        assert a in src, f"셀{i}에 '{a}' 없음"
        src = src.replace(a, b)
    nb["cells"][i]["source"] = [ln + NL for ln in src.splitlines()]

swap(2, [("real_rec_data_human.zip", "real_rec_data_v8.zip"),
         ("real_rec_data_human/", "real_rec_data_v8/"),
         ("meta_human_train.txt", "meta_v8_train.txt"),
         ("meta_human_val.txt", "meta_v8_val.txt"),
         ("'human': 3", "'human': 3, 'order': 3"),
         ("train_v7.txt", "train_v8.txt")])
swap(4, [("korean_lowres_v7", "korean_lowres_v8"), ("train_v7.txt", "train_v8.txt")])
swap(5, [("korean_lowres_v7", "korean_lowres_v8")])
swap(6, [("korean_lowres_v7", "korean_lowres_v8")])

for c in nb["cells"]:
    if c["cell_type"] != "code": continue
    ast.parse("".join(l for l in ("".join(c["source"])).splitlines(True)
                      if not l.lstrip().startswith(("!", "%"))))
out = HERE / "ocr_finetune8_colab.ipynb"
json.dump(nb, io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[노트북] {out.name} — 전 셀 ast 통과")
