// 위험군 한정 제목 대조 경로: ①위험군 명단 산출 ②제목 유사도 판별력 ③실판독 회귀·비용 계측
// 보수 설계 검증: 위험군 미발동 시 판독 결과가 기존과 완전 동일해야 한다 (확인 14권 유지)
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ hash: '#autotest' });
await page.waitForSelector('#testout', { timeout: 300000 });
const out = JSON.parse((await page.$eval('#testout', el => el.textContent))
  .replace(/^@@TESTOUT@@/, '').replace(/@@END@@$/, ''));

const t = await page.evaluate(async () => {
  const cat = await loadCatalogRaw();
  const risk = buildRiskGroups(cat);
  const g1 = risk.get('004.15-된22ㅇ10') || [];        // 꼬리 숫자 시리즈
  const g2 = risk.get('592.27-애897ㅂ') || [];         // 접두 분류쌍 + 동일 저자
  // 제목 유사도: 부분 판독으로도 형제를 가르는지 (공유 접두 제목의 변별 꼬리)
  const s1 = titleSim('맥OS 세쿼이아 2025', '된다! 맥북&아이맥 : 맥OS 세쿼이아 2025년');
  const s2 = titleSim('맥OS 세쿼이아 2025', '된다! 맥북 & 아이맥 = Gotcha! MacBook & iMac');
  // 제목 대조 1회 비용 계측: 데모 사진의 임의 영역을 회전 OCR (실비용 근사)
  const img = document.getElementById('photo');
  const t0 = performance.now();
  const crop = mkCanvas(80, 400);
  crop.getContext('2d').drawImage(img, 100, 100, 80, 400, 0, 0, 80, 400);
  const rot = mkCanvas(400, 80);
  const cx = rot.getContext('2d');
  cx.translate(200, 40); cx.rotate(Math.PI / 2); cx.drawImage(crop, -40, -200);
  await detRecPiece(rot);
  const oneMs = Math.round(performance.now() - t0);
  return { nRisk: risk.size, g1: g1.length, g2: g2.length, s1, s2, oneMs, checks: _titleChecks };
});
await browser.close();

assert(out.err === null && out.ok >= 13, `판독 회귀: ok ${out.ok}, err ${out.err}`);
assert(t.nRisk >= 300 && t.nRisk <= 1200, `위험군 규모 이상: ${t.nRisk}`);
assert(t.g1 >= 2, `꼬리 숫자 시리즈 그룹 실패 (된22ㅇ10): ${t.g1}`);
assert(t.g2 >= 2, `접두 분류쌍 그룹 실패 (592.27-애897ㅂ): ${t.g2}`);
assert(t.s1 > t.s2 + 0.12, `제목 변별력 부족: 정답 ${t.s1.toFixed(2)} vs 형제 ${t.s2.toFixed(2)}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_title — 위험군 ${t.nRisk}권 · 그룹 ${t.g1}/${t.g2} · 변별 ${t.s1.toFixed(2)}>${t.s2.toFixed(2)} · 대조 1회 ${t.oneMs}ms · 데모 발동 ${t.checks}건`);
