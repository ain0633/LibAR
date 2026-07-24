# 원고용 그림 3종 생성 — 전부 실측값만 사용 (가짜 숫자 금지 원칙)
#   A. 실증 결과 대시보드 (지표 카드 한 장)
#   B. 정확도는 어디서 왔나 (학습이 통한 곳 vs 논리가 통한 곳)
#   C. 위험도 분석 교차검증 (177구간 순위 위 현장 발견 9구간)
# 출력: ../공모전자료/원고그림/*.png (300dpi, 문서 삽입용 흰 배경)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import os

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
GREEN = '#1e7d46'; DARK = '#15321f'; RED = '#d64545'; GRAY = '#6b7280'; BG = '#f4f8f5'
OUT = os.path.join(os.path.dirname(__file__), '..', '공모전자료', '원고그림')
os.makedirs(OUT, exist_ok=True)

# ── A. 실증 결과 대시보드 ──────────────────────────────────────
cards = [
    ('99%', '판독 정확도', '서가 걷기 스캔 · 정답지 87권 공식 채점'),
    ('100%', '자리 추정 정확도', '도서찾기 후보 검증 273건 전부 적중'),
    ('97%', "'확인' 표시 신뢰도", '확인 표시 중 실제 정답 비율'),
    ('16권/8초', '사진 한 장 점검', '스마트폰 단독 처리'),
    ('20,944권', '대조 기준 장서', '실증관 종합자료실 전 장서'),
    ('4 + 6 + 7건', '실증 발견', '오배열 4 · 기록-실물 불일치 6 · 대출중인데 서가에 7'),
    ('7 / 9', '위험도 예측 적중', '문제 발견 9구간 중 7이 위험도 상위 절반'),
    ('788줄', '현장 평가셋', '수집 조각 5,200여 개 중 사람 검증 정답'),
]
fig, axes = plt.subplots(2, 4, figsize=(12.2, 4.4))
fig.suptitle('LibAR 실증 결과 요약 — 모든 수치는 실증관(대림도서관) 측정값', fontsize=13, fontweight='bold', color=DARK, y=0.98)
for ax, (num, title, sub) in zip(axes.flat, cards):
    ax.set_axis_off()
    ax.add_patch(FancyBboxPatch((0.02, 0.04), 0.96, 0.92, boxstyle='round,pad=0.02,rounding_size=0.06',
                                fc=BG, ec='#cfe3d6', lw=1.2, transform=ax.transAxes))
    ax.text(0.5, 0.66, num, ha='center', va='center', fontsize=19, fontweight='bold', color=GREEN, transform=ax.transAxes)
    ax.text(0.5, 0.40, title, ha='center', va='center', fontsize=10.5, fontweight='bold', color=DARK, transform=ax.transAxes)
    ax.text(0.5, 0.17, sub, ha='center', va='center', fontsize=7.2, color=GRAY, transform=ax.transAxes, wrap=True)
plt.tight_layout(rect=[0, 0, 1, 0.93])
plt.savefig(os.path.join(OUT, 'A_실증결과_대시보드.png'), dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

# ── B. 정확도는 어디서 왔나 ────────────────────────────────────
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw={'width_ratios': [1, 1]})
# 좌: 초기엔 모델 학습이 통했다 (광각 라벨 직독률)
steps1 = ['사전학습\n그대로', '저해상 라벨\n파인튜닝', '라벨·제목\n이원 운용']
vals1 = [6, 30, 52]
b1 = a1.bar(steps1, vals1, color=['#b9cfc0', GREEN, GREEN], width=0.55)
for r, v in zip(b1, vals1):
    a1.text(r.get_x() + r.get_width()/2, v + 1.5, f'{v}%', ha='center', fontsize=12, fontweight='bold', color=DARK)
