// 오배열 근거 팝업 경로: ①근거 계산(물리 이웃 vs 올바른 자리) ②팝업 표시/닫기
//   합성 밴드로 결정적 검증 — 데모 사진의 오배열 유무에 의존하지 않는다.
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp();
await page.evaluate(async () => { await sessReady; });

const r = await page.evaluate(() => {
  // 물리 순서(x): 005.1 → 005.5 → 005.2 → 005.3  ⇒ 005.5 하나만 오배열(LIS 밖)
  const mk = (call, x) => ({ band: 0, call, how: '청구기호', title: '', box: [x, 0, x + 10, 10] });
  const rows = [mk('005.1-가1', 0), mk('005.5-나2', 20), mk('005.2-다3', 40), mk('005.3-라4', 60)];
  flagMisplaced(rows);
  const mis = rows.filter(x => x.mis).map(x => x.call);
  const bad = rows.find(x => x.mis);
  const reason = misplaceReason(bad, rows);
  showReason(bad, rows);
  const pop = document.getElementById('reasonPop');
  const shown = pop && pop.style.display === 'block' && pop.textContent.includes(bad.call);
  hideReason();
  const hidden = pop.style.display === 'none';
  return { mis, reason, shown, hidden };
});
await browser.close();

assert(r.mis.length === 1 && r.mis[0] === '005.5-나2', `LIS 오배열 특정 실패: ${JSON.stringify(r.mis)}`);
assert(r.reason.phys.left === '005.1-가1' && r.reason.phys.right === '005.2-다3',
  `물리 이웃 오류: ${JSON.stringify(r.reason.phys)}`);
// 005.5는 정상 배열(005.1/005.2/005.3)의 맨 뒤에 와야 함 → 왼쪽 005.3, 오른쪽 서가 끝(null)
assert(r.reason.exp.left === '005.3-라4' && r.reason.exp.right === null,
  `올바른 자리 오류: ${JSON.stringify(r.reason.exp)}`);
assert(r.shown, '근거 팝업이 표시되지 않음');
assert(r.hidden, '근거 팝업 닫기 실패');
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_reason — 오배열 ${r.mis[0]} · 지금 ${r.reason.phys.left}↔${r.reason.phys.right} · 올바른자리 ${r.reason.exp.left}↔서가끝 · 팝업 표시/닫기 OK`);
