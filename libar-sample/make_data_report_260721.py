# -*- coding: utf-8 -*-
"""앱 수집 데이터 실험 결산 + 데이터 활용 계획 + 최종 모델·성능 개선 로드맵 — 팀 공유 리포트."""
import base64, io, sys
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
ROOT = HERE.parent

def b64(path, width=1000, q=78):
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), 1)
    h, w = im.shape[:2]
    if w > width: im = cv2.resize(im, (width, int(h*width/w)))
    return base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1]).decode()

img_pin = b64(ROOT/"도서찾기_핀_예시2.png", width=440, q=82)

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LibAR 수집 데이터 실험 결산 & 다음 계획 (2026-07-21)</title>
<style>
body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;max-width:1100px;margin:0 auto;
     padding:24px 20px;color:#222;line-height:1.7;background:#fafafa}}
h1{{font-size:1.55em;border-bottom:3px solid #2b6cb0;padding-bottom:8px}}
h2{{font-size:1.2em;margin-top:2em;border-left:5px solid #2b6cb0;padding-left:12px}}
blockquote{{background:#eef4fb;border-left:4px solid #2b6cb0;margin:12px 0;padding:12px 16px;border-radius:0 6px 6px 0}}
table{{border-collapse:collapse;margin:10px 0;background:#fff;font-size:.92em;width:100%}}
th,td{{border:1px solid #d0d7de;padding:6px 10px;text-align:center}}
td.l{{text-align:left}}
th{{background:#f0f4f8}}
.kpi{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
.kpi div{{flex:1;min-width:140px;background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:12px;text-align:center}}
.kpi .n{{font-size:1.3em;font-weight:bold;color:#2b6cb0}}
.kpi .l{{font-size:.82em;color:#666}}
.up{{color:#188038;font-weight:bold}} .down{{color:#c53030;font-weight:bold}}
.verdict{{background:#fdf6ec;border-left:4px solid #d69e2e;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0}}
.concept{{background:#f0faf4;border-left:4px solid #28a058;padding:12px 16px;margin:14px 0;border-radius:0 6px 6px 0}}
.step{{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:12px 16px;margin:10px 0}}
.step b.num{{display:inline-block;background:#2b6cb0;color:#fff;border-radius:50%;width:24px;height:24px;
            text-align:center;line-height:24px;margin-right:8px}}
img.phone{{width:300px;border:1px solid #ccc;border-radius:14px;display:block;margin:8px auto}}
code{{background:#eef;padding:1px 5px;border-radius:4px}}
small.g{{color:#666}}
footer{{margin-top:2.5em;font-size:.85em;color:#777;border-top:1px solid #ddd;padding-top:10px}}
</style></head><body>

<h1>📊 앱 수집 데이터 실험 결산 & 다음 계획 <small style="font-size:.55em;color:#666">2026-07-21 · 팀 공유용</small></h1>

<blockquote><b>3주간 앱으로 모은 데이터로 학습 실험 5건을 돌렸고, 5건 모두 배포 기각했습니다.</b>
그런데 실패가 아닙니다 — 각 기각이 병목을 하나씩 소거해 "성능이 어디서 나오는지"를 확정했고,
수집 데이터는 학습 연료 대신 <b>평가 잣대·앱 기능·공모전 증거</b>로 전환되어 지금의 개선 전부를 떠받치고 있습니다.</blockquote>

<div class="kpi">
<div><div class="n">5,200+</div><div class="l">수집 조각 (수집 모드 + 원샷)</div></div>
<div><div class="n">788줄</div><div class="l">사람 라벨 정답 (label.html)</div></div>
<div><div class="n">5건 기각</div><div class="l">rec v5~v8 + 검출기 v5</div></div>
<div><div class="n">177줄</div><div class="l">공정 현장 평가셋 (76+101)</div></div>
<div><div class="n">99% / 97%</div><div class="l">걷기 판독률 / 확인율 (유지)</div></div>
</div>

<h2>① 실험 결과 — 무엇을 시도했고, 왜 전부 기각됐나</h2>
<table>
<tr><th>실험</th><th>재료 (앱 수집)</th><th>결과</th><th>기각 원인 = 배운 것</th></tr>
<tr><td>rec v5 <small class="g">07-14</small></td><td class="l">소급 정답 335줄 (조각→카탈로그 자동 매칭)</td>
<td class="down">저해상 20→16 퇴화</td><td class="l"><b>정답 오염</b> — 자동 매칭이 비슷한 청구기호를 헷갈림</td></tr>
<tr><td>rec v6 <small class="g">07-17</small></td><td class="l">게이트 강화 소급 정답 825줄</td>
<td class="down">전 그룹 하락</td><td class="l"><b>선택 편향</b> — 모델이 이미 읽는 조각만 정답이 됨 = 새 정보 0</td></tr>
<tr><td>rec v7 <small class="g">07-17</small></td><td class="l">사람 라벨 302줄 (편향 없는 정답)</td>
<td class="down">전 그룹 정체</td><td class="l"><b>정보 한계</b> — 글자 줄 높이 25px엔 학습할 신호 자체가 없음</td></tr>
<tr><td>rec v8 <small class="g">07-19</small></td><td class="l">원샷 고해상 재료 501줄 (줄 49px, 2배)</td>
<td class="down">62→58 하락</td><td class="l"><b>학습량 한계</b> — 400줄 미세조정은 기존 가중치를 흔들 뿐 (환각 오독 유발)</td></tr>
<tr><td>검출기 v5 <small class="g">07-19</small></td><td class="l">박스 완화 + 사람 확정 오탐 17건</td>
<td class="l">검출 지표 <span class="up">↑</span> 판독 E2E <span class="down">14→12</span></td>
<td class="l"><b>결합 리스크</b> — 판독 파이프라인이 기존 박스 통계에 튜닝돼 있음. 교체 판정은 E2E로</td></tr>
</table>

<div class="verdict"><b>결론 — 성능은 모델 학습이 아니라 픽셀·로직·UX에서 나왔다 (전부 실측).</b><br>
권차 매칭 수술 <span class="up">+10%p</span> (판독률 89→99%) · A안 고해상 원샷 <span class="up">+11%p</span>
(어려운 조각 50→61%, 수집 확정률 2→44%) · 파인튜닝 4회 <b>0%p</b>.
모델 3종은 아래 구성으로 <b>확정·동결</b>하고, 남은 개선은 로직과 운영에서 얻습니다.</div>

<h2>② 수집 데이터는 폐기인가 — 아니오, 용도가 바뀌었습니다</h2>
<table>
<tr><th>자산</th><th>규모</th><th>현재·향후 용도</th></tr>
<tr><td>공정 현장 평가셋</td><td>177줄 (76+101)</td><td class="l"><b>모든 변경의 판정 잣대.</b> 경량화(fp16) 전수 감사도 이걸로 완료 — 247줄 완전 동률, 손실 0 입증</td></tr>
<tr><td>순서 추론 파이프라인</td><td>검증 정밀도 100% (273/273)</td><td class="l">학습 정답용으로 만들었다가 → <b>도서찾기 "후보 확률 핀" 기능으로 앱에 재사용</b> (아래 그림)</td></tr>
<tr><td>사람 확정 오탐(라벨아님)</td><td>17건</td><td class="l">미래 검출기 재학습 재료로 보존</td></tr>
<tr><td>전산-서가 불일치 발견</td><td>실물 6건</td><td class="l">타관대출·라벨 불일치 등 — "앱이 전산의 구멍을 찾는다" 공모전 원고 핵심 소재</td></tr>
<tr><td>위험도 매쉬업 분석</td><td>177구간</td><td class="l">장서 구조(복본·저자 밀집)×대출로 오배열 위험 구간 예측 — 상관 +0.31, 현장 발견 9구간 중 7이 상위 50% 적중 (원고 데이터 분석 장)</td></tr>
</table>

<div style="text-align:center;margin:14px 0">
<img class="phone" src="data:image/jpeg;base64,{img_pin}">
<small class="g">▲ 데이터→기능 재사용 사례: 순서 추론(수집 데이터로 검증)이 도서찾기 확률 핀이 됨 —<br>
찾는 책만 📍98%로 표시, 못 읽었으면 "있어야 할 틈"의 후보 2~3권을 확률로 제시</small></div>

<div class="concept"><b>앞으로의 수집 방침</b> — 대규모 사람 라벨링은 종료합니다(학습 노선이 닫혔으므로).
수집 모드 자체는 유지 — ①평가셋 보강 ②검출 오탐(하드 네거티브) 축적 ③전산-서가 불일치 발견은
라벨링 없이도 계속 쌓이는 가치입니다.</div>

<h2>③ 최종 모델 구성 (확정)</h2>
<table>
<tr><th>모델</th><th>크기</th><th>역할</th><th>검증</th></tr>
<tr><td>YOLO26n v3 (동적 입력)</td><td>9.8MB</td><td class="l">청구기호 라벨 검출 — 라이브 960px / 사진·원샷 1280px</td>
<td class="l">v4·v5 도전 모두 E2E 열세로 기각, v3 유지 확정</td></tr>
<tr><td>PP-OCRv5 mobile det</td><td>4.5MB</td><td class="l">라벨 안 텍스트 줄 검출</td><td class="l">server det 대비 17배 빠름·정확도 동등 실측</td></tr>
<tr><td>한국어 rec v4 <b>fp16</b></td><td>48MB</td><td class="l">청구기호 글자 인식</td>
<td class="l"><b>전수 감사 완료</b>: fp32 대비 247줄 완전 동률(손실 0) · int8은 예측 붕괴로 기각</td></tr>
</table>
<table>
<tr><th>지연시간 <small class="g">워밍업 5 + 100회 반복, 개발 PC</small></th><th>평균±표준편차</th><th>P99</th></tr>
<tr><td>검출 1프레임 (WebGPU 960)</td><td>98.8 ± 9.9ms</td><td>143ms</td></tr>
<tr><td>인식 1줄 (WebGPU fp16)</td><td>21.5 ± 2.2ms</td><td>28ms</td></tr>
<tr><td>WASM 폴백 (검출/인식)</td><td>572 / 77ms</td><td>637 / 94ms</td></tr>
</table>
<blockquote>실전 수치: 걷기 판독률 <b>99%</b>·확인율 97% · 서가 사진 1장 <b>16권 확인 / 8.3초</b>
(600번대 실사진 실측 — 이 판독에서 실제 오배열 1건 <code>673.53-이57ㄴ</code>도 검출) ·
전 과정 온디바이스 = 서버비 0원.</blockquote>

<h2>④ 성능 개선 — 앞으로의 계획</h2>
<div class="step"><b class="num">1</b><b>내일(화) 현장 검증</b> — 광수쌤과 라이브 vs 📷사진 점검 A/B(결과 좋은 쪽을 사서 기본으로 채택),
000~500번대 구간 판독률 첫 공식 측정, <code>707-양94ㅇ</code> 실물 확인(행 문맥 게이트 착수 조건)</div>
<div class="step"><b class="num">2</b><b>로직 (모델 무관 정확도)</b> — 행 문맥 게이트: 주변이 전부 900번대인데 혼자 707로 매칭되면
경보 대신 재확인으로 강등 → 거짓 오배열 경보 제거(사서 신뢰) · "다시 확인" 카운터 중복 박스 제거(실제보다 나쁘게 보이는 표시 결함)</div>
<div class="step"><b class="num">3</b><b>운영 루프 (실사용 완성도)</b> — 카탈로그 주간 갱신 루틴(솔로몬 엑셀 내보내기) ·
상태 플래그 경보(타관·제적·대출중 책이 서가에 있으면 알림 — 발견 6건이 존재 증명) ·
PWA 오프라인 캐시(63MB 재다운로드 제거) · 사서 파일럿 2~4주 → 실사용 수치를 원고에</div>
<div class="step"><b class="num">4</b><b>조건부 카드 (필요시에만)</b> — 미판독 크롭 한정 2차 판독(외부 AI, 크롭만 전송·사용량 과금 소액):
화요일 진단에서 인식기 체급이 병목으로 나올 때만 · 검출기 재도전: 서가 전체 프레임 수집 경로가 생기고 + 판독 E2E 선판정 조건으로만</div>
<div class="step"><b class="num">5</b><b>공모전 원고 (8/7 마감)</b> — 판독률 99%·픽셀 실증(2%→44%)·기각 실험 5건의 방법론(과학적 소거)·
전산-서가 불일치 발견·위험도 매쉬업 분석을 골격으로</div>

<footer>LibAR · 수집 데이터 실험 결산 리포트 (2026-07-21) · 공개 데모 https://ainsof.dev/libar-demo/ ·
관련: 팀공유_rec학습실험_v5-v7_회고_260718 · 팀공유_현장테스트1일차_리포트_260714</footer>
</body></html>"""

out = ROOT/"팀공유_수집데이터_실험결산과_계획_260721.html"
io.open(out, "w", encoding="utf-8").write(html)
print(f"저장: {out.name} ({out.stat().st_size//1024}KB)")
