# -*- coding: utf-8 -*-
"""M3 하이브리드(YOLO 검출 × OCR 인식) 전 지형 우세 팀 공유 리포트 (이미지 base64 내장 HTML)."""
import base64, io, sys
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

def b64(path, width=1400, q=72):
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), 1)
    h, w = im.shape[:2]
    if w > width: im = cv2.resize(im, (width, int(h*width/w)))
    return base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1]).decode()

OUT = HERE/"out_ondevice"
img_hy_600 = b64(OUT/"yolo_KakaoTalk_20260708_163804413_11_ar.jpg")
img_hy_700 = b64(OUT/"yolo_KakaoTalk_20260708_164051931_10_ar.jpg")
img_he_700 = b64(OUT/"closeupKakaoTalk_20260708_164051931_10_ft_ar.jpg")

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>M3 하이브리드 파이프라인 — 전 지형 우세 (2026-07-13)</title>
<style>
body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;max-width:1100px;margin:0 auto;
     padding:24px 20px;color:#222;line-height:1.7;background:#fafafa}}
h1{{font-size:1.6em;border-bottom:3px solid #2b6cb0;padding-bottom:8px}}
h2{{font-size:1.2em;margin-top:2em;border-left:5px solid #2b6cb0;padding-left:12px}}
blockquote{{background:#eef4fb;border-left:4px solid #2b6cb0;margin:12px 0;padding:12px 16px;border-radius:0 6px 6px 0}}
table{{border-collapse:collapse;margin:10px 0;background:#fff;font-size:.93em}}
th,td{{border:1px solid #d0d7de;padding:6px 12px;text-align:center}}
th{{background:#f0f4f8}}
.kpi{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
.kpi div{{flex:1;min-width:150px;background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:12px;text-align:center}}
.kpi .n{{font-size:1.5em;font-weight:bold;color:#2b6cb0}}
.kpi .l{{font-size:.85em;color:#666}}
.up{{color:#188038;font-weight:bold}}
img.full{{width:100%;border:1px solid #ccc;border-radius:6px;margin:8px 0}}
.verdict{{background:#fdf6ec;border-left:4px solid #d69e2e;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0}}
.concept{{background:#f0faf4;border-left:4px solid #28a058;padding:12px 16px;margin:14px 0;border-radius:0 6px 6px 0}}
footer{{margin-top:2.5em;font-size:.85em;color:#777;border-top:1px solid #ddd;padding-top:10px}}
</style></head><body>

<h1>🎯 M3 하이브리드 파이프라인 — 전 지형 우세 달성 <small style="font-size:.55em;color:#666">2026-07-13 · 팀 공유용</small></h1>

<blockquote><b>두 모델의 분업이 완성됐습니다:</b> YOLO 검출기가 라벨 <b>위치</b>를 찾고, 파인튜닝 OCR이
<b>읽기</b>만 담당하는 하이브리드 파이프라인이 광각·각도 사진 전부에서 기존 휴리스틱 방식을 넘어섰습니다.
특히 <b>17° 기울어진 서가</b>(기존 방식 사실상 실패 지형)에서 2.2배를 기록했습니다.</blockquote>

<div class="kpi">
<div><div class="n">27권</div><div class="l">광각 한 장 최고 기록 (기존 20권, +35%)</div></div>
<div><div class="n">×2.2</div><div class="l">각도 사진 (9 → 20권)</div></div>
<div><div class="n">17°</div><div class="l">서가 기울기 자동 감지·회전 보정</div></div>
<div><div class="n">0회</div><div class="l">검출기 학습 라벨링 수작업 (전자동 수확)</div></div>
</div>

<h2>1. 무엇이 바뀌었나 — "어디에 있나"와 "뭐라고 쓰였나"의 분리</h2>
<div class="concept"><b>원리:</b> 지금까지는 색 규칙(파랑·보라·검정·빨강 밴드)으로 라벨 위치를 추정했다.
색 규칙은 정면 사진에선 강하지만 기울어진 서가·원거리에선 줄 자체를 못 찾는다. 이제
<b>YOLO 검출기(우리 데이터 206장·7,039박스로 자가 학습, 사람 라벨링 0회)</b>가 라벨 박스를 직접 찾고,
박스들의 배열로 <b>줄 기울기를 계산해 이미지를 회전 보정</b>한 뒤 OCR이 읽는다.
각도 사진에서 청구기호 직독이 1권 → 9권이 된 것이 회전 보정의 효과다.</div>

<h2>2. 결과 — 같은 사진, 같은 OCR 모델(v4), 파이프라인만 교체</h2>
<table>
<tr><th rowspan="2">사진</th><th colspan="3">기존 휴리스틱 (색 밴드)</th><th colspan="3">하이브리드 (YOLO+회전보정)</th><th rowspan="2">차이</th></tr>
<tr><th>직독</th><th>제목복구</th><th>최종</th><th>직독</th><th>제목복구</th><th>최종</th></tr>
<tr><td>600_11 광각 (정면)</td><td>11</td><td>9</td><td>20</td><td>12</td><td>15</td><td><b class="up">27권</b></td><td class="up">+7</td></tr>
<tr><td>700_10 각도 (17°)</td><td>1</td><td>8</td><td>9</td><td>9</td><td>11</td><td><b class="up">20권</b></td><td class="up">+11</td></tr>
</table>
<p>주목할 점: 하이브리드는 <b>직독과 제목복구가 동시에 늘었다</b>. 검출 박스가 정확하니 토큰이 제 책에 붙고
(직독↑), 미매칭 박스의 위치도 정확하니 그 위 제목 크롭도 정확해진다(복구↑). 검출 개선 하나가 두 축을 함께 올렸다.</p>

<h2>3. 각도 사진 — 실패 지형이 우세 지형으로</h2>
<figure><img class="full" src="data:image/jpeg;base64,{img_he_700}">
<figcaption style="text-align:center;color:#666;font-size:.85em">기존 휴리스틱: 17° 기울기에서 색 밴드가 무너져 9권 (직독은 단 1권)</figcaption></figure>
<figure><img class="full" src="data:image/jpeg;base64,{img_hy_700}">
<figcaption style="text-align:center;color:#666;font-size:.85em">하이브리드: 같은 사진 20권 (🟢직독 9 + 🔵제목복구 11) — 박스가 기울기를 따라간다</figcaption></figure>

<h2>4. 광각 정면 — 기존 방식의 홈그라운드에서도 +7권</h2>
<figure><img class="full" src="data:image/jpeg;base64,{img_hy_600}">
<figcaption style="text-align:center;color:#666;font-size:.85em">600번대 광각 3단: 27권 매칭 (기존 최고 20권) — 광각 한 장 신기록</figcaption></figure>

<h2>5. 판정과 다음 단계</h2>
<div class="verdict"><b>판정: M3(검출-인식 통합) 실증 완료 — 전 지형(정면·광각·각도)에서 기존 방식 우세.</b><br>
검출기 v2는 재현율 70%로 아직 성장 여지가 크고(라벨링 전자동이라 데이터만 늘리면 됨),
검출이 좋아지면 직독·복구가 함께 오르는 구조가 이번에 확인됐다.<br><br>
<b>남은 과제는 속도:</b> 제목복구가 개발 PC(CPU)에서 미매칭 박스당 1~2.5분 — 광각은 미매칭이 100박스라
사진 한 장에 수 시간이 걸렸다. 크롭 최적화(업스케일 제외·높이 제한)로 박스당 20초 이하가 목표.
참고로 <b>걷기 스캔 실시간 경로는 제목복구를 쓰지 않는다</b>(프레임 투표가 그 역할을 대신) —
제목복구는 최종 결과 화면의 마무리 단계에만 선택 적용.<br><br>
<b>다음:</b> ① 제목복구 속도 수술 → ② 걷기 동영상 3편 하이브리드 재측정 (검출 기반이라
프레임당 인식 수 상승 기대) → ③ 계획안 M3 완료 처리.</div>

<footer>LibAR · 2026 도서관 데이터 활용 공모전 · 실증: 영등포구립 대림도서관<br>
관련: 팀공유_걷기스캔실증_v4채택_260711 · 팀공유_파인튜닝v1v2v3_비교리포트_260710 · LibAR_개발여정_및_계획안_260708</footer>
</body></html>"""

out = HERE.parent/"팀공유_하이브리드M3_전지형우세_260713.html"
io.open(out, "w", encoding="utf-8").write(html)
print(f"저장: {out} ({out.stat().st_size/1e6:.1f}MB)")
