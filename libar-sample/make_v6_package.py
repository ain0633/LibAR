# -*- coding: utf-8 -*-
"""v6 학습 패키지 생성: GT 단위 train/val 분리 → zip → 노트북(v5 복제+치환).
노트북은 json 라운드트립으로만 생성 (Bash 헤어독 경유 금지 — 이스케이프 붕괴 전례).
사용: py -3.12 make_v6_package.py
"""
import io, json, ast, random, zipfile
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
SRC = HERE / "real_rec_data_field_v6"

# ── 1) GT 단위 train/val 분리 (같은 책은 같은 쪽 — 누수 차단) ──
rows = [l.split("\t") for l in io.open(SRC / "meta_field.txt", encoding="utf-8").read().splitlines() if l.strip()]
by_gt = defaultdict(list)
for f, gt, tag in rows:
    by_gt[gt].append((f, gt, tag))
gts = sorted(by_gt)
random.seed(26)
random.shuffle(gts)
val_gts, val_n = [], 0
for g in gts:                                  # val 목표 ~15%줄
    if val_n >= len(rows) * 0.15: break
    val_gts.append(g); val_n += len(by_gt[g])
val_set = set(val_gts)
tr = [r for g in gts if g not in val_set for r in by_gt[g]]
va = [r for g in val_gts for r in by_gt[g]]
for name, part in [("meta_field_train.txt", tr), ("meta_field_val.txt", va)]:
    io.open(SRC / name, "w", encoding="utf-8").write("\n".join("\t".join(r) for r in part) + "\n")
print(f"[분리] train {len(tr)}줄({len(gts)-len(val_gts)}책) / val {len(va)}줄({len(val_gts)}책)")

# ── 2) zip (내부 폴더명 = real_rec_data_field_v6) ──
zp = HERE / "real_rec_data_field_v6.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(SRC.rglob("*")):
        if p.is_file() and p.name != "meta_field.txt":
            z.write(p, f"real_rec_data_field_v6/{p.relative_to(SRC)}")
print(f"[zip] {zp.name} {zp.stat().st_size//1024}KB")

# ── 3) 노트북: v5 복제 + 치환 (셀3의 PP-OCRv5 참조는 건드리지 않는다) ──
nb = json.load(io.open(HERE / "ocr_finetune5_colab.ipynb", encoding="utf-8"))
NL = chr(10)
nb["cells"][0]["source"] = [ln + NL for ln in f"""# 6차 파인튜닝 (v6) — 강화 게이트 현장 조각 {len(rows)}줄
**v5 기각 사후 재도전.** 소급 GT 오염(~10%)을 게이트 3종으로 원천 차단한 재료:
분류번호 완전일치 필수 · 저자 2위 격차 0.1 · 접두 분류쌍(005.13/005.133) 다의성 스킵 — 육안 표본 48/48 무오염.

**v6 변경:** field 학습쌍 137→**{len(tr)}줄**(구간 000~600·900, 700·800은 v3 재료가 담당) · field 가중 **6→3**(v5의 low 퇴화가 과대 가중 탓이라는 진단 반영).
**평가(v5와 동일):** val 3분할 close/low/field — **field가 오르고 close·low가 안 떨어져야 채택.** 로컬 A/B(골든·걷기 재채점) 통과까지가 채택 조건.
**업로드:** `synth_rec.zip` + `real_rec_data_v3.zip` + `real_rec_data_field_v6.zip` (3개) · GPU(T4) 런타임 · 셀1 후 세션 재시작""".splitlines()]

def swap(i, pairs):
    src = "".join(nb["cells"][i]["source"])
    for a, b in pairs:
        assert a in src, f"셀{i}에 '{a}' 없음"
        src = src.replace(a, b)
    nb["cells"][i]["source"] = [ln + NL for ln in src.splitlines()]

swap(2, [("{'close': 6, 'low': 2, 'pair': 4, 'field': 6}", "{'close': 6, 'low': 2, 'pair': 4, 'field': 3}"),
         ("real_rec_data_field.zip", "real_rec_data_field_v6.zip"),
         ("real_rec_data_field/", "real_rec_data_field_v6/"),   # unzip -d 경로·read 경로·상대경로 전부
         ("train_v5.txt", "train_v6.txt"),
         ("# 2) 데이터 업로드(3개) + 층화 배합 — v4 배합에 field 트랙 추가",
          "# 2) 데이터 업로드(3개) + 층화 배합 — v6: 강화 게이트 field, 가중 3")])
swap(4, [("korean_lowres_v5", "korean_lowres_v6"), ("train_v5.txt", "train_v6.txt")])
swap(5, [("korean_lowres_v5", "korean_lowres_v6")])
swap(6, [("korean_lowres_v5", "korean_lowres_v6")])

for i, c in enumerate(nb["cells"]):            # 코드 셀 문법 검증 (매직·셸 라인 제외)
    if c["cell_type"] != "code": continue
    body = "".join(l for l in ("".join(c["source"])).splitlines(True)
                   if not l.lstrip().startswith(("!", "%")))
    ast.parse(body)
out = HERE / "ocr_finetune6_colab.ipynb"
json.dump(nb, io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[노트북] {out.name} — 전 셀 ast 통과")
