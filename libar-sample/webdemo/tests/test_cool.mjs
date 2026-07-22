// 발열 절감 2종 (7/22 현장 발열 대응 — 성능·속도 무손실 설계 검증):
//   ① 정지 화면 검출 게이트: frameDiff 동일/변경 판별 · motGate 연속 3회 상한 · 움직임 즉시 복귀
//   ② 셔터(판독) 중 카메라 센서 휴면: showStill → track.enabled false, hideStill → 복귀
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ camera: true });

const r = await page.evaluate(async () => {
  // ① frameDiff / motGate 단위 검증
  const c = mkCanvas(320, 240), g = c.getContext('2d');
  g.fillStyle = '#666'; g.fillRect(0, 0, 320, 240);
  _motPrev = null; _motSkip = 0; _motRows = null;
  frameDiff(c);                                        // 첫 호출(기준 없음) = 255
  const dSame = frameDiff(c);                          // 동일 화면 → 0
  g.fillStyle = '#fff'; g.fillRect(0, 0, 160, 240);
  const dMove = frameDiff(c);                          // 절반 변경 → 큼
  _motRows = [{}];                                     // 재사용할 직전 박스 존재 가정
  frameDiff(c);                                        // 기준 갱신(다시 정지 상태)
  const dStill = frameDiff(c);
  const skips = [motGate(dStill), motGate(dStill), motGate(dStill), motGate(dStill)];  // 상한 3회
  const resume = motGate(50);                          // 움직임 → 즉시 정상 검출
  // ② 라이브 → 셔터 중 센서 휴면 → 복귀
  show('scan');
  await toggleLive();
  await new Promise(r => setTimeout(r, 800));
  const enLive = stream.getVideoTracks().every(t => t.enabled);
  const still = mkCanvas(64, 48);
  still.getContext('2d').fillRect(0, 0, 64, 48);       // convertToBlob은 렌더링 컨텍스트 필수
  await showStill(still);
  const enStill = stream.getVideoTracks().some(t => t.enabled);
  const camHidden = document.getElementById('cam').classList.contains('hidden');
  hideStill();
  const enBack = stream.getVideoTracks().every(t => t.enabled);
  const camBack = !document.getElementById('cam').classList.contains('hidden');
  await toggleLive(false);
  return { dSame, dMove, skips, resume, enLive, enStill, camHidden, enBack, camBack };
});
await browser.close();

assert(r.dSame < 3, `동일 화면 변화량 ${r.dSame} (기대 <3)`);
assert(r.dMove > 10, `변경 화면 변화량 ${r.dMove} (기대 >10)`);
assert(r.skips.join() === 'true,true,true,false', `생략 상한 3회 실패: ${r.skips}`);
assert(r.resume === false, '움직임 감지 후에도 생략됨');
assert(r.enLive, '라이브 시작 시 트랙 비활성');
assert(!r.enStill && r.camHidden, `셔터 중 센서 미휴면: enabled=${r.enStill}, camHidden=${r.camHidden}`);
assert(r.enBack && r.camBack, `셔터 복귀 실패: enabled=${r.enBack}, cam=${r.camBack}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log('PASS test_cool — 정지 게이트(동일<3·변경>10·상한3·복귀) · 셔터 중 센서 휴면/복귀 OK');
