# -*- coding: utf-8 -*-
"""현장 테스트 1일차(07-14) 팀 공유 리포트 — 현장 리포트가 이끈 수정들 + 코랩 모델 판정 2건."""
import base64, io, sys
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

def b64(path, width=1000, q=78):
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), 1)
    h, w = im.shape[:2]
    if w > width: im = cv2.resize(im, (width, int(h*width/w)))
    return base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1]).decode()

img_crops = b64(HERE/"수집조각/_quality_montage.jpg")
img_retro = b64(HERE/"수집조각/_retro_gt_check.jpg")

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>현장 테스트 1일차 — 리포트가 이끈 수정들과 모델 판정 (2026-07-14)</title>
<style>
body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;max-width:1100px;margin:0 auto;
     padding:24px 20px;color:#222;line-height:1.7;background:#fafafa}}
h1{{font-size:1.6em;border-bottom:3px solid #2b6cb0;padding-bottom:8px}}
h2{{font-size:1.2em;margin-top:2em;border-left:5px solid #2b6cb0;padding-left:12px}}
blockquote{{background:#eef4fb;border-left:4px solid #2b6cb0;margin:12px 0;padding:12px 16px;border-radius:0 6px 6px 0}}
table{{border-collapse:collapse;margin:10px 0;background:#fff;font-size:.93em;width:100%}}
th,td{{border:1px solid #d0d7de;padding:6px 12px;text-align:center}}
td.l{{text-align:left}}
th{{background:#f0f4f8}}
.kpi{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
.kpi div{{flex:1;min-width:150px;background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:12px;text-align:center}}
.kpi .n{{font-size:1.5em;font-weight:bold;color:#2b6cb0}}
.kpi .l{{font-size:.85em;color:#666}}
.up{{color:#188038;font-weight:bold}}
.down{{color:#c53030;font-weight:bold}}
img.full{{width:100%;border:1px solid #ccc;border-radius:6px;margin:8px 0}}
.verdict{{background:#fdf6ec;border-left:4px solid #d69e2e;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0}}
.concept{{background:#f0faf4;border-left:4px solid #28a058;padding:12px 16px;margin:14px 0;border-radius:0 6px 6px 0}}
footer{{margin-top:2.5em;font-size:.85em;color:#777;border-top:1px solid #ddd;padding-top:10px}}
</style></head><body>

<h1>🛠 현장 테스트 1일차 — 리포트가 이끈 수정들과 모델 판정 <small style="font-size:.55em;color:#666">2026-07-14 · 팀 공유용</small></h1>

<blockquote><b>오늘 하루의 요약:</b> 광수쌤이 대림 현장에서 앱을 실사용하며 보내주신 리포트 하나하나가
그날 안에 수정·배포로 이어졌습니다(총 10여 회 배포). 그 과정에서 <b>걷기 판독률이 89%→99%로 뛰는
최대 발견</b>(권차 매칭 수술)이 나왔고, 코랩으로 학습한 모델 2개(검출기 v4·인식기 v5)는
같은 잣대로 평가해 <b>둘 다 채택하지 않기로</b> 판정했습니다 — 수치가 좋아질 때만 배포한다는
원칙이 지켜진 하루였습니다. 밤에는 전체 장서 엑셀(20,944권)이 도착해 앱과 학습 파이프라인에 연결됐습니다.</blockquote>

<div class="kpi">
<div><div class="n">89→99%</div><div class="l">걷기 판독률 (권차 매칭 수술)</div></div>
<div><div class="n">3~5초</div><div class="l">수집 모드 (기존 판독 40~50초)</div></div>
<div><div class="n">20,944권</div><div class="l">전체 장서 카탈로그 연결</div></div>
<div><div class="n">335줄</div><div class="l">현장 학습쌍 (77→335, 소급 매칭)</div></div>
</div>

<h2>1. 현장 리포트 → 당일 수정 (아이폰12 미니, 대림 3층)</h2>
<table>
<tr><th>광수쌤 리포트</th><th>원인</th><th>수정 (당일 배포)</th></tr>
<tr><td class="l">"사진 찍으면 '살펴보는 중'에서 안 바뀌어요"</td>
<td class="l">아이폰(크롬도 내부는 사파리 엔진)에서 GPU 세션은 생기는데 실제 추론이 조용히 실패</td>
<td class="l">엔진 업그레이드(ORT 1.27) + 실패 시 CPU 모드 자동 전환 + 오류를 화면에 표시</td></tr>
<tr><td class="l">배터리 8%에서 먹통</td>
<td class="l">저전력 모드가 GPU를 회수 → 모델을 다시 내려받아야 재시작되는 구조</td>
<td class="l">모델 파일(63MB)을 메모리에 보관 — 네트워크 없이 즉시 재구축</td></tr>
<tr><td class="l">"000번대 서가인데 5권 확인이라고 떠요" (목록 밖 오탐)</td>
<td class="l">저자기호만 비슷하면 목록의 다른 책을 짚던 폴백</td>
<td class="l">분류번호 유사도 게이트 — 분류가 안 맞으면 기각</td></tr>
<tr><td class="l">"일시정지 안 누르고는 안 되나요?"</td>
<td class="l">판독이 수동 트리거였음</td>
<td class="l">화면이 안정되면 자동 판독(12초 간격) + 프레임마다 결과 누적(투표)</td></tr>
<tr><td class="l">"제공 동의했는데 폰에 zip이 다운로드돼요"</td>
<td class="l">전송이 삐끗하면 다운로드로 떨어지는 폴백</td>
<td class="l">드라이브 전송 전용으로 재설계 — 실패분은 다음 스캔 때 자동 재전송, 전송 중 진행 바</td></tr>
<tr><td class="l">"판독에 40~50초 걸려요. 다음 세트로 넘어가면 에러가 나요"</td>
<td class="l">데이터 수집엔 필요 없는 인식(OCR) 단계가 전체를 지연</td>
<td class="l"><b>수집 모드 신설</b>: 검출→조각→전송만, 사진당 3~5초 · 라이브 4초 자동 수집 · 인식 모델 다운로드도 생략</td></tr>
</table>

<div class="concept"><b>이 방식의 의미:</b> 현장 리포트 → 원인 진단 → 당일 배포 → 다음 스캔으로 즉시 검증.
현장 테스트가 "버그 목록 만들기"가 아니라 <b>당일 개선 루프</b>로 돌았습니다. 새로고침 한 번이면 광수쌤 폰에 반영됩니다.</div>

<h2>2. 오늘의 최대 발견 — 걷기 판독률 89% → 99% (권차 매칭 수술)</h2>
<p>검출기 v4를 채점하려고 미판독 10권을 추적하다가 뜻밖의 진범을 찾았습니다.
<b>검출기는 무죄였습니다</b> — 미판독 책의 라벨 위치는 기존 검출기(v3)도 31/31 전부 찾고 있었고,
심지어 OCR도 <code>911 v.1 이15ㄱ</code>처럼 <b>답을 다 읽고 있었습니다</b>. 문제는 그 다음 매칭 로직:</p>
<table>
<tr><th>구멍</th><th>증상</th><th>수술</th></tr>
<tr><td class="l">권차 토큰(v.1)이 분류번호와 저자기호 사이에 끼면</td><td class="l">"인접해야 매칭" 규칙이 깨져 통째로 실패</td><td class="l">매칭 전에 권차 토큰을 빼고 붙인다</td></tr>
<tr><td class="l">복본(v.1/v.2 두 권)이 있으면</td><td class="l">"어느 책인지 모호함"으로 기각</td><td class="l">읽어둔 권차로 어느 권인지 판별</td></tr>
<tr><td class="l">첫 글자만 오독(상↔싱)</td><td class="l">전체 실패</td><td class="l">나머지가 완전 일치하는 유일 후보면 인정</td></tr>
</table>
<p>결과: 걷기 판독률 <b>89% → 99% (86/87)</b>, 사진도 12→13권·10→17권으로 동반 상승(손실 0).
909~911 구간이 조직적으로 죽었던 이유는 그 구간이 <b>권차 밀집 구간</b>이었기 때문입니다.</p>
<div class="verdict"><b>교훈:</b> "특정 구간이 조직적으로 안 읽힌다"의 1차 용의자는 모델이 아니라
파이프라인 후단 로직이다. 모델 재학습(코랩 GPU 시간)보다 추적 스크립트 한 편이 먼저다.</div>

<h2>3. 코랩 모델 판정 2건 — 둘 다 "채택 안 함"이 정답이었다</h2>
<h3>3-1. 검출기 v4 (call_label_yolo_v4) — 미채택</h3>
<p>909 구간 미판독을 "검출 누락"으로 보고 준비한 재학습이었지만, 위 추적으로 <b>검출은 이미 충분</b>함이
확인됐습니다(v4=v3 동률 31/31). 학습 패키지는 향후 실제 검출 구멍이 발견될 때를 위해 보존합니다.</p>
<h3>3-2. 인식기 v5 (현장 조각 첫 투입) — 기각</h3>
<p>광수쌤 수집 조각으로 만든 학습쌍을 처음 투입한 파인튜닝. 같은 검증셋에서 현재 배포본(v4)과 정면 비교:</p>
<table>
<tr><th>검증셋</th><th>v4 (배포 중)</th><th>v5 (신규)</th><th>판정</th></tr>
<tr><td>현장 조각 52줄</td><td>39</td><td>39</td><td>동률</td></tr>
<tr><td>근접 27줄</td><td>7</td><td>7</td><td>동률</td></tr>
<tr><td>저해상 43줄</td><td><b>20</b></td><td class="down">16</td><td class="down">퇴화</td></tr>
</table>
<p><b>원인 3중주:</b> ①자동 정답의 ~10% 오염(카탈로그에 005.13/005.130/005.133이 다 있어 비슷한 이웃에게
정답을 뺏기는 사례) ②수집 구간 편중(컴퓨터·음악 2개 구간에 집중 → "흐릿하면 005처럼 찍는" 편식)
③현장 데이터 6배 가중이 편식을 증폭. 처방은 4장의 수집 가이드로.</p>
<div class="verdict"><b>판정 원칙이 지켜졌습니다:</b> "동률 + 한 곳이라도 퇴화면 배포하지 않는다."
이 게이트 덕분에 앱 품질은 한 번도 뒤로 간 적이 없습니다.</div>

<h2>4. 데이터 파이프라인 — 수집→전송→정답 부여가 하루 만에 완주</h2>
<p>오늘 광수쌤이 보낸 조각 zip 17개(520+조각)가 자동으로 드라이브에 도착했고, 품질을 전수 분석했습니다:</p>
<img class="full" src="data:image/jpeg;base64,{img_crops}" alt="수집 조각 표본">
<p style="text-align:center;color:#666;font-size:.85em">현장 수집 조각 표본 — 000번대(파랑)·100번대(초록) 서가. 절반쯤은 육안으로도 판독 가능</p>
<p>밤에 전체 장서 엑셀이 도착하면서 <b>소급 매칭</b>이 열렸습니다: 정답 없이 쌓인 조각을 판독해
장서 목록과 대조, 분류번호·저자기호가 <b>같은 책에서 동시에 맞을 때만</b> 정답을 부여합니다(보수 게이트).
학습쌍이 77줄 → <b>335줄</b>로 늘었습니다.</p>
<img class="full" src="data:image/jpeg;base64,{img_retro}" alt="소급 정답 검증">
<p style="text-align:center;color:#666;font-size:.85em">소급 정답 육안 검증(28표본 중 25 정답) — 흐릿한 이미지에 장서 목록의 참값이 붙는다. 이게 "쓸수록 똑똑해지는" 재료</p>

<h2>5. 전체 장서 연결 — 앱이 종합자료실 전체를 안다</h2>
<table>
<tr><th></th><th>어제까지</th><th>오늘부터</th></tr>
<tr><td class="l">대조·판정 대상</td><td>1,860권 (600~900번대 일부)</td><td class="up">20,944권 (000~999 전체)</td></tr>
<tr><td class="l">도서찾기 검색</td><td>일부 구간</td><td class="up">종합자료실 전 장서</td></tr>
<tr><td class="l">샘플 사진 판독</td><td>13권</td><td class="up">14권 (+1, 오탐 0)</td></tr>
</table>
<p>원장 23,346행 중 서가 점검 대상(비치 19,416 + 관외대출 1,529)만 필터했고, 앱에는
청구기호·서명·구간·자료실 4개 필드만 나갑니다(내부 관리 필드 비공개 원칙 유지).
대출중 책이 서가에서 발견되는 것도 계속 잡습니다.</p>

<h2>6. 다음 — 더 양질의 데이터를 모으는 법</h2>
<p>수집 가이드(팀공유_데이터수집_가이드_260714.md)의 세 줄 요약:</p>
<blockquote>
① <b>반 발짝 가까이</b> — 한 화면에 책 10~15권 (조각당 학습 가치 1.6~2배, 실측)<br>
② <b>안 간 구간 위주</b> — 200·300·400·500·800번대 (편식 방지)<br>
③ <b>수집 8 : 판독 2</b> — 평소엔 빠른 수집 모드, 가끔 일반 스캔으로 고품질 정답 확보
</blockquote>
<p>이 가이드로 데이터가 두 배쯤 쌓이면 인식기 v6에 재도전합니다(정제된 정답 + 가중 6→3).</p>

<footer>LibAR · 현장 테스트 1일차 리포트 (2026-07-14) · 공개 데모 https://ainsof.dev/libar-demo/ ·
문의: 아인</footer>
</body></html>"""

out = HERE/"팀공유_현장테스트1일차_리포트_260714.html"
io.open(out, "w", encoding="utf-8").write(html)
print(f"[완료] {out} ({out.stat().st_size//1024}KB)")
