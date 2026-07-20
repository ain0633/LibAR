// 사서 점검 현황(n5 축약) 경로: ①세션 KPI 집계(확인/미조치/조치완료) ②기기 저장 전송 기록 렌더
//   ③홈 진입 버튼 존재 ④리포트 전송 기록(saveDashLog) 저장 형식
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp();
await page.evaluate(async () => { await sessReady; });

const r = await page.evaluate(() => {
  sessionBooks.set('005.1-가1', { call: '005.1-가1', title: 'A', mis: false });
  sessionBooks.set('005.5-나2', { call: '005.5-나2', title: 'B', mis: true });
  sessionBooks.set('005.9-다3', { call: '005.9-다3', title: 'C', mis: true, resolved: true });
  saveDashLog(5, 1, 1, 2);                            // 전송 기록 1건 저장
  show('dash');
  return {
    active: document.getElementById('view-dash').classList.contains('active'),
    ok: document.getElementById('d-ok').textContent,
    mis: document.getElementById('d-mis').textContent,
    done: document.getElementById('d-done').textContent,
    logN: document.getElementById('dash-log').children.length,
    logTxt: document.getElementById('dash-log').textContent,
    homeBtn: !!document.querySelector('[onclick*="dash"]'),
    saved: JSON.parse(localStorage.getItem('libar_dash')).length,
  };
});
await browser.close();

assert(r.active, 'dash 화면 미표시');
assert(r.ok === '1' && r.mis === '1' && r.done === '1', `KPI 집계: ok ${r.ok} mis ${r.mis} done ${r.done} (기대 1/1/1)`);
assert(r.logN === 1 && /확인 5/.test(r.logTxt) && /오배열 1/.test(r.logTxt), `기록 렌더: ${r.logN}건 "${r.logTxt.trim().slice(0, 60)}"`);
assert(r.homeBtn, '홈에 점검 현황 진입 버튼 없음');
assert(r.saved === 1, `localStorage 저장 ${r.saved}건`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_dash — KPI 1/1/1 · 전송 기록 1건 렌더 · 홈 진입 OK`);
