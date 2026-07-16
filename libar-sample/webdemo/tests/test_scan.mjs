// 판독 경로: 샘플 광각 온디바이스 풀 파이프라인 — 확인 권수·오류 회귀 게이트
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ hash: '#autotest' });
await page.waitForSelector('#testout', { timeout: 300000 });
const out = JSON.parse((await page.$eval('#testout', el => el.textContent))
  .replace(/^@@TESTOUT@@/, '').replace(/@@END@@$/, ''));
await browser.close();

assert(out.err === null, `판독 오류: ${out.err}`);
assert(out.ok >= 13, `확인 권수 회귀: ${out.ok} < 13`);
assert(out.mis <= 1, `오배열 과다: ${out.mis}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_scan — 확인 ${out.ok}권 · ${out.det}/${out.rec} · ${out.recMs}ms`);
