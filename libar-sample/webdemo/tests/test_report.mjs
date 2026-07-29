// 리포트 경로: 판독 → 리포트 합성 → 드라이브 전송(fetch 스텁) — zip 이름 규칙·내용물·권수 게이트
// 이름이 libar_report_*가 아니면 변환기(libar_crops_* 글롭)가 학습 재료로 오인한다 — 최우선 검증
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ hash: '#autotest' });
await page.waitForSelector('#testout', { timeout: 300000 });

const sent = await page.evaluate(async () => {
  localStorage.setItem('libar_report_ok', '1');          // 첫 사용 confirm 생략
  let captured = null;
  const orig = window.fetch;
  window.fetch = (u, o) => String(u).includes('script.google')
    ? (captured = JSON.parse(o.body), Promise.resolve(new Response('', { status: 200 })))
    : orig(u, o);
  await sendReport();
  window.fetch = orig;
  if (!captured) return { err: '업로드 fetch가 호출되지 않음 (sendReport 내부 실패?)' };
  const zip = await JSZip.loadAsync(captured.zip, { base64: true });
  if (!zip.file('report.jpg') || !zip.file('report.json')) return { err: 'zip 내용물 누락' };
  const meta = JSON.parse(await zip.file('report.json').async('string'));
  const jpg = await zip.file('report.jpg').async('uint8array');
  return { name: captured.name, ok: meta.ok, mis: meta.mis, books: meta.books.length,
           bandOk: meta.books.every(b => typeof b.band === 'number'),   // 진단 필드: 칸(band) 보존
           howOk: meta.books.every(b => typeof b.how === 'string'),     // 진단 필드: 직독/복구 보존
           jpgKB: Math.round(jpg.length / 1024) };
});
await browser.close();

assert(!sent.err, sent.err);
assert(sent.name.startsWith('libar_report_'), `zip 이름 규칙 위반(변환기 오염 위험): ${sent.name}`);
assert(sent.ok >= 13, `리포트 확인 권수 회귀: ${sent.ok} < 13`);
assert(sent.books >= sent.ok, `판정 목록 누락: books ${sent.books} < ok ${sent.ok}`);
assert(sent.bandOk, '리포트 books에 band(칸) 필드 누락 — 현장 판정 진단 불가');
assert(sent.howOk, '리포트 books에 how(직독/복구) 필드 누락 — 현장 판정 진단 불가');
assert(sent.jpgKB > 30, `리포트 이미지가 비정상적으로 작음: ${sent.jpgKB}KB`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_report — ${sent.name} · 확인 ${sent.ok}·오배열 ${sent.mis} · 이미지 ${sent.jpgKB}KB`);
