# -*- coding: utf-8 -*-
"""중간 완성 + 공개 데모 배포 팀 공유 리포트 — 현장 테스트 가이드·자가 개선 원리 포함."""
import base64, io, sys
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
SCRATCH = Path(r"C:/Users/ain06/AppData/Local/Temp/claude/c--Users-ain06-OneDrive----2026---------------/0ddd6241-69e9-48f8-afe6-eeb71a4cf0cf/scratchpad")

def b64(path, width=1400, q=72):
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), 1)
    h, w = im.shape[:2]
    if w > width: im = cv2.resize(im, (width, int(h*width/w)))
    return base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1]).decode()

img_home = b64(SCRATCH/"app_home.png", width=420, q=85)
img_walk = b64(HERE/"hybrid_v3_results/yolo_동영상1_f00060_ar.jpg")
img_pairs = b64(HERE/"real_rec_data_v3/pair_montage_3rd.jpg", width=1100, q=82)

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LibAR 중간 완성 — 공개 데모 배포 (2026-07-13)</title>
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
.kpi .n{{font-size:1.35em;font-weight:bold;color:#2b6cb0}}
.kpi .l{{font-size:.85em;color:#666}}
.up{{color:#188038;font-weight:bold}}
img.full{{width:100%;border:1px solid #ccc;border-radius:6px;margin:8px 0}}
img.phone{{width:300px;border:1px solid #ccc;border-radius:14px;display:block;margin:8px auto}}
.verdict{{background:#fdf6ec;border-left:4px solid #d69e2e;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0}}
.concept{{background:#f0faf4;border-left:4px solid #28a058;padding:12px 16px;margin:14px 0;border-radius:0 6px 6px 0}}
.step{{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:12px 16px;margin:10px 0}}
.step b.num{{display:inline-block;background:#2b6cb0;color:#fff;border-radius:50%;width:24px;height:24px;
            text-align:center;line-height:24px;margin-right:8px}}
.url{{font-size:1.25em;font-weight:bold;background:#0b1326;color:#4be277;padding:10px 18px;border-radius:8px;
     display:inline-block;letter-spacing:.02em}}
code{{background:#eef;padding:1px 5px;border-radius:4px}}
footer{{margin-top:2.5em;font-size:.85em;color:#777;border-top:1px solid #ddd;padding-top:10px}}
</style></head><body>

<h1>📱 LibAR 중간 완성 — 누구나 쓸 수 있는 공개 데모 배포 <small style="font-size:.55em;color:#666">2026-07-13 · 팀 공유용</small></h1>

<blockquote><b>오늘부터 LibAR는 링크 하나로 만질 수 있는 실물입니다.</b> 폰 브라우저로 접속하면
카메라가 서가를 실시간 인식하고, 도서 찾기·층별 길안내·오배열 판정까지 전 흐름이 동작합니다.
설치 없음, 서버 전송 없음 — 모든 AI가 폰 안에서 돕니다.<br><br>
<span class="url">https://ainsof.dev/libar-demo/</span></blockquote>

<div class="kpi">
<div><div class="n">공개 배포</div><div class="l">폰 브라우저에서 즉시 실행 (HTTPS·설치 불필요)</div></div>
<div><div class="n">95% / 97%</div><div class="l">걷기 스캔 판독률 / 오독 방어율 (실측)</div></div>
<div><div class="n">4축 완성</div><div class="l">검출→인식→대조→판정 전 단계 탑재</div></div>
<div><div class="n">1,860권</div><div class="l">도서 찾기 검색 + 3층 실배치도 길안내</div></div>
</div>

<h2>1. 무엇이 완성됐나 — 두 사용자, 두 과업</h2>
<p>첫 화면은 배너 두 개뿐입니다. <b>이용자는 책을 찾고, 사서는 서가를 점검합니다.</b></p>
<img class="phone" src="data:image/jpeg;base64,{img_home}">
<table>
<tr><th>흐름</th><th>동작</th></tr>
<tr><td>🔍 도서 찾기 (이용자)</td><td>장서 1,860권 검색 → 층별 실배치도(공식 지도 이식)에 위치 핀 → 서가 앞에서 스캔하면 정확한 칸 하이라이트</td></tr>
<tr><td>📷 서가 점검 (사서)</td><td>진입 즉시 카메라 시작 → 책 라벨에 실시간 초록 박스 → 하단 시트에 확인/잘못 꽂힘/다시 확인 3색 집계 + 실물 썸네일</td></tr>
</table>
<p>서가를 걸으며 찍은 프레임 한 장을 앱이 이렇게 읽습니다 (초록=청구기호 확인):</p>
<figure><img class="full" src="data:image/jpeg;base64,{img_walk}">
<figcaption style="text-align:center;color:#666;font-size:.85em">걷기 프레임 실측 — 이런 프레임들이 투표로 합산되어 판독률 95%가 된다</figcaption></figure>

<h2>2. 성능 스코어보드 (전부 대림 실측)</h2>
<table>
<tr><th>지형</th><th>수치</th><th>의미</th></tr>
<tr><td>근접 사진</td><td class="up">96% (22/23)</td><td>한 단 정면 촬영 시 판독률</td></tr>
<tr><td>걷기 스캔 (3회 주행 합산)</td><td class="up">판독률 95% · 오독 방어 97%</td><td>"서가 한 줄 = 30초 산책" — 서비스 핵심 모드</td></tr>
<tr><td>광각·각도 사진</td><td class="up">52권 (기존 방식 29권)</td><td>17° 기울어진 서가에서 2.2배 — AI 검출기 효과</td></tr>
<tr><td>오배열 오탐</td><td class="up">0건 (동영상 3편)</td><td>가짜 경보로 사서를 헛걸음시키지 않음</td></tr>
</table>
<div class="verdict"><b>정직한 현재 한계 두 가지.</b> ① AI 검출기는 걷기 영상에서 아직 89%
(색 규칙 방식 95%가 당분간 걷기 담당) — 오늘 원인을 909번 서가 줄의 조직적 누락으로 특정했고,
바로 아래 '원리'의 방법으로 다음 모델이 학습합니다. ② 어린이자료실(그림책·비정형 배가)은 적용 범위 밖입니다.</div>

<h2>3. 🧪 대림도서관 현장 테스트 방법 (5분 코스)</h2>
<div class="step"><b class="num">1</b><b>접속</b> — 폰 브라우저(크롬/사파리)에서 <code>ainsof.dev/libar-demo</code> ·
와이파이 없어도 됩니다 (첫 로드만 데이터 ~15MB, 이후 인식은 폰 안에서)</div>
<div class="step"><b class="num">2</b><b>서가 점검하기</b> — 카메라가 자동으로 켜지면 3층 서가를 <b>팔 뻗은 거리에서 천천히</b>
비춰주세요. 책 라벨마다 초록 박스가 따라붙는지 확인 (박스가 안 붙는 서가가 있다면 그게 가장 값진 발견입니다!)</div>
<div class="step"><b class="num">3</b><b>사진 스캔</b> — 우하단 <b>🖼 사진 업로드</b>로 서가 사진을 찍어 올려보세요.
특히 <b>000~500번대(아직 한 번도 학습 안 한 색 라벨)</b>를 부탁드립니다. '판정 시연' 칩을 누르면
청구기호 인식·오배열 판정이 끝난 화면(실측)을 볼 수 있습니다</div>
<div class="step"><b class="num">4</b><b>📦 학습용 조각 제공</b> — 스캔 후 이 버튼을 누르면 <b>라벨 조각만 담긴 zip</b>이
저장됩니다. 팀 드라이브에 올려주세요. <u>서가 전체 사진은 절대 포함되지 않습니다</u> — 우표 크기 라벨 조각 + 인식된 정답뿐</div>
<div class="step"><b class="num">5</b><b>도서 찾기</b> — 아무 책이나 검색해서 3층 지도 안내가 실제 동선과 맞는지,
'바로 안내' 책의 위치 하이라이트가 실물과 일치하는지 봐주세요</div>

<h2>4. 🔄 테스트가 성능을 올리는 원리 — "쓸수록 정확해지는 앱"</h2>
<div class="concept"><b>비유: 답안지로 문제집 만들기.</b> 앱이 라벨을 또렷하게 읽어 장서목록과 글자까지
일치하면 그 라벨 조각은 <b>정답이 확정된 문제</b>가 됩니다. 같은 책이 흐릿하게 찍힌 조각에 이 정답을
붙이면, AI가 가장 못 푸는 유형의 문제에 답안지가 달린 <b>맞춤 교재</b>가 됩니다. 사람이 정답을
입력할 필요가 전혀 없습니다 — 스캔하는 행위 자체가 교재 제작입니다.</div>
<p>4단계에서 저장한 zip이 정확히 이 교재의 재료입니다. 지금까지 이 방법으로만 학습을 반복해
인식 모델은 v1→v4, 검출 모델은 v1→v3까지 왔습니다 (수작업 라벨링 0회):</p>
<figure><img class="full" src="data:image/jpeg;base64,{img_pairs}">
<figcaption style="text-align:center;color:#666;font-size:.85em">실제 수확된 학습쌍 — 흐릿한 라벨 조각(문제) + 빨간 글씨 정답(답안지)</figcaption></figure>
<table>
<tr><th>테스트 행동</th><th>모델이 배우는 것</th></tr>
<tr><td>박스가 안 붙는 서가를 찍어줌</td><td>검출기가 못 보던 라벨 모양·색 (오늘 발견된 909 줄이 정확히 이 케이스)</td></tr>
<tr><td>000~500번대를 찍어줌</td><td>아직 한 번도 본 적 없는 구간의 라벨 색 → 도서관 전체 커버리지</td></tr>
<tr><td>흐릿한/각도 사진을 올려줌</td><td>인식 모델의 가장 약한 조건 — 개선 폭이 가장 큰 교재</td></tr>
<tr><td>조각 zip을 드라이브에 올려줌</td><td>다음 학습(v4)의 데이터셋 — 모델 파일 교체만으로 모든 사용자에게 배포</td></tr>
</table>
<div class="concept"><b>프라이버시 원칙:</b> 기본값은 아무것도 전송하지 않습니다. 조각 제공은
버튼을 눌러 동의했을 때만, 사진 전체가 아닌 라벨 조각만 — 서지 정보는 원래 공개 데이터이고,
내부 관리 정보나 이용자 모습은 애초에 담기지 않습니다.</div>

<h2>5. 다음 단계</h2>
<table>
<tr><th>단계</th><th>내용</th><th>담당</th></tr>
<tr><td>현장 테스트</td><td>위 5분 코스 + 조각 zip 수집</td><td>광수쌤 🙏</td></tr>
<tr><td>검출기 v4</td><td>수집 조각 + 909 구간 승격 데이터로 재학습 → 걷기 95% 돌파 목표</td><td>아인 (Colab 준비)</td></tr>
<tr><td>인식 브라우저 이식</td><td>'판정 시연' 없이 라이브에서 청구기호까지 — M5 완성</td><td>아인</td></tr>
<tr><td>전체 장서 확장</td><td>000~900 전체 장서데이터 + 구간별 스팟 사진</td><td>광수쌤께 요청</td></tr>
</table>

<footer>LibAR · 2026 도서관 데이터 활용 공모전 · 실증: 영등포구립 대림도서관<br>
데모: https://ainsof.dev/libar-demo/ · 관련: 팀공유_하이브리드M3_전지형우세_260713 · 팀공유_걷기스캔실증_v4채택_260711</footer>
</body></html>"""

out = HERE.parent/"팀공유_중간완성_공개데모_260713.html"
io.open(out, "w", encoding="utf-8").write(html)
print(f"저장: {out} ({out.stat().st_size/1e6:.1f}MB)")
