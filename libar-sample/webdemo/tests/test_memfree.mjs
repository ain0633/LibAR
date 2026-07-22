// 백그라운드 메모리 방어 (7/22 현장 크래시 대응): ①hidden 진입 → _det 캐시·_hiCnv 해제
//   ②복귀 후 detect 정상 재생성 ③미동의 cropBag 상한 300 트림(최신분 유지)
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp({ optin: false });

const r = await page.evaluate(async () => {
  // ① 검출 1회로 캐시 채우고 원샷 캔버스 흉내
  await detect(mkCanvas(120, 60), 960);
  _hiCnv = mkCanvas(10, 10);
  const before = { det: Object.keys(_det).length, hi: !!_hiCnv };
  // hidden 위장 후 visibilitychange 발화
  Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
  document.dispatchEvent(new Event('visibilitychange'));
  const freed = { det: Object.keys(_det).length, hi: _hiCnv === null };
  // ② 복귀 → 다음 검출이 캐시를 다시 만든다
  Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
  await detect(mkCanvas(120, 60), 960);
  const rebuilt = !!_det[960];
  // ③ 미동의 cropBag 350개 선적재 → bagCrops 1회 → 300개로 트림 + 방금 조각(최신 scan)이 남아야
  for (let i = 0; i < 350; i++) cropBag.push({ blob: new Blob(['x']), call: 'old', how: null, box: [0,0,1,1], scan: -1 });
  const c = mkCanvas(40, 40); c.getContext('2d').fillRect(0, 0, 40, 40);
  await bagCrops(c, [{ call: '123-테45ㅅ', how: '청구기호', box: [2, 2, 30, 30] }]);
  return { before, freed, rebuilt, bagN: cropBag.length, newest: cropBag[cropBag.length - 1].call };
});
await browser.close();

assert(r.before.det >= 1 && r.before.hi, `사전 상태 이상: ${JSON.stringify(r.before)}`);
assert(r.freed.det === 0 && r.freed.hi, `hidden 해제 실패: ${JSON.stringify(r.freed)}`);
assert(r.rebuilt, '복귀 후 detect 캐시 재생성 실패');
assert(r.bagN === 300 && r.newest === '123-테45ㅅ', `cropBag 상한 실패: ${r.bagN}개, 최신 ${r.newest}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log('PASS test_memfree — hidden 시 _det·_hiCnv 해제 · 복귀 재생성 · 미동의 cropBag 300 상한 OK');