a1.set_ylim(0, 60); a1.set_ylabel('광각 사진 라벨 직독률(%)')
a1.set_title('개발 초기 — 모델 학습이 정확도를 올렸다', fontsize=11, fontweight='bold', color=DARK)
a1.spines[['top', 'right']].set_visible(False)
# 우: 마지막 도약은 논리 수리 (걷기 판독률) + 재학습 5회 무효
steps2 = ['모델·파이프라인\n완성 시점', '판독 논리 수리\n(현장 실패 분석)']
vals2 = [89, 99]
b2 = a2.bar(steps2, vals2, color=['#b9cfc0', GREEN], width=0.45)
for r, v in zip(b2, vals2):
    a2.text(r.get_x() + r.get_width()/2, v + 0.6, f'{v}%', ha='center', fontsize=12, fontweight='bold', color=DARK)
a2.set_ylim(80, 102); a2.set_ylabel('걷기 스캔 판독률(%)')
a2.set_title('마지막 도약 — 논리 수리가 정확도를 올렸다', fontsize=11, fontweight='bold', color=DARK)
a2.annotate('같은 기간 모델 재학습 5회 시도\n→ 전부 효과 없음 확인 후 폐기', xy=(0.5, 0.30),
            xycoords='axes fraction', ha='center', fontsize=9, color=RED,
            bbox=dict(boxstyle='round,pad=0.5', fc='#fdf0f0', ec=RED, lw=1))
a2.spines[['top', 'right']].set_visible(False)
fig.suptitle('정확도는 어디서 왔나 — 효과를 실험으로 확인한 것만 남겼습니다', fontsize=12.5, fontweight='bold', color=DARK)
plt.tight_layout(rect=[0, 0, 1, 0.92])
plt.savefig(os.path.join(OUT, 'B_정확도_개선_경로.png'), dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

# ── C. 위험도 분석 교차검증 ────────────────────────────────────
# mashup_risk.txt 실측: 현장 발견 9구간의 위험도 순위 (177구간 중)
field = [('609', 14), ('911', 29), ('909', 34), ('001', 52), ('325', 62),
         ('594', 66), ('592', 74), ('375', 113), ('688', 134)]
fig, ax = plt.subplots(figsize=(11.5, 3.4))
ax.axvspan(0.5, 88.5, color='#e8f4ec', zorder=0)
ax.text(44, 1.62, '위험도 상위 절반 (1~88위)', ha='center', fontsize=9.5, color=GREEN, fontweight='bold')
ax.text(133, 1.62, '하위 절반 (89~177위)', ha='center', fontsize=9.5, color=GRAY)
ax.hlines(1, 0.5, 177.5, color='#d1d5db', lw=2, zorder=1)
for i in range(0, 178, 22):
    ax.vlines(max(i, 1), 0.93, 1.07, color='#d1d5db', lw=1)
for name, rank in field:
    inside = rank <= 88
    ax.plot(rank, 1, 'o', ms=13, color=GREEN if inside else GRAY, zorder=3,
            mec='white', mew=1.5)
    ax.annotate(name, xy=(rank, 1), xytext=(rank, 1.28), ha='center', fontsize=9,
                fontweight='bold', color=DARK,
                arrowprops=dict(arrowstyle='-', color='#9ca3af', lw=0.8))
ax.text(1, 0.62, '1위\n(가장 위험)', ha='left', fontsize=8.5, color=GRAY)
ax.text(177, 0.62, '177위\n(가장 안전)', ha='right', fontsize=8.5, color=GRAY)
ax.set_xlim(-3, 182); ax.set_ylim(0.45, 1.8); ax.set_axis_off()
ax.set_title('장서 데이터로 만든 오배열 위험도 vs 실제 현장 발견 — 문제가 나온 9구간 중 7구간이 위험도 상위 절반\n'
             '(177개 서가 구간을 권차·복본 밀집, 저자기호 인접, 대출 비율로 점수화한 뒤, 실증에서 실제 오배열·불일치가 발견된 구간의 순위를 표시)',
             fontsize=10.5, color=DARK, pad=14)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'C_위험도_교차검증.png'), dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
# ── D. 종합 대시보드 (한 장 총괄) ──────────────────────────────
fig = plt.figure(figsize=(13.5, 9))
gs = fig.add_gridspec(4, 3, height_ratios=[0.9, 1.15, 1.15, 0.28], hspace=0.55, wspace=0.25,
                      left=0.045, right=0.965, top=0.90, bottom=0.03)
