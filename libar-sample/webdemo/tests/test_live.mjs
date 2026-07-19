// 라이브 루프: 가짜 카메라로 시작→검출 반복→일시정지까지 기본 생명주기
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ camera: true });
await page.evaluate(() => { show('scan'); if (!live) toggleLive(); });
await page.waitForFunction(() => /책 \d+권 보임|수집 모드|준비 중/.test(document.getElementById('scan-title').textContent), { timeout: 60000 });
await new Promise(r => setTimeout(r, 6000));             // 유휴 감속 발동 대기 (0박스 3초 + 프레임 1회)
const st1 = await page.evaluate(() => ({ live, ms: lastMs, boxes: lastRows ? lastRows.length : 0, rest: _paceRest }));
await page.evaluate(() => toggleLive(false));            // 일시정지 (판독 생략)
await new Promise(r => setTimeout(r, 1000));
const st2 = await page.evaluate(() => ({ live }));
await browser.close();

assert(st1.live && st1.ms > 0, `라이브 루프 미작동: ${JSON.stringify(st1)}`);
// 발열 카드 ②: 가짜 카메라(책 0권)는 6초 뒤 유휴 감속 900ms, 박스가 있으면 기본 450ms
assert(st1.rest === (st1.boxes ? 450 : 900), `페이싱 이상: 박스 ${st1.boxes}개인데 휴식 ${st1.rest}ms`);
assert(!st2.live, '일시정지가 안 먹음');
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_live — 검출 ${st1.ms.toFixed(0)}ms/프레임, 휴식 ${st1.rest}ms(박스 ${st1.boxes}) · 시작·정지 정상`);
