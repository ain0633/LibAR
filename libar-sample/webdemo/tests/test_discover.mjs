// 이용자 탐색 경로: ①🔥인기대출 토글 → 목록 교집합 책에 핀 ②핀 탭 → 서지 팝업(제목·대출횟수)
//   ③⭐사서추천 전환 → 추천사 팝업 ④재토글 → 핀·팝업 해제. 동봉 JSON 실데이터로 검증.
import { openApp, assert } from './util.mjs';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const pop = JSON.parse(readFileSync(path.join(HERE, '../demo/popular_daelim.json'), 'utf8'));
const rec = JSON.parse(readFileSync(path.join(HERE, '../demo/recommend_daelim.json'), 'utf8'));
const popB = pop[0];
const recB = rec.find(b => b.note && b.note.length > 20) || rec[0];

const { browser, page, errs } = await openApp();
await page.evaluate(async () => { await sessReady; });
// 동봉 JSON 선로드 — 긴 fetch를 evaluate 안에서 기다리면 부하 시 프라미스가 GC에 수거된다(폴링으로 대기)
await page.evaluate(() => { discData('pop'); discData('rec'); });
await page.waitForFunction('_disc.pop && _disc.rec', { timeout: 30000, polling: 300 });

const r = await page.evaluate(async ([popCall, recCall]) => {
  const mk = (call, x) => ({ band: 0, call, how: call ? '청구기호' : null, box: [x, 0, x + 10, 20] });
  show('scan');
  findTarget = null;
  lastImg = mkCanvas(140, 30);
  lastRows = [mk(popCall, 0), mk('099.999-없33ㅁ', 40), mk(recCall, 80)];
  const pins = () => [...document.getElementById('ar').children].filter(e => e.style.cursor === 'pointer');
  await toggleDisc('pop');
  const popPins = pins().length;
  const popTitleMsg = document.getElementById('scan-title').textContent;
  pins()[0].click();
  const popPop = document.getElementById('discPop');
  const popShown = popPop.style.display === 'block';
  const popText = popPop.textContent;
  await toggleDisc('rec');                              // pop → rec 직접 전환
  const recPins = pins().length;
  pins()[0]?.click();
  const recText = document.getElementById('discPop').textContent;
  await toggleDisc('rec');                              // 끄기
  const offPins = pins().length;
  const offPop = document.getElementById('discPop').style.display === 'none';
  return { popPins, popTitleMsg, popShown, popText, recPins, recText, offPins, offPop };
}, [popB.call, recB.call]);
await browser.close();

assert(r.popPins === 1, `인기대출 핀 수: ${r.popPins} (기대 1)`);
assert(r.popTitleMsg.includes('1권'), `인기대출 안내 문구: ${r.popTitleMsg}`);
assert(r.popShown && r.popText.includes(popB.title.slice(0, 8)), `인기대출 팝업 내용: ${r.popText.slice(0, 60)}`);
assert(r.popText.includes('대출'), `대출횟수 표기 없음: ${r.popText.slice(0, 60)}`);
assert(r.recPins === 1, `사서추천 핀 수: ${r.recPins} (기대 1)`);
assert(r.recText.includes(recB.title.slice(0, 8)) && r.recText.includes(recB.note.slice(0, 10)),
       `추천사 표기 없음: ${r.recText.slice(0, 80)}`);
assert(r.offPins === 0 && r.offPop, `해제 후 잔존: 핀 ${r.offPins}, 팝업 ${r.offPop}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_discover — 🔥핀·서지·대출횟수 · ⭐핀·추천사 · 전환·해제 OK (동봉 ${pop.length}+${rec.length}권)`);
