// 지연시간 벤치: 실제 실행 환경(브라우저)에서 워밍업 5회 + 100회 반복 — 평균·표준편차·P50·P99
// 검출(960, 라이브 경로)과 인식 1줄(fp16 rec) 각각. WebGPU 기본 + #wasm 폴백 재측정.
import { openApp } from './util.mjs';

function stats(a) {
  const s = [...a].sort((x, y) => x - y), n = s.length;
  const mean = s.reduce((p, c) => p + c, 0) / n;
  const sd = Math.sqrt(s.reduce((p, c) => p + (c - mean) ** 2, 0) / n);
  return { mean: mean.toFixed(1), sd: sd.toFixed(1), p50: s[Math.floor(n * 0.5)].toFixed(1),
           p99: s[Math.min(n - 1, Math.floor(n * 0.99))].toFixed(1) };
}

for (const hash of ['', '#wasm']) {
  const { browser, page } = await openApp({ hash });
  const r = await page.evaluate(async () => {
    show('scan');
    const img = document.getElementById('photo');           // 데모 12MP 사진 (실제 판독 입력)
    await ensureRec(() => {});
    // ── 검출 960 (라이브 프레임 경로): 워밍업 5 + 100회 ──
    for (let i = 0; i < 5; i++) await detect(img, 960);
    const det = [];
    for (let i = 0; i < 100; i++) { const t = performance.now(); await detect(img, 960); det.push(performance.now() - t); }
    // ── 인식 1줄 (fp16 rec, 48×320 고정 입력): 워밍업 5 + 100회 ──
    const c = mkCanvas(120, 40); const g = c.getContext('2d');
    g.drawImage(img, 500, 2800, 400, 130, 0, 0, 120, 40);   // 라벨 부근 실제 픽셀
    for (let i = 0; i < 5; i++) await recLine(c, 0, 0, 120, 40);
    const rec = [];
    for (let i = 0; i < 100; i++) { const t = performance.now(); await recLine(c, 0, 0, 120, 40); rec.push(performance.now() - t); }
    return { det, rec, be: backend, rbe: recBackend };
  });
  await browser.close();
  const d = stats(r.det), q = stats(r.rec);
  console.log(`[${r.be}/${r.rbe}] 검출960: 평균 ${d.mean}±${d.sd}ms · P50 ${d.p50} · P99 ${d.p99}`);
  console.log(`[${r.be}/${r.rbe}] 인식1줄: 평균 ${q.mean}±${q.sd}ms · P50 ${q.p50} · P99 ${q.p99}`);
}
