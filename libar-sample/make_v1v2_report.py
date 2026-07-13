# -*- coding: utf-8 -*-
"""파인튜닝 v1/v2/v3 3세대 비교 리포트 (AR 이미지 base64 내장 HTML) 생성."""
import base64, io, sys
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

def b64(path, width=1200, q=68):
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), 1)
    h, w = im.shape[:2]
    if w > width: im = cv2.resize(im, (width, int(h*width/w)))
    return base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1]).decode()

# (이름, [v1 base, v2 base, v3 base], [v1, v2, v3 수치])
P = [
 ("① 800번대 광각 (서가 3m · 슬롯 140)",
  ["daelim_v3_results/out_ondevice/closeupKakaoTalk_20260707_135237882_ft",
   "out_ondevice/closeupKakaoTalk_20260707_135237882_ft2",
   "out_ondevice/closeupKakaoTalk_20260707_135237882_ft3"],
  [dict(직독=46, 복구=17, 계=63, 오배열=4), dict(직독=47, 복구=18, 계=65, 오배열=5), dict(직독=46, 복구=19, 계=65, 오배열=4)]),
 ("② 600번대 근접 (보라 라벨 · 26권)",
  ["out_ondevice/closeupKakaoTalk_20260708_163804413_ft",
   "out_ondevice/closeupKakaoTalk_20260708_163804413_ft2",
   "out_ondevice/closeupKakaoTalk_20260708_163804413_ft3"],
  [dict(직독=20, 복구=1, 계=21, 오배열=0), dict(직독=17, 복구=3, 계=20, 오배열=0), dict(직독=17, 복구=4, 계=21, 오배열=0)]),
 ("③ 700번대 근접 (검정 라벨 · 27권)",
  ["out_ondevice/closeupKakaoTalk_20260708_164051931_ft",
   "out_ondevice/closeupKakaoTalk_20260708_164051931_ft2",
   "out_ondevice/closeupKakaoTalk_20260708_164051931_ft3"],
  [dict(직독=20, 복구=2, 계=22, 오배열=0), dict(직독=16, 복구=3, 계=19, 오배열=0), dict(직독=18, 복구=1, 계=19, 오배열=0)]),
]

DESC = {0: "v1 (합성 5,883장)", 1: "v2 (+실전 354장 ×8)", 2: "v3 (+페어 386장 · 층화 배합)"}

secs = []
for name, bases, nums in P:
    rows = ""
    for i, n in enumerate(nums):
        b = f"<b>{n['계']}</b>"
        rows += f"<tr><td><b>{DESC[i]}</b></td><td>{n['직독']}</td><td>{n['복구']}</td><td>{b}</td><td>{n['오배열']}</td></tr>\n"
    figs = "".join(
        f'<figure><figcaption>v{i+1}</figcaption><img src="data:image/jpeg;base64,{b64(HERE/(bs+"_ar.jpg"))}"></figure>'
        for i, bs in enumerate(bases))
    secs.append(f"""
<h2>{name} <small>— v1 {nums[0]["계"]} → v2 {nums[1]["계"]} → v3 {nums[2]["계"]}권</small></h2>
<table class="num">
<tr><th></th><th>청구기호 직독</th><th>제목 복구</th><th>매칭 계</th><th>오배열 의심</th></tr>
{rows}</table>
<div class="pair">{figs}</div>""")

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>파인튜닝 v1·v2·v3 3세대 비교 리포트 (2026-07-10)</title>
<style>
body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;max-width:1280px;margin:0 auto;
     padding:24px 20px;color:#222;line-height:1.7;background:#fafafa}}
