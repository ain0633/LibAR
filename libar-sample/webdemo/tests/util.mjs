// 공용: 브라우저 띄우기 + 앱 로드. 서버(8791)는 run_all.mjs가 보장한다.
import puppeteer from 'puppeteer-core';

export const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
export const URL = 'http://localhost:8791/webdemo/app.html';

export async function openApp({ camera = false, hash = '', optin = true } = {}) {
  const args = camera ? ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] : [];
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e).slice(0, 100)));
  if (optin) await page.evaluateOnNewDocument(() => localStorage.setItem('libar_optin', '1'));
  await page.goto(URL + hash, { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(async () => { await sessReady; });
  return { browser, page, errs };
}

export function assert(cond, msg) { if (!cond) throw new Error('ASSERT: ' + msg); }
