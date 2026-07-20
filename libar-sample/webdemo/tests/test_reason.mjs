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
  // 조치 완료 체크: 시트 렌더 → 완료 → 카운터 0·완료 표시 (합성 캔버스를 판독 이미지로)
  lastImg = mkCanvas(100, 20);
  fillSheet(lastImg, rows);
  const misBefore = document.getElementById('c-mis').textContent;
  resolveMis(bad);
  const misAfter = document.getElementById('c-mis').textContent;
  const doneShown = document.getElementById('list-mis').textContent.includes('재배열 완료');
  // 판독 불가 안내 카드 표시/닫기
  showNoRead('photo');
  const nr = document.getElementById('noReadPop');
  const nrShown = nr && nr.style.display === 'block' && nr.textContent.includes('못 읽었어요');
  hideNoRead();
  const nrHidden = nr.style.display === 'none';
  return { mis, reason, shown, hidden, misBefore, misAfter, doneShown, nrShown, nrHidden };
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
assert(r.misBefore === '1' && r.misAfter === '0', `조치 체크 카운터: ${r.misBefore}→${r.misAfter} (기대 1→0)`);
assert(r.doneShown, '완료 항목이 시트에 표시되지 않음');
assert(r.nrShown && r.nrHidden, `판독불가 카드 표시/닫기 실패: ${r.nrShown}/${r.nrHidden}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_reason — 오배열 ${r.mis[0]} · 근거(${r.reason.phys.left}↔${r.reason.phys.right} → ${r.reason.exp.left}↔끝) · 조치 1→0 · 판독불가 카드 OK`);
