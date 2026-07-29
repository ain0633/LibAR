# -*- coding: utf-8 -*-
"""v7 학습 패키지: human 트랙(사람 정답 = 모델 독립 GT) GT 단위 분리 → zip → 노트북(v6 복제+치환).
val_human = 최초의 편향 없는 현장 평가셋 (v6까지의 field val은 v4 선택 편향).
사용: py -3.12 make_v7_package.py
"""
import io, json, ast, random, zipfile
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
SRC = HERE / "real_rec_data_human"

# ── 1) GT 단위 train/val 분리 (val ~20% — 공정 평가셋 몫을 v6의 15%보다 키움) ──
rows = [l.split("\t") for l in io.open(SRC / "meta_human.txt", encoding="utf-8").read().splitlines() if l.strip()]
by_gt = defaultdict(list)
for f, gt, tag in rows:
    by_gt[gt].append((f, gt, tag))
gts = sorted(by_gt)
random.seed(27)
random.shuffle(gts)
val_gts, val_n = [], 0
for g in gts:
    if val_n >= len(rows) * 0.2: break
    val_gts.append(g); val_n += len(by_gt[g])
val_set = set(val_gts)
tr = [r for g in gts if g not in val_set for r in by_gt[g]]
va = [r for g in val_gts for r in by_gt[g]]
for name, part in [("meta_human_train.txt", tr), ("meta_human_val.txt", va)]:
    io.open(SRC / name, "w", encoding="utf-8").write("\n".join("\t".join(r) for r in part) + "\n")
print(f"[분리] train {len(tr)}줄({len(gts)-len(val_gts)}책) / val {len(va)}줄({len(val_gts)}책)")

# ── 2) zip ──
zp = HERE / "real_rec_data_human.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(SRC.rglob("*")):
        if p.is_file() and p.name not in ("meta_human.txt", "hard_negatives.txt"):
            z.write(p, f"real_rec_data_human/{p.relative_to(SRC)}")
print(f"[zip] {zp.name} {zp.stat().st_size//1024}KB")

# ── 3) 노트북: v6 복제 + 치환 ──
nb = json.load(io.open(HERE / "ocr_finetune6_colab.ipynb", encoding="utf-8"))
NL = chr(10)
nb["cells"][0]["source"] = [ln + NL for ln in f"""# 7차 파인튜닝 (v7) — 사람 라벨(human) 트랙 첫 투입
**v5·v6 연속 기각의 원인 = 소급 매칭의 선택 편향** (모델이 이미 읽는 조각만 GT를 얻음 → 새 정보 0).
v7 재료는 **사람 눈이 정답을 붙인 {len(rows)}줄** — 모델과 독립이라 "모델은 못 읽고 사람은 읽는" 진짜 새 교재.
병합 게이트: 권차 줄 제외·복본 꼬리 제거·숫자줄↔저자GT 오배정 차단·소수점 미노출 분류 GT 금지 (육안 재점검 완료).

**val_human {len(va)}줄 = 최초의 편향 없는 현장 평가셋** (배치가 v4 실패 조각 위주라 v4에게 불리한 시험지 — 상승 여력 측정용).
**채택 기준:** human val 상승 + close/low 유지 → 이후 로컬 A/B(골든·autotest 재채점) 통과.
**업로드:** `synth_rec.zip` + `real_rec_data_v3.zip` + `real_rec_data_human.zip` (3개) · GPU(T4) 런타임 · 셀1 후 세션 재시작""".splitlines()]

def swap(i, pairs):
    src = "".join(nb["cells"][i]["source"])
    for a, b in pairs:
        assert a in src, f"셀{i}에 '{a}' 없음"
        src = src.replace(a, b)
    nb["cells"][i]["source"] = [ln + NL for ln in src.splitlines()]

swap(2, [("real_rec_data_field_v6.zip", "real_rec_data_human.zip"),
         ("real_rec_data_field_v6/", "real_rec_data_human/"),
         ("meta_field_train.txt", "meta_human_train.txt"),
         ("meta_field_val.txt", "meta_human_val.txt"),
         ("'field': 3", "'human': 3"),
         ("va = {'close': [], 'low': [], 'field': []}", "va = {'close': [], 'low': [], 'human': []}"),
         ("va['field']", "va['human']"),
         ("train_v6.txt", "train_v7.txt")])
swap(4, [("korean_lowres_v6", "korean_lowres_v7"), ("train_v6.txt", "train_v7.txt")])
swap(5, [("korean_lowres_v6", "korean_lowres_v7"), ("val_field", "val_human"),
         ("close/low/field", "close/low/human"), ("field가 오르고", "human이 오르고")])
swap(6, [("korean_lowres_v6", "korean_lowres_v7")])

for c in nb["cells"]:
    if c["cell_type"] != "code": continue
    ast.parse("".join(l for l in ("".join(c["source"])).splitlines(True)
                      if not l.lstrip().startswith(("!", "%"))))
out = HERE / "ocr_finetune7_colab.ipynb"
json.dump(nb, io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[노트북] {out.name} — 전 셀 ast 통과")
