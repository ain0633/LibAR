// 회전 재시작 폭풍: 루프 병주(먹통) 회귀 게이트 — 07-16 현장 먹통의 재현 테스트
// 판정: detect 동시 실행 수(_maxIn)가 1을 넘으면 루프가 겹친 것 (직렬 루프 불변식 위반)
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ camera: true });
await page.evaluate(() => {
  window._inflight = 0; window._maxIn = 0;
  const d = detect;
  window.detect = async (...a) => {
    _maxIn = Math.max(_maxIn, ++_inflight);
    try { return await d(...a); } finally { _inflight--; }
  };
  show('scan'); if (!live) toggleLive();
});
await new Promise(r => setTimeout(r, 4000));
// 회전 3연타 → 5초 관찰 → 다시 2연타 → 5초 관찰
for (const burst of [3, 2]) {
  await page.evaluate(n => { for (let i = 0; i < n; i++) setTimeout(() => dispatchEvent(new Event('orientationchange')), i * 150); }, burst);
  await new Promise(r => setTimeout(r, 5000));
}
const st = await page.evaluate(() => ({ live, gen: liveGen, maxIn: _maxIn,
  title: document.getElementById('scan-title').textContent.slice(0, 40) }));
await browser.close();

assert(st.maxIn <= 1, `루프 병주 감지: 동시 detect ${st.maxIn}개 (세대 토큰 깨짐)`);
assert(st.live, `회전 후 라이브 죽음: ${st.title}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_rotate — 회전 5회 후에도 루프 1개(gen ${st.gen}) · 라이브 생존`);
