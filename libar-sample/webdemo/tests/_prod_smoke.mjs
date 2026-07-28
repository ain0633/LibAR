// 일회용 진단: 실배포 사이트(ainsof.dev) 스모크 — 판독 E2E + 오늘 배포한 3기능(찾기 핀 팝업·
// 탐색 발견 정지·이중인식 기본화) + 진짜 오류 수집(ORT [W] 소음 제외)
import puppeteer from 'puppeteer-core';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new' });
const page = await browser.newPage();
const errs = [];
page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 160)));
page.on('console', m => { if (m.type() === 'error' && !m.text().includes('onnxruntime')) errs.push('console: ' + m.text().slice(0, 160)); });

// ① 전체 판독 E2E (#autotest = 데모 사진 → 검출·인식·매칭·판정·이중인식)
await page.goto('https://ainsof.dev/libar-demo/#autotest', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#testout', { timeout: 300000 });
const out = JSON.parse((await page.$eval('#testout', el => el.textContent))
  .replace(/^@@TESTOUT@@/, '').replace(/@@END@@$/, ''));
const env = await page.evaluate(() => ({ ver: APP_VER + ' · ' + APP_UPDATED, dual: _dualOn, dualN: _dualN }));

// ② 찾기 핀 팝업 + 발견 정지
const find = await page.evaluate(() => {
  const mk = (call, x) => ({ band: 0, call, how: '청구기호', score: 1.0, box: [x, 0, x + 10, 20] });
  findTarget = { call: '673.53-황24ㄷ', title: '다락방 재즈', sec: '673 식품가공' };
  live = true; document.getElementById('still-ov').style.display = 'flex';
  foundStop([mk('673.52-가11ㄱ', 0), mk('673.53-황24ㄷ', 20)]);
  document.getElementById('ar').children[0]?.click();
  const p = document.getElementById('discPop');
  const r = { stop: !live, btn: document.getElementById('btn-live').textContent,
              pop: p.style.display === 'block', text: p.textContent.slice(0, 80) };
  hideDisc(); findTarget = null;
  return r;
});

// ③ 탐색 발견 정지 + 앰버 핀 팝업 (동봉 인기대출 실데이터)
const disc = await page.evaluate(async () => {
  await discData('pop');
  const first = [..._disc.pop.keys()][0];
  const rows = [{ band: 0, call: first, how: '청구기호', score: 1.0, box: [0, 0, 10, 20] }];
  live = true;
  discMode = 'pop';
  discStop(rows, 1);
  const pins = [...document.getElementById('ar').children].filter(e => e.style.cursor === 'pointer');
  pins[0]?.click();
  const p = document.getElementById('discPop');
  const r = { stop: !live, pinN: pins.length, pop: p.style.display === 'block',
              msg: document.getElementById('scan-title').textContent };
  hideDisc(); setDiscMode(null);
  return r;
});
await browser.close();

const fail = [];
if (out.err !== null) fail.push(`판독 오류 ${out.err}`);
if (out.ok < 14) fail.push(`확인 ${out.ok} < 14`);
if (!env.dual) fail.push('이중인식 기본화 꺼짐');
if (!(find.stop && find.pop && find.text.includes('다락방 재즈') && find.btn === '▶ 재개')) fail.push(`찾기 ${JSON.stringify(find)}`);
if (!(disc.stop && disc.pinN >= 1 && disc.pop && disc.msg.includes('핀을 탭'))) fail.push(`탐색 ${JSON.stringify(disc)}`);
if (errs.length) fail.push(`오류 ${errs.length}건: ${errs.slice(0, 3).join(' | ')}`);
console.log(JSON.stringify({ env, ok: out.ok, mis: out.mis, dualN: env.dualN, find, disc, errs: errs.length }, null, 1));
console.log(fail.length ? '❌ FAIL: ' + fail.join(' · ') : '✅ 프로덕션 스모크 전부 통과');
process.exit(fail.length ? 1 : 0);