fig.suptitle('LibAR 실증 대시보드 — 영등포구립 대림도서관 종합자료실 · 7주 실증 · 전 수치 실측값 (v1.0 기준)',
             fontsize=14, fontweight='bold', color=DARK, y=0.965)

def card(ax, num, title, sub, accent=GREEN):
    ax.set_axis_off()
    ax.add_patch(FancyBboxPatch((0.01, 0.02), 0.98, 0.96, boxstyle='round,pad=0.02,rounding_size=0.05',
                                fc=BG, ec='#cfe3d6', lw=1.2, transform=ax.transAxes))
    ax.text(0.5, 0.68, num, ha='center', va='center', fontsize=21, fontweight='bold', color=accent, transform=ax.transAxes)
    ax.text(0.5, 0.38, title, ha='center', va='center', fontsize=10.5, fontweight='bold', color=DARK, transform=ax.transAxes)
    ax.text(0.5, 0.15, sub, ha='center', va='center', fontsize=7.5, color=GRAY, transform=ax.transAxes)

# 1행: 핵심 KPI 3장
for i, (n, t, s) in enumerate([
        ('99%', '판독 정확도', '서가 걷기 스캔 · 정답지 87권 공식 채점'),
        ('100%', '자리 추정 정확도', '도서찾기 후보 검증 273건 전부 적중'),
        ('0원', '서버·장비 비용', '온디바이스 AI 3종(63.5MB) — 웹 주소만으로 도입')]):
    card(fig.add_subplot(gs[0, i]), n, t, s)

# 2행 좌: 정확도 여정
ax = fig.add_subplot(gs[1, 0])
labels = ['광각 직독\n(사전학습)', '광각 직독\n(파인튜닝)', '광각 직독\n(이원 운용)', '걷기 판독\n(파이프라인)', '걷기 판독\n(논리 수리)']
vals = [6, 30, 52, 89, 99]
colors = ['#b9cfc0', '#7fb392', GREEN, '#b9cfc0', GREEN]
bars = ax.bar(labels, vals, color=colors, width=0.62)
for r, v in zip(bars, vals):
    ax.text(r.get_x() + r.get_width()/2, v + 2, f'{v}%', ha='center', fontsize=9.5, fontweight='bold', color=DARK)
ax.set_ylim(0, 112); ax.set_yticks([])
ax.tick_params(axis='x', labelsize=7.2)
ax.set_title('정확도 여정 — 학습으로 6→52%, 논리 수리로 89→99%', fontsize=9.5, fontweight='bold', color=DARK)
ax.spines[['top', 'right', 'left']].set_visible(False)

# 2행 중: 실증 발견
ax = fig.add_subplot(gs[1, 1])
found = [('대출 중인데 서가에', 7), ('전산-실물 불일치', 6), ('실제 오배열', 4)]
names = [f[0] for f in found]; nums = [f[1] for f in found]
b = ax.barh(names, nums, color=[GREEN, '#7fb392', RED], height=0.55)
for r, v in zip(b, nums):
    ax.text(v + 0.15, r.get_y() + r.get_height()/2, f'{v}건', va='center', fontsize=10.5, fontweight='bold', color=DARK)
ax.set_xlim(0, 8.6); ax.set_xticks([])
ax.tick_params(axis='y', labelsize=8.5)
ax.set_title('표본 점검만으로 찾아낸 것 — 총 17건', fontsize=9.5, fontweight='bold', color=DARK)
ax.spines[['top', 'right', 'bottom']].set_visible(False)

# 2행 우: 활용 데이터 3축
ax = fig.add_subplot(gs[1, 2]); ax.set_axis_off()
ax.set_title('활용한 도서관 데이터 3축', fontsize=9.5, fontweight='bold', color=DARK)
rows3 = [('자관 장서 데이터', '20,944권', '대조·판정·찾기의 기준'),
         ('정보나루 인기대출 API', '소장 357권 연결', '서가 위 인기 핀'),
         ('국중도 사서추천 API', '소장 222권 연결', '서가 위 추천 핀·추천사')]
