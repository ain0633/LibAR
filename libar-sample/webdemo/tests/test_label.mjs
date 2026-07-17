// 라벨링 페이지 경로: 배치 로드 → 답변 → 드라이브 전송(스텁) — zip 이름 규칙·내용물 게이트
// libar_labels_* 이름이라 크롭 변환기(libar_crops_*)와 자동 분리 — 이름 위반 = 오염 위험
import puppeteer from 'puppeteer-core';
import { CHROME, assert } from './util.mjs';

const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new' });
const page = await browser.newPage();
const errs = [];
page.on('pageerror', e => errs.push(String(e).slice(0, 100)));
await page.goto('http://localhost:8791/webdemo/label.html', { waitUntil: 'load', timeout: 60000 });
// items는 최상위 let — window 속성이 아니라 전역 렉시컬 바인딩이라 typeof로 확인
await page.waitForFunction(() => typeof items !== 'undefined' && items.length > 0, { timeout: 30000 });

const out = await page.evaluate(async () => {
  let captured = null;
  const orig = window.fetch;
  window.fetch = (u, o) => String(u).includes('script.google')
    ? (captured = JSON.parse(o.body), Promise.resolve(new Response('', { status: 200 })))
    : orig(u, o);
  const nCands = items[0].cands.length;
  pick(items[0].cands[0]?.call || '909-테스트');       // 첫 조각 답변
  pick('__skip');                                      // 둘째는 스킵 (전송 제외 확인)
  hits('909');                                         // 카탈로그 검색 동작
  const nHits = document.getElementById('hits').children.length;
  await submitLabels();
  window.fetch = orig;
  if (!captured) return { err: '전송 fetch 미호출' };
  const zip = await JSZip.loadAsync(captured.zip, { base64: true });
  const meta = JSON.parse(await zip.file('labels.json').async('string'));
  return { name: captured.name, n: meta.labels.length, skipped: meta.skipped,
           id: meta.labels[0].id, call: meta.labels[0].call, nCands, nHits, total: items.length };
});
await browser.close();

assert(!out.err, out.err);
assert(out.name.startsWith('libar_labels_'), `zip 이름 규칙 위반: ${out.name}`);
assert(out.n === 1 && out.skipped === 1, `답변/스킵 분리 실패: 답변 ${out.n}·스킵 ${out.skipped}`);
assert(/^\d{13}_crop_\d+$/.test(out.id), `id 형식 이상(병합 불가): ${out.id}`);
assert(out.nHits > 0, '카탈로그 검색 결과 0');
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_label — 배치 ${out.total}개 · 후보 ${out.nCands} · 검색 ${out.nHits}건 · 전송 ${out.name} (${out.id}→${out.call})`);
