// A안 원샷 경로: 라이브 중 hiShot 3단(ImageCapture→승격→폴백) — 어떤 단이 잡히든
// ①캔버스를 돌려주고 ②스트림이 살아 있고 ③이후 라이브 루프가 계속 돌아야 한다.
// (승격 실패 기기 = 폴백으로 기존 동작과 동일해야 회귀가 없다)
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ camera: true });
await page.evaluate(() => toggleLive());
await new Promise(r => setTimeout(r, 2500));

const out = await page.evaluate(async () => {
  const cam = document.getElementById('cam');
  if (!cam.videoWidth) return { err: '카메라 프레임 없음' };
  const fc = mkCanvas(cam.videoWidth, cam.videoHeight);
  fc.getContext('2d').drawImage(cam, 0, 0);
  const hi = await hiShot(fc);
  await new Promise(r => setTimeout(r, 800));          // 원복 재협상 여유
  return {
    fcW: fc.width, hiW: hi.width, hiH: hi.height, info: _hiInfo,
    same: hi === fc,
    trackAlive: stream.getVideoTracks()[0].readyState,
    camAlive: cam.videoWidth > 0, liveOn: live,
  };
});
// 원샷 후에도 정지·재시작이 멀쩡한지 (회전 수술 때 잡은 레이스 계열 회귀 방지)
await page.evaluate(async () => { await toggleLive(false); toggleLive(); });
await new Promise(r => setTimeout(r, 1500));
const after = await page.evaluate(() => ({ liveOn: live, camW: document.getElementById('cam').videoWidth }));
await browser.close();

assert(!out.err, out.err);
assert(out.hiW > 0 && out.hiH > 0, `원샷 결과가 빈 캔버스: ${out.hiW}×${out.hiH}`);
assert(out.hiW >= out.fcW || out.same, `원샷이 프레임보다 작음(폴백도 아님): ${out.hiW} < ${out.fcW}`);
assert(out.trackAlive === 'live' && out.camAlive, `원샷 후 스트림 사망: ${out.trackAlive}`);
assert(out.liveOn, '원샷 후 라이브 플래그 꺼짐');
assert(after.liveOn && after.camW > 0, '원샷 후 정지→재시작 실패');
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_hishot — ${out.same ? '폴백(프레임 유지)' : out.info} · 프레임 ${out.fcW} → 원샷 ${out.hiW} · 스트림 생존`);