for k, (t, n, s) in enumerate(rows3):
    y = 0.80 - k * 0.33
    ax.add_patch(FancyBboxPatch((0.01, y - 0.13), 0.98, 0.27, boxstyle='round,pad=0.01,rounding_size=0.04',
                                fc=BG, ec='#cfe3d6', lw=1, transform=ax.transAxes))
    ax.text(0.05, y, t, fontsize=8.8, fontweight='bold', color=DARK, va='center', transform=ax.transAxes)
    ax.text(0.97, y + 0.045, n, fontsize=10, fontweight='bold', color=GREEN, va='center', ha='right', transform=ax.transAxes)
    ax.text(0.97, y - 0.065, s, fontsize=7, color=GRAY, va='center', ha='right', transform=ax.transAxes)

# 3행 좌+중: 위험도 스트립 (압축판)
ax = fig.add_subplot(gs[2, 0:2])
field = [('609', 14), ('911', 29), ('909', 34), ('001', 52), ('325', 62),
         ('594', 66), ('592', 74), ('375', 113), ('688', 134)]
ax.axvspan(0.5, 88.5, color='#e8f4ec', zorder=0)
ax.hlines(1, 0.5, 177.5, color='#d1d5db', lw=2, zorder=1)
for name, rank in field:
    inside = rank <= 88
    ax.plot(rank, 1, 'o', ms=10, color=GREEN if inside else GRAY, zorder=3, mec='white', mew=1.2)
    ax.annotate(name, xy=(rank, 1), xytext=(rank, 1.42), ha='center', fontsize=7.8, fontweight='bold',
                color=DARK, arrowprops=dict(arrowstyle='-', color='#9ca3af', lw=0.7))
ax.text(44, 0.45, '위험도 상위 절반', ha='center', fontsize=8, color=GREEN, fontweight='bold')
ax.text(133, 0.45, '하위 절반', ha='center', fontsize=8, color=GRAY)
ax.set_xlim(-3, 182); ax.set_ylim(0.2, 1.85); ax.set_axis_off()
ax.set_title('장서 데이터 기반 오배열 위험도(177구간) vs 실제 발견 — 9구간 중 7이 상위 절반', fontsize=9.5, fontweight='bold', color=DARK)

# 3행 우: 검증 문화
ax = fig.add_subplot(gs[2, 2]); ax.set_axis_off()
ax.set_title('숫자를 지키는 장치', fontsize=9.5, fontweight='bold', color=DARK)
rows4 = [('자동 검사(배포 게이트)', '16종 전부 통과 시에만 배포'),
         ('현장 평가셋', '사람 검증 정답 788줄 (조각 5,200여 개)'),
         ('효과 없어 폐기한 방법', '모델 재학습 5회 — 실험 기록과 함께 폐기'),
         ('공식 채점 정답지', '걷기 87권 · 자리 추정 273건')]
for k, (t, s) in enumerate(rows4):
    y = 0.84 - k * 0.24
    ax.text(0.03, y, '●', fontsize=8, color=GREEN, va='center', transform=ax.transAxes)
    ax.text(0.10, y + 0.035, t, fontsize=8.6, fontweight='bold', color=DARK, va='center', transform=ax.transAxes)
    ax.text(0.10, y - 0.055, s, fontsize=7.3, color=GRAY, va='center', transform=ax.transAxes)

# 4행: 푸터
ax = fig.add_subplot(gs[3, :]); ax.set_axis_off()
ax.text(0.5, 0.5, '사진 한 장 16권/8초 · 검출 7,039박스 자체 학습 · 인식 702줄 파인튜닝 · 공개 데모 운영 중 ainsof.dev/libar-demo',
        ha='center', va='center', fontsize=9, color=GRAY, transform=ax.transAxes)
plt.savefig(os.path.join(OUT, 'D_종합대시보드.png'), dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

print('저장 완료:', OUT)
for f in sorted(os.listdir(OUT)): print(' -', f)
