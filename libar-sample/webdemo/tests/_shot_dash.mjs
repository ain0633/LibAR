// 일회용: dash_build.py 산출 HTML 스크린샷 (육안 확인용)
import puppeteer from 'puppeteer-core';
const file = process.argv[2], out = process.argv[3];
const browser = await puppeteer.launch({ channel: 'chrome', headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 900, height: 1400 });
await page.goto('file:///' + file.replace(/\\/g, '/'));
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log('saved', out);
