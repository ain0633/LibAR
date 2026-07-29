// v1.3 이중인식(#dual 옵트인): ①기본 주소 = v1.2 그대로(미발동) ②#dual = 미판독 한정 제목 회수
//   ③회수 책은 how='제목'·오배열 플래그 불참 ④직독 확인 권수 무손실(회수는 더하기만)
import { openApp, assert } from './util.mjs';

// 기본화(07-28 승인): 기본 주소 = v1.3 켜짐 · #nodual = v1.2 동작 롤백 스위치
{
  const { browser, page } = await openApp();
  const on = await page.evaluate(() => ({ ver: APP_VER, on: _dualOn }));
  await browser.close();
  assert(on.on && on.ver === 'v1.3', `기본 주소가 v1.3이 아님: ${JSON.stringify(on)}`);
}
{
  const { browser, page } = await openApp({ hash: '#nodual' });
  const off = await page.evaluate(() => ({ ver: APP_VER, on: _dualOn }));
  await browser.close();
  assert(!off.on && off.ver === 'v1.2', `#nodual 롤백 스위치 불량: ${JSON.stringify(off)}`);
}

// #dual + 샘플 판독 E2E: 발동·회수·판정 격리 확인
const { browser, page, errs } = await openApp({ hash: '#autotest-dual' });
await page.waitForSelector('#testout', { timeout: 300000 });
const out = JSON.parse((await page.$eval('#testout', el => el.textContent))
  .replace(/^@@TESTOUT@@/, '').replace(/@@END@@$/, ''));
const st = await page.evaluate(() => ({
  ver: APP_VER, on: _dualOn, n: _dualN, hit: _dualHit, ms: _dualMs,
  titleRows: (lastRows || []).filter(r => r.how === '제목').map(r => ({ call: r.call, mis: !!r.mis })),
}));
// 표시 구분: 제목 회수 = 하늘색 박스 + 📖제목 뱃지, 직독 = 초록 (합성 rows로 렌더 검증)
const disp = await page.evaluate(() => {
  const img = mkCanvas(100, 40);
  const rows = [
    { band: 0, call: '811.6-나883마', title: '마음이 살짝 기운다', how: '제목', score: 0.55, box: [0, 0, 10, 30] },
    { band: 0, call: '811.6-나883ㄴ', title: '너에게도 안녕이', how: '청구기호', score: 1.0, box: [20, 0, 30, 30] },
  ];
  drawBoxes(img, rows); fillSheet(img, rows);
  const ar = document.getElementById('ar').children;
  return { boxSky: ar[0].style.border.includes('rgba(56, 189, 248'),
           boxGreen: ar[1].style.border.includes('rgba(75, 226, 119'),
           badge: document.getElementById('list-ok').innerHTML.includes('📖제목') };
});
await browser.close();

assert(st.on && st.ver === 'v1.3', `#dual 버전 표기: ${JSON.stringify({ ver: st.ver, on: st.on })}`);
assert(out.err === null, `판독 오류: ${out.err}`);
assert(out.ok >= 14, `직독 확인 권수 회귀: ${out.ok} < 14 (이중인식은 더하기만 해야 함)`);
assert(st.n > 0 && st.n <= 20, `이중인식 미발동 또는 상한 초과: 발동 ${st.n}`);
assert(st.titleRows.every(r => !r.mis), `제목 회수 책이 오배열 플래그됨: ${JSON.stringify(st.titleRows)}`);
assert(disp.boxSky && disp.boxGreen && disp.badge, `제목 회수 구분 표시 실패: ${JSON.stringify(disp)}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_dual — 기본=v1.3 켜짐·#nodual=v1.2 롤백 · 발동 ${st.n}건·회수 ${st.hit}건·${st.ms}ms · 확인 ${out.ok}권 유지 · 제목 회수 플래그 0 · 하늘색 박스/뱃지 OK`);
