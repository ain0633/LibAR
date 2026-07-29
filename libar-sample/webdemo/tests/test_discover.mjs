// 이용자 탐색 경로: ①🔥인기대출 토글 → 목록 교집합 책에 핀 ②핀 탭 → 서지 팝업(제목·대출횟수)
//   ③⭐사서추천 전환 → 추천사 팝업 ④재토글 → 핀·팝업 해제. 동봉 JSON 실데이터로 검증.
import { openApp, assert } from './util.mjs';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const pop = JSON.parse(readFileSync(path.join(HERE, '../demo/popular_daelim.json'), 'utf8'));
const rec = JSON.parse(readFileSync(path.join(HERE, '../demo/recommend_daelim.json'), 'utf8'));
const popB = pop[0];
const recB = rec.find(b => b.note && b.note.length > 20) || rec[0];

const { browser, page, errs } = await openApp();
await page.evaluate(async () => { await sessReady; });
// 동봉 JSON 선로드 — 긴 fetch를 evaluate 안에서 기다리면 부하 시 프라미스가 GC에 수거된다(폴링으로 대기)
await page.evaluate(() => { discData('pop'); discData('rec'); });
await page.waitForFunction('_disc.pop && _disc.rec', { timeout: 30000, polling: 300 });

const r = await page.evaluate(async ([popCall, recCall]) => {
  const mk = (call, x) => ({ band: 0, call, how: call ? '청구기호' : null, box: [x, 0, x + 10, 20] });
  show('scan');
  findTarget = null;
  lastImg = mkCanvas(140, 30);
  lastRows = [mk(popCall, 0), mk('099.999-없33ㅁ', 40), mk(recCall, 80)];
  const pins = () => [...document.getElementById('ar').children].filter(e => e.style.cursor === 'pointer');
  await toggleDisc('pop');
  const popPins = pins().length;
  const popTitleMsg = document.getElementById('scan-title').textContent;
  pins()[0].click();
  const popPop = document.getElementById('discPop');
  const popShown = popPop.style.display === 'block';
  const popText = popPop.textContent;
  await toggleDisc('rec');                              // pop → rec 직접 전환
  const recPins = pins().length;
  pins()[0]?.click();
  const recText = document.getElementById('discPop').textContent;
  await toggleDisc('rec');                              // 끄기
  const offPins = pins().length;
  const offPop = document.getElementById('discPop').style.display === 'none';
  // ⑤ 라이브 발견 정지(discStop): 자동판독에서 탐색 도서를 찾으면 정지 화면 전환 + 탭 가능 핀
  //    (라이브 박스엔 식별이 없어 핀을 걸 수 없다 — 07-28 "핀 탭해도 팝업 안 뜸" 수리)
  await toggleDisc('pop');
  live = true;
  document.getElementById('still-ov').style.display = 'flex';
  discStop(lastRows, 1);
  const stop = { liveOff: !live, ovOff: document.getElementById('still-ov').style.display === 'none',
                 btn: document.getElementById('btn-live').textContent,
                 msg: document.getElementById('scan-title').textContent,
                 pinN: pins().length };
  pins()[0]?.click();
  stop.popup = document.getElementById('discPop').style.display === 'block';
  await toggleDisc('pop');                              // 정리
  return { popPins, popTitleMsg, popShown, popText, recPins, recText, offPins, offPop, stop };
}, [popB.call, recB.call]);
// 도서찾기 탭 경로: 검색/추천/인기 선택지 + 스캔 알림표(pill) 연동
await page.evaluate(() => { openFind(); });
await page.waitForFunction('typeof findIdx !== "undefined" && findIdx && findIdx.length > 0', { timeout: 60000, polling: 500 });
const tabs = await page.evaluate(async (popCall) => {
  await findTab('pop');
  const popRows = document.getElementById('find-list').children.length;
  const pillOn = !document.getElementById('disc-pill').classList.contains('hidden');
  const inputHidden = document.getElementById('find-q').classList.contains('hidden');
  await findTab('rec');
  const recRows = document.getElementById('find-list').children.length;
  await findTab('search');
  const afterSearch = { pillOff: document.getElementById('disc-pill').classList.contains('hidden'),
                        discOff: discMode === null };
  // ⑥ A안(목록 스캔): 배너 버튼 → 특정 책 지정 없이 discMode 유지 채 스캔 진입 = 전체 핀 모드의 진입점
  await findTab('pop');
  const scanBtn = !!document.querySelector('#find-list button');
  discScan();
  const listScan = { view: document.getElementById('view-scan').classList.contains('active'),
                     ft: findTarget === null, dm: discMode === 'pop',
                     pill: !document.getElementById('disc-pill').classList.contains('hidden'),
                     photoBtnHidden: document.getElementById('btn-photocheck').classList.contains('hidden') };
  setDiscMode(null);
  // ⑦ 목록에서 한 권 선택(guideSection) → 탐색 배너·discMode 해제 (한 권 찾기 ↔ 전체 핀 배타 — 07-28 "추천사 왜 안 꺼져" 수리)
  //    + 찾기 핀 팝업에 대출횟수·추천사 곁들임 (07-28 요청)
  await findTab('pop');
  guideSection({ call: popCall, title: '테스트', sec: '800번대', room: '3층 종합자료실' });
  showFindInfo();
  const pick = { ft: !!findTarget, dm: discMode === null,
                 pill: document.getElementById('disc-pill').classList.contains('hidden'),
                 rich: document.getElementById('discPop').textContent.includes('회 대출') };
  hideDisc();
  findTarget = null;
  return { popRows, pillOn, inputHidden, recRows, ...afterSearch, scanBtn, listScan, pick };
}, popB.call);
await browser.close();

