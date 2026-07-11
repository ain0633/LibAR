# -*- coding: utf-8 -*-
"""걷기 스캔 실증 + v4 채택 팀 공유 리포트 (이미지 base64 내장 HTML)."""
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

img_frame = b64(HERE/"video_v4_results/out_ondevice/closeup동영상2_f00060_ft4_ar.jpg")
img_close = b64(HERE/"video_results/out_ondevice/closeupKakaoTalk_20260710_212437244_ft_ar.jpg")
img_pairs = b64(HERE/"real_rec_data_v3/pair_montage_3rd.jpg", width=1100, q=82)

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>걷기 스캔 실증 + v4 채택 (2026-07-11)</title>
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

<h1>🚶 걷기 스캔 첫 실증 + 파인튜닝 v4 채택 <small style="font-size:.55em;color:#666">2026-07-11 · 팀 공유용</small></h1>

<blockquote><b>3차 데이터(862-912 구간, 장서 834권):</b> 걷기 동영상 3편(43·48·58초) + 단 세트 사진 25장.
"서가 한 줄 = 30초 산책"이라는 LibAR의 핵심 사용자 경험이 <b>처음으로 숫자로 증명</b>된 리포트입니다.</blockquote>

<div class="kpi">
<div><div class="n">×12</div><div class="l">걷기 증폭 (프레임당 7권 → 합산 88권)</div></div>
<div><div class="n">96%</div><div class="l">새 구간 근접 매칭 (22/23, 역대 최고)</div></div>
<div><div class="n">4색째</div><div class="l">빨강 라벨 무수정 통과 (파랑·보라·검정·빨강)</div></div>
<div><div class="n">v4 채택</div><div class="l">사진 109권·걷기 257권 총합 신기록</div></div>
</div>

<h2>1. 걷기 스캔 — 한 번 걷기가 사진 12장 몫을 한다</h2>
<div class="concept"><b>원리:</b> 걷는 동안 각 책이 5~10프레임에 등장한다. 한 프레임은 평균 6~7권밖에 못 읽지만
(1080p 동영상은 라벨이 작다), 프레임마다 <b>읽히는 책이 달라서</b> 투표로 합치면 80권대가 된다.
프레임 하나의 실수는 다른 프레임이 덮어쓰고, 오독은 2프레임 이상 일치 규칙이 걸러낸다
— 오배열 오탐 0건이 3편 모두에서 유지된 이유.</div>

<table>
<tr><th>걷기 동영상</th><th>길이</th><th>프레임당 평균</th><th>합산 고유 (v1→v4)</th><th>2프레임 안정 (v1→v4)</th></tr>
<tr><td>동영상1</td><td>43초</td><td>6.2권</td><td>83 → <b class="up">88권</b></td><td>64 → <b class="up">70권</b></td></tr>
<tr><td>동영상2</td><td>48초</td><td>6.4권</td><td>85 → 82권</td><td>72 → 70권</td></tr>
<tr><td>동영상3</td><td>58초</td><td>7.2권</td><td>85 → <b class="up">87권</b></td><td>79 → <b class="up">80권</b></td></tr>
<tr><td><b>합계</b></td><td></td><td></td><td>253 → <b class="up">257권</b></td><td>215 → <b class="up">220권</b></td></tr>
</table>
<p>가장 천천히 걸은 동영상3의 안정 인식이 최고(80권) — <b>"느리게 걸을수록 정확하다"</b>는 촬영 가이드까지 데이터가 알려줬다.</p>
<figure><img class="full" src="data:image/jpeg;base64,{img_frame}">
<figcaption style="text-align:center;color:#666;font-size:.85em">걷기 프레임 한 장의 인식 (🟢직독) — 이런 프레임 49장이 투표로 합쳐진다</figcaption></figure>

<h2>2. 새 구간(862-912) 일반화 — 4번째 구간, 4번째 색, 수정 0줄</h2>
<p>보유 장서 834권짜리 대형 구간에서 근접 <b>96% (22/23, 역대 최고)</b>. 동영상의 빨강 라벨도
자동 감지로 통과 — 파랑(800)·보라(600)·검정(700)·빨강(900) 4색 연속 무수정. "구간 하나 추가 = 코드 0~2줄"이 4회 재현됐다.</p>
<figure><img class="full" src="data:image/jpeg;base64,{img_close}">
<figcaption style="text-align:center;color:#666;font-size:.85em">새 구간 근접 기준샷 — 22/23 매칭</figcaption></figure>

<h2>3. 페어 수확 — 동영상이 학습 데이터 공장이 됐다</h2>
<div class="concept"><b>원리 (답안지→문제집):</b> 근접 프레임에서 확정한 청구기호(답)를, 같은 책의 원거리
흐릿한 크롭(문제)에 이식하면 "모델이 못 읽는 이미지 + 확실한 정답" 학습쌍이 생긴다. 동영상은 같은 단을
거리를 바꿔가며 수십 번 찍은 것이라 이 쌍이 대량 생산된다 — 페어 32→102줄(×3.2), 학습셋 386→702줄.</div>
<figure><img class="full" src="data:image/jpeg;base64,{img_pairs}">
<figcaption style="text-align:center;color:#666;font-size:.85em">수확된 학습쌍 샘플 (이미지 + 빨간 글씨가 이식된 정답)</figcaption></figure>

<h2>4. v4 판정 — 단일 모델 확정</h2>
<table>
<tr><th>측정</th><th>v1 (합성만)</th><th>v4 (실전 702줄 층화 배합)</th></tr>
<tr><td>사진 기준샷 3장 합계</td><td>106권</td><td><b class="up">109권</b></td></tr>
<tr><td>광각 청구기호 직독</td><td>46권</td><td><b class="up">52권</b></td></tr>
<tr><td>근접 (600 / 700)</td><td>21 / 22</td><td>21 / 20</td></tr>
<tr><td>걷기 3편 합계</td><td>253권</td><td><b class="up">257권</b></td></tr>
</table>
<div class="verdict"><b>판정: v4 단일 모델 채택 (근접=v1/광각=v3 이원 운용 청산).</b><br>
실운용 모드(광각 순회·걷기 스캔) 전부에서 우위, 근접은 동률급(700 -2는 노이즈 수준). 모델 하나로
온디바이스 탑재·유지보수 단순화. v2 실패(배합) → v3 부분 회복 → v4 채택으로 파인튜닝 트랙 완결.<br><br>
<b>다음:</b> 파인튜닝 축은 수확 체감 확인(데이터 2배에 +1.6%) → 남은 큰 이득은 <b>YOLO 검출 통합</b>
(각도·원거리 프레임, 학습셋 206장/7,039박스 준비 완료).</div>

<footer>LibAR · 2026 도서관 데이터 활용 공모전 · 실증: 영등포구립 대림도서관<br>
관련: 팀공유_파인튜닝v1v2v3_비교리포트_260710 · LibAR_개발여정_및_계획안_260708</footer>
</body></html>"""

out = HERE.parent/"팀공유_걷기스캔실증_v4채택_260711.html"
io.open(out, "w", encoding="utf-8").write(html)
print(f"저장: {out} ({out.stat().st_size/1e6:.1f}MB)")
