// 라이브 루프: 가짜 카메라로 시작→검출 반복→일시정지까지 기본 생명주기
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ camera: true });
await page.evaluate(() => { show('scan'); if (!live) toggleLive(); });
await page.waitForFunction(() => /책 \d+권 보임|수집 모드|준비 중/.test(document.getElementById('scan-title').textContent), { timeout: 60000 });
await new Promise(r => setTimeout(r, 6000));             // 유휴 감속 발동 대기 (0박스 3초 + 프레임 1회)
const st1 = await page.evaluate(() => ({ live, ms: lastMs, boxes: lastRows ? lastRows.length : 0, rest: _paceRest }));
// 발열 카드 A: 시트 펼침 = 가려진 검출 휴면(-1), 접으면 재개
await page.evaluate(() => setSheet(true));
await new Promise(r => setTimeout(r, 1200));
const shOpen = await page.evaluate(() => _paceRest);
await page.evaluate(() => setSheet(false));
await new Promise(r => setTimeout(r, 2000));
const shClose = await page.evaluate(() => _paceRest);
// 블랙아웃 워치독: 8프레임만 밝기 0을 강제 — ~4초 뒤 카메라 재획득(세션 유지)으로 자가 복구해야 함
const wdGen = await page.evaluate(() => { sessionBooks.set('x-테스트', { call: 'x-테스트' });
  const orig = frameDiff; let n = 0;
  frameDiff = src => { orig(src); _motLum = ++n <= 8 ? 0 : 128; return 255; };
  return liveGen; });
await page.waitForFunction(g => liveGen > g && live, { timeout: 15000 }, wdGen);
const wd = await page.evaluate(() => ({ live, keep: sessionBooks.has('x-테스트') }));
await new Promise(r => setTimeout(r, 1500));
await page.evaluate(() => toggleLive(false));            // 일시정지 (판독 생략)
await new Promise(r => setTimeout(r, 1000));
const st2 = await page.evaluate(() => ({ live }));
await browser.close();

assert(st1.live && st1.ms > 0, `라이브 루프 미작동: ${JSON.stringify(st1)}`);
// 발열 카드 ②: 가짜 카메라(책 0권)는 6초 뒤 유휴 감속 900ms, 박스가 있으면 기본 450ms
assert(st1.rest === (st1.boxes ? 450 : 900), `페이싱 이상: 박스 ${st1.boxes}개인데 휴식 ${st1.rest}ms`);
assert(shOpen === -1, `시트 펼침 중 검출 휴면 실패: _paceRest ${shOpen}`);
assert(shClose > 0, `시트 접은 뒤 재개 실패: _paceRest ${shClose}`);
assert(!st2.live, '일시정지가 안 먹음');
assert(wd.live && wd.keep, `블랙 워치독 자가 복구 실패: ${JSON.stringify(wd)} (기대 라이브 재개·세션 유지)`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_live — 검출 ${st1.ms.toFixed(0)}ms/프레임, 휴식 ${st1.rest}ms(박스 ${st1.boxes}) · 시트 휴면/재개 OK · 블랙 워치독 복구 OK · 시작·정지 정상`);
