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
  const withReads = items.filter(i => i.reads.length).length;
  pick(items[0].cands[0]?.call || '909-테스트');       // 첫 조각 답변
  pick('__skip');                                      // 둘째는 스킵 (전송 제외 확인)
  pick('__notlabel');                                  // 셋째는 검출 오탐 표시 (하드 네거티브 분리)
  hits('909');                                         // 카탈로그 검색 동작
  const nHits = document.getElementById('hits').children.length;
  hits('375.226 교52ㅇ');                              // 목록 밖 책 → 직접 입력 버튼 (스페이스→하이픈)
  const directBtn = document.querySelector('#hits button')?.textContent || '';
  hits('김65ㄷ v.2 c.2');                              // 라벨 표기(v./c.) → 전산 표기(-N=N) 변환 검색
  const volHit = document.getElementById('hits').innerHTML.includes('912-김65ㄷ-2=2');
  hits('005.133-모27ㅋ-2');                            // 오타(57→27) → 근사 추천
  const nearHit = document.getElementById('hits').innerHTML.includes('005.133-모57ㅋ-2');
  hits('594.5 김64ㅁ');                                // 접두 이웃(594.54)이 잡혀도 직접 입력 버튼 공존
  const h = document.getElementById('hits').innerHTML;
  const coexist = h.includes('594.54-김64ㅁ') && h.includes('594.5-김64ㅁ');
  await submitLabels();
  window.fetch = orig;
  if (!captured) return { err: '전송 fetch 미호출' };
  const zip = await JSZip.loadAsync(captured.zip, { base64: true });
  const meta = JSON.parse(await zip.file('labels.json').async('string'));
  return { name: captured.name, n: meta.labels.length, skipped: meta.skipped,
           notlabels: meta.notlabels.length,
           withReads, directBtn, volHit, nearHit, coexist,
           id: meta.labels[0].id, call: meta.labels[0].call, nCands, nHits, total: items.length };
});
// 분담 시작점: 새 기기에서 #s=300 → 300번부터 (기존 진행 기기는 저장 위치 우선)
const p2 = await browser.newPage();
await p2.evaluateOnNewDocument(() => localStorage.clear());     // 새 기기 조건 (저장 위치 우선 규칙과 분리)
await p2.goto('http://localhost:8791/webdemo/label.html#s=300', { waitUntil: 'load', timeout: 60000 });
await p2.waitForFunction(() => typeof items !== 'undefined' && items.length > 0, { timeout: 30000 });
const startPos = await p2.evaluate(() => pos);
await browser.close();

assert(!out.err, out.err);
assert(startPos === 300, `분담 시작점 실패: pos ${startPos} ≠ 300`);
assert(out.name.startsWith('libar_labels_'), `zip 이름 규칙 위반: ${out.name}`);
assert(out.n === 1 && out.skipped === 1 && out.notlabels === 1,
       `답변/스킵/라벨아님 분리 실패: ${out.n}/${out.skipped}/${out.notlabels}`);
// 라벨링 배치는 글자 줄이 검출된 조각만 담아야 한다 (빈 모서리 조각이 1번으로 뜬 사고 회귀 방지)
assert(out.withReads / out.total >= 0.5, `판독줄 있는 조각 비율 붕괴: ${out.withReads}/${out.total}`);
assert(/^\d{13}_crop_\d+$/.test(out.id), `id 형식 이상(병합 불가): ${out.id}`);
assert(out.nHits > 0, '카탈로그 검색 결과 0');
assert(out.volHit, '권차·복본 표기 변환 검색 실패 (v.2 c.2 → -2=2)');
assert(out.nearHit, '오타 근사 추천 실패 (모27ㅋ → 모57ㅋ)');
assert(out.coexist, '접두 이웃 히트 시 직접 입력 버튼 소실 (594.5 김64ㅁ)');
assert(out.directBtn.includes('375.226-교52ㅇ'), `목록 밖 직접 입력 버튼 실패: ${out.directBtn.slice(0, 60)}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_label — 배치 ${out.total}개 · 후보 ${out.nCands} · 검색 ${out.nHits}건 · 전송 ${out.name} (${out.id}→${out.call})`);
