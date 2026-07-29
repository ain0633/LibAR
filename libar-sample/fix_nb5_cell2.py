# -*- coding: utf-8 -*-
"""ocr_finetune5_colab.ipynb 셀2 수리 — 생성 시 이스케이프 붕괴로 문자열 안에 실제 줄바꿈 유입.
백슬래시 이스케이프 없는 코드(chr(9)/chr(10))로 교체해 재발 원천 차단."""
import json, io, ast

CELL2 = """# 2) 데이터 업로드(3개) + 층화 배합 — v4 배합에 field 트랙 추가
MIX = {'close': 6, 'low': 2, 'pair': 4, 'field': 6}   # <- 배합 비율 (여기만 바꿔서 재실험)

from google.colab import files
up = files.upload()   # synth_rec.zip, real_rec_data_v3.zip, real_rec_data_field.zip 셋 다 선택
!unzip -oq synth_rec.zip -d PaddleOCR/train_data/
!unzip -oq real_rec_data_v3.zip -d PaddleOCR/train_data/
!unzip -oq real_rec_data_field.zip -d PaddleOCR/train_data/
import io
TAB, NL = chr(9), chr(10)
def read(p): return [l.split(TAB) for l in io.open(p, encoding='utf-8').read().splitlines() if l.strip()]
merged = ['synth_rec/train/' + p + TAB + t for p, t in read('PaddleOCR/train_data/synth_rec/train/rec_gt_train.txt')]
from collections import Counter
used = Counter()
for p, t, g in read('PaddleOCR/train_data/real_rec_data_v3/meta_train.txt'):
    merged += ['real_rec_data_v3/' + p + TAB + t] * MIX.get(g, 1); used[g] += MIX.get(g, 1)
for p, t, g in read('PaddleOCR/train_data/real_rec_data_field/meta_field_train.txt'):
    merged += ['real_rec_data_field/' + p + TAB + t] * MIX.get(g, 1); used[g] += MIX.get(g, 1)
va = {'close': [], 'low': [], 'field': []}
for p, t, g in read('PaddleOCR/train_data/real_rec_data_v3/meta_val.txt'):
    va['close' if g == 'close' else 'low'].append('real_rec_data_v3/' + p + TAB + t)
for p, t, g in read('PaddleOCR/train_data/real_rec_data_field/meta_field_val.txt'):
    va['field'].append('real_rec_data_field/' + p + TAB + t)
io.open('PaddleOCR/train_data/train_v5.txt', 'w', encoding='utf-8').write(NL.join(merged) + NL)
for k, v in va.items():
    io.open('PaddleOCR/train_data/val_' + k + '.txt', 'w', encoding='utf-8').write(NL.join(v) + NL)
io.open('PaddleOCR/train_data/val_all.txt', 'w', encoding='utf-8').write(NL.join(sum(va.values(), [])) + NL)
print('train', len(merged), '줄 · 실전 배합', dict(used))
print('val close', len(va['close']), '/ low', len(va['low']), '/ field', len(va['field']))
"""

nb = json.load(io.open('ocr_finetune5_colab.ipynb', encoding='utf-8'))
nb['cells'][2]['source'] = CELL2.splitlines(keepends=True)
json.dump(nb, io.open('ocr_finetune5_colab.ipynb', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 검증: 모든 코드 셀이 파이썬으로 파싱되는지 (!, %, { } 치환 라인 제외)
for i, c in enumerate(nb['cells']):
    if c['cell_type'] != 'code': continue
    body = '\n'.join(l for l in ''.join(c['source']).split('\n')
                     if not l.lstrip().startswith(('!', '%')))
    body = body.replace('{CFG_REL}', 'X').replace('{name}', 'X')
    try:
        ast.parse(body)
        print(f'셀 {i}: OK')
    except SyntaxError as e:
        print(f'셀 {i}: 구문 오류 — {e}')