assert(r.popPins === 1, `인기대출 핀 수: ${r.popPins} (기대 1)`);
assert(r.popTitleMsg.includes('1권'), `인기대출 안내 문구: ${r.popTitleMsg}`);
assert(r.popShown && r.popText.includes(popB.title.slice(0, 8)), `인기대출 팝업 내용: ${r.popText.slice(0, 60)}`);
assert(r.popText.includes('대출'), `대출횟수 표기 없음: ${r.popText.slice(0, 60)}`);
assert(r.recPins === 1, `사서추천 핀 수: ${r.recPins} (기대 1)`);
assert(r.recText.includes(recB.title.slice(0, 8)) && r.recText.includes(recB.note.slice(0, 10)),
       `추천사 표기 없음: ${r.recText.slice(0, 80)}`);
assert(r.offPins === 0 && r.offPop, `해제 후 잔존: 핀 ${r.offPins}, 팝업 ${r.offPop}`);
assert(tabs.popRows > 10 && tabs.recRows > 10, `탭 목록 부족: pop ${tabs.popRows} rec ${tabs.recRows}`);
assert(tabs.pillOn && tabs.inputHidden, `인기 탭 상태: pill ${tabs.pillOn}, 검색창 숨김 ${tabs.inputHidden}`);
assert(tabs.pillOff && tabs.discOff, `검색 탭 복귀 후 해제 실패: pill숨김 ${tabs.pillOff}, disc ${tabs.discOff}`);
assert(tabs.scanBtn, '목록 스캔 버튼(A안) 부재');
assert(tabs.listScan.view && tabs.listScan.ft && tabs.listScan.dm && tabs.listScan.pill && tabs.listScan.photoBtnHidden,
       `목록 스캔 진입 상태: ${JSON.stringify(tabs.listScan)} (기대 스캔뷰·findTarget無·discMode 유지·pill·사서버튼 숨김)`);
assert(r.stop.liveOff && r.stop.ovOff && r.stop.btn === '▶ 재개', `탐색 발견 정지 실패: ${JSON.stringify(r.stop)}`);
assert(r.stop.pinN >= 1 && r.stop.popup && r.stop.msg.includes('핀을 탭'),
       `탐색 정지 핀·팝업: ${JSON.stringify(r.stop)} (기대 핀 1+·팝업 열림·안내 문구)`);
assert(tabs.pick.ft && tabs.pick.dm && tabs.pick.pill,
       `한 권 선택 후 탐색 잔존: ${JSON.stringify(tabs.pick)} (기대 findTarget有·discMode無·pill 숨김)`);
assert(tabs.pick.rich, `찾기 핀 팝업 대출횟수 곁들임 부재: ${JSON.stringify(tabs.pick)}`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_discover — 🔥핀·서지·대출횟수 · 전환·해제 · 발견 정지 핀·팝업 · 한권선택 시 탐색 해제 · 찾기 탭(pop ${tabs.popRows}·rec ${tabs.recRows}행)·pill 연동 OK`);
