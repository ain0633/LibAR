// 수집 모드: 인식 생략 → 조각 → 드라이브 전송, 그리고 "빠름"의 회귀 게이트
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ hash: '#collect' });
assert(await page.evaluate(() => collectMode), '#collect 해시로 수집 모드 미진입');

const t0 = Date.now();
await page.evaluate(() => { show('scan'); loadDemo(1); });
await page.waitForFunction(() => /조각 \d+개 수집/.test(document.getElementById('scan-title').textContent), { timeout: 30000 });
const tBag = Date.now() - t0;
await page.waitForFunction(() => /전송됨|전송 대기/.test(document.getElementById('btn-crops').textContent), { timeout: 120000 });
const st = await page.evaluate(() => ({ btn: document.getElementById('btn-crops').textContent,
  bagLeft: cropBag.length, recLoaded: !!recSess }));
await browser.close();

assert(tBag < 20000, `수집이 느림: ${tBag}ms (인식이 끼어든 것 아닌지)`);
assert(!st.recLoaded, '수집 모드가 인식 모델(48MB)을 로드함');
assert(/전송됨/.test(st.btn) && st.bagLeft === 0, `전송 실패: ${st.btn} (잔여 ${st.bagLeft})`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_collect — 조각화 ${tBag}ms · ${st.btn}`);
