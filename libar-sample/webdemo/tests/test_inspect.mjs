// 사서용 사진 점검 경로: ①12MP 사진 판독(기존 1280 검출 경로) ②점검 기록 누적(휘발 방지)
//   ③여러 장 → 한 zip 묶음(report_N.jpg + summary.json). 라이브와 별개 입구라 회귀 없이 검증.
//   zip 검증은 앱에 이미 로드된 JSZip으로 페이지 안에서 실제 해제해 확인.
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp();
await page.evaluate(async () => { await sessReady; await ensureRec(() => {}); });

const r = await page.evaluate(async () => {
  const img = document.getElementById('photo');
  show('scan');
  for (const n of [1, 2]) {                            // 데모 2장을 사진 점검 경로로 순차 판독
    img.src = `demo/demo${n}.jpg`; await img.decode();
    await scanImage(img, '📷 사진 점검');
    if (lastRows && lastRows.some(x => x.call)) await logInspection();
  }
  const { zip, ok, mis, n } = await buildReportZip();
  const reload = await JSZip.loadAsync(await zip.generateAsync({ type: 'base64' }), { base64: true });
  const files = Object.keys(reload.files).sort();
  const summary = JSON.parse(await reload.file('summary.json').async('string'));
  const cnt = document.getElementById('insp-count');
  return { logN: _inspLog.length, ok, mis, n, files,
           photos: summary.photos, items: summary.items.length,
           r1: !!reload.file('report_1.jpg'), r2: !!reload.file('report_2.jpg'),
           counterShown: !cnt.classList.contains('hidden'), counterText: cnt.textContent };
});
await browser.close();

assert(r.logN === 2, `점검 기록 누적 실패: ${r.logN}장`);
assert(r.n === 2 && r.r1 && r.r2, `묶음 구조 이상: ${r.files.join(',')}`);
assert(r.files.includes('summary.json'), 'summary.json 누락');
assert(r.photos === 2 && r.items === 2, `summary 불일치: photos ${r.photos}, items ${r.items}`);
assert(r.ok >= 13, `점검 판독 회귀: 확인 ${r.ok}권 (< 13)`);   // 사진 경로=기존 판독력 유지
assert(r.counterShown && /점검 2장/.test(r.counterText), `카운터 미표시: ${r.counterText}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_inspect — 점검 ${r.logN}장 누적 · 묶음 ${r.files.length}파일(${r.files.join(',')}) · 확인 ${r.ok}권 · 오배열 ${r.mis}`);