h1{{font-size:1.6em;border-bottom:3px solid #2b6cb0;padding-bottom:8px}}
h2{{font-size:1.2em;margin-top:2em;border-left:5px solid #2b6cb0;padding-left:12px}}
h2 small{{font-weight:normal;color:#555;font-size:.8em}}
blockquote{{background:#eef4fb;border-left:4px solid #2b6cb0;margin:12px 0;padding:12px 16px;border-radius:0 6px 6px 0}}
table{{border-collapse:collapse;margin:10px 0;background:#fff;font-size:.93em}}
th,td{{border:1px solid #d0d7de;padding:6px 12px;text-align:center}}
th{{background:#f0f4f8}}
table.num td:first-child{{text-align:left}}
.up{{color:#188038;font-weight:bold}} .dn{{color:#d33;font-weight:bold}}
.pair{{display:flex;gap:8px;margin:10px 0}}
.pair figure{{flex:1;margin:0}}
.pair img{{width:100%;border:1px solid #ccc;border-radius:6px}}
.pair figcaption{{font-weight:bold;text-align:center;padding:3px;background:#e8eef5;border-radius:6px 6px 0 0}}
.verdict{{background:#fdf6ec;border-left:4px solid #d69e2e;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0}}
footer{{margin-top:2.5em;font-size:.85em;color:#777;border-top:1px solid #ddd;padding-top:10px}}
</style></head><body>

<h1>📚 LibAR 파인튜닝 3세대 비교 (v1·v2·v3) <small style="font-size:.55em;color:#666">2026-07-10 · 팀 공유용</small></h1>

<blockquote><b>실험 흐름:</b> v1(합성 저해상 5,883장) → v2(+실전 수확 354장을 일괄 8배 오버샘플)
→ v3(+페어 이식 32장 포함 386장을 <b>근접 6배·저해상 2배·페어 6배로 층화 배합</b>).
페어 = 같은 단의 근접샷(답안지)에서 확정한 정답을 광각샷(문제집)의 흐릿한 크롭에 이식한 것.<br>
박스 색: 🟢 청구기호 직독 · 🔵 제목으로 복구 · 🔴 오배열 의심 · ⚪ 미인식</blockquote>

<table class="num">
<tr><th>기준샷</th><th>v1</th><th>v2</th><th>v3</th><th>판독</th></tr>
<tr><td>800번대 광각 (140슬롯)</td><td>63권</td><td>65권</td><td><b>65권</b></td><td><span class="up">광각 +2 유지</span></td></tr>
<tr><td>600번대 근접 (26권)</td><td>21권</td><td>20권</td><td><b>21권</b></td><td><span class="up">v1 수준 회복</span></td></tr>
<tr><td>700번대 근접 (27권)</td><td>22권</td><td>19권</td><td>19권</td><td><span class="dn">-3 잔존</span> (직독은 16→18 회복)</td></tr>
</table>

<div class="verdict"><b>판정: v3는 v2의 상위 호환 — 그러나 종합 1위는 여전히 v1.</b><br>
층화 배합이 방향대로 작동해 600 근접을 회복시키고 700 직독도 +2 되돌렸지만, 700 계는 -3 잔존.
잔존 원인 추정: 근접 태그 안에 <b>훼손 라벨 hard 샘플(제목복구 74줄)</b>이 섞여 함께 6배 오버샘플됨
→ "선명해도 넘겨짚는" 버릇 일부 잔존 (Colab 분리평가 val_close 14%가 그 신호).<br><br>
<b>운용 결정:</b> ① 근접(걷기 스캔) 모드 = v1 · 광각(순회) 모드 = v3 이원 운용 (이원화 구조라 교체 비용 한 줄)
② v4는 걷기 동영상·3컷 세트 등 새 데이터 도착 후 — 태그를 해상도×훼손여부×페어 3축으로 분리해 배합.
③ 파인튜닝 축은 수확 체감 — 다음 메인 작업은 <b>YOLO 검출 통합</b> (각도·광각 프레임 3~25%가 최대 구멍이자
페어 수확량의 병목).</div>
{"".join(secs)}

<h2>참고 — 실험 방법의 신뢰성</h2>
<p>모델 세대별 OCR 토큰 캐시 분리(<code>_ft</code>/<code>_ft2</code>/<code>_ft3</code>)로 교차 오염 차단.
밴드 검출·매칭 로직·카탈로그는 3세대 완전 동일 조건. v3 학습은 Colab T4 20 epochs,
평가는 실전 크롭을 근접/저해상으로 분리 채점해 베스트 선택.</p>

<footer>LibAR · 2026 도서관 데이터 활용 공모전 · 실증: 영등포구립 대림도서관<br>
관련 문서: LibAR_개발여정_및_계획안_260708.html · 팀공유_근접vs광각_비교리포트_260708.html</footer>
</body></html>"""

out = HERE.parent/"팀공유_파인튜닝v1v2v3_비교리포트_260710.html"
io.open(out, "w", encoding="utf-8").write(html)
print(f"저장: {out} ({out.stat().st_size/1e6:.1f}MB)")
