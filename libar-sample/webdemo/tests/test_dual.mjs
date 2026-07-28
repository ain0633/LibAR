// v1.3 이중인식(#dual 옵트인): ①기본 주소 = v1.2 그대로(미발동) ②#dual = 미판독 한정 제목 회수
//   ③회수 책은 how='제목'·오배열 플래그 불참 ④직독 확인 권수 무손실(회수는 더하기만)
import { openApp, assert } from './util.mjs';

// 기본 주소: 플래그 꺼짐 = 전 버전 그대로 (광수쌤 롤백 경로)
{
  const { browser, page } = await openApp();
  const off = await page.evaluate(() => ({ ver: APP_VER, on: _dualOn }));
  await browser.close();
  assert(!off.on && off.ver === 'v1.2', `기본 주소가 v1.2가 아님: ${JSON.stringify(off)}`);
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
await browser.close();

assert(st.on && st.ver === 'v1.3', `#dual 버전 표기: ${JSON.stringify({ ver: st.ver, on: st.on })}`);
assert(out.err === null, `판독 오류: ${out.err}`);
assert(out.ok >= 14, `직독 확인 권수 회귀: ${out.ok} < 14 (이중인식은 더하기만 해야 함)`);
assert(st.n > 0 && st.n <= 20, `이중인식 미발동 또는 상한 초과: 발동 ${st.n}`);
assert(st.titleRows.every(r => !r.mis), `제목 회수 책이 오배열 플래그됨: ${JSON.stringify(st.titleRows)}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_dual — 기본=v1.2 미발동 · #dual=v1.3 발동 ${st.n}건·회수 ${st.hit}건·${st.ms}ms · 확인 ${out.ok}권 유지 · 제목 회수 플래그 0`);
