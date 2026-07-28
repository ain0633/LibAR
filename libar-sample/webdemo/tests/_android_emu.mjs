// 일회용 진단: 실배포 사이트를 안드로이드(Pixel 7) 에뮬레이션으로 스모크
// — Blink 엔진 + 안드로이드 UA·화면·터치에서 전체 판독 E2E(#autotest)와 레이아웃 확인
import puppeteer from 'puppeteer-core';

const PIXEL7 = {
  userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
  viewport: { width: 412, height: 915, deviceScaleFactor: 2.625, isMobile: true, hasTouch: true },
};

const browser = await puppeteer.launch({
  channel: 'chrome', headless: 'new',
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
});
const page = await browser.newPage();
await page.emulate(PIXEL7);
const errs = [];
page.on('pageerror', e => errs.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

// 1) 실배포 사이트 + #autotest = 데모 사진 전체 판독 파이프라인 (검출→인식→매칭→판정)
await page.goto('https://ainsof.dev/libar-demo/#autotest', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#testout', { timeout: 300000 });
const out = JSON.parse((await page.$eval('#testout', el => el.textContent))
  .replace(/^@@TESTOUT@@/, '').replace(/@@END@@$/, ''));
const env = await page.evaluate(() => ({
  ver: typeof APP_VER !== 'undefined' ? APP_VER + ' ' + APP_UPDATED : '?',
  backend, recBackend,
  ua: navigator.userAgent.includes('Android'),
  imageCapture: typeof window.ImageCapture !== 'undefined',
  rvfc: 'requestVideoFrameCallback' in HTMLVideoElement.prototype,
  offscreen: typeof OffscreenCanvas !== 'undefined',
}));

// 2) 홈 화면 레이아웃 스크린샷 (모바일 뷰포트 렌더 확인)
await page.evaluate(() => show('home'));
await page.screenshot({ path: process.argv[2] || '_android_home.png' });

await browser.close();
console.log(JSON.stringify({ out, env, errs }, null, 1));
