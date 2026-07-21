// 초안2용 화면 캡처: 기능별 실행 결과 묶음 (폰 비율 390×760, 배율 2)
import puppeteer from 'puppeteer-core';
import { CHROME, URL } from './util.mjs';

const OUT = 'C:/Users/ain06/AppData/Local/Temp/claude/c--Users-ain06-OneDrive----2026---------------/0ddd6241-69e9-48f8-afe6-eeb71a4cf0cf/scratchpad/';
const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', protocolTimeout: 600000 });
const page = await browser.newPage();
await page.setViewport({ width: 390, height: 760, deviceScaleFactor: 2 });
await page.evaluateOnNewDocument(() => localStorage.setItem('libar_optin', '1'));
await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
await page.evaluate(async () => { await sessReady; });

const shot = async name => { await new Promise(r => setTimeout(r, 400)); await page.screenshot({ path: OUT + name }); console.log(name); };

// ① 홈
await shot('v2_home.png');

// ② 도서찾기 검색
await page.evaluate(() => { openFind(); });
await page.waitForFunction('typeof findIdx !== "undefined" && findIdx && findIdx.length > 0', { timeout: 60000, polling: 500 });
await page.evaluate(() => { const q = document.getElementById('find-q'); q.value = '재즈'; q.oninput({ target: q }); });
await shot('v2_find.png');

// ③ 길안내 지도
await page.evaluate(() => {
  const b = findIdx.find(x => x.title.includes('다락방의 재즈')) || findIdx.find(x => x.call.startsWith('673.53'));
  guideSection(b);
});
await shot('v2_guide.png');

// ④ 서가 판독 결과 — AR 박스 화면과 시트 화면 각 1장
await page.evaluate(async () => { await ensureRec(() => {}); });
await page.evaluate(async () => {
  findTarget = null;                                   // 구간 안내가 남긴 찾기 모드 해제
  show('scan');
  document.getElementById('cam').classList.add('hidden');
  const img = document.getElementById('photo');
  img.src = 'demo/demo1.jpg'; await img.decode();
  await scanImage(img, '내 서가');
  setSheet(false);
});
await shot('v2_scan_ar.png');
await page.evaluate(() => setSheet(true));
await shot('v2_scan_sheet.png');

// ⑤ 오배열 근거 팝업 (합성 밴드 — test_reason과 동일 재료)
await page.evaluate(() => {
  setSheet(false);
  const mk = (call, x) => ({ band: 0, call, how: '청구기호', title: '', box: [x, 40, x + 60, 240] });
  const rows = [mk('005.1-가1', 10), mk('005.5-나2', 90), mk('005.2-다3', 170), mk('005.3-라4', 250)];
  flagMisplaced(rows);
  lastImg = mkCanvas(390, 300); lastRows = rows;
  showReason(rows.find(r => r.mis), rows);
});
await shot('v2_reason.png');

// ⑥ 사서 대시보드
await page.evaluate(() => { hideReason(); saveDashLog(14, 1, 1, 2); show('dash'); renderDash(); });
await shot('v2_dash.png');

await browser.close();
console.log('완료');
