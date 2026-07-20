// 도서찾기 후보·확률 경로: ①직독 일치=98% 단독 핀 ②틈의 유일 후보=95% ③후보 2권=45%씩
//   ④화면 밖=방향 안내 ⑤찾기 모드 오버레이는 후보만 렌더(다른 박스 숨김)
//   ⑥화면 밖 권수 거리(카탈로그 순서) ⑦구간(sec) 다르면 구간 리다이렉트
import { openApp, assert } from './util.mjs';

const { browser, page, errs } = await openApp();
await page.evaluate(async () => { await sessReady; await loadCatalogRaw(); });

const r = await page.evaluate(() => {
  const mk = (call, x, band = 0) => ({ band, call, how: call ? '청구기호' : null,
                                       box: [x, 0, x + 10, 20] });
  findTarget = { call: '673.53-황24ㄷ', title: '다락방 재즈' };
  // ① 직독 일치
  const A = findCandidates([mk('673.52-가11ㄱ', 0), mk('673.53-황24ㄷ', 20), mk('674-다33ㄷ', 40)]);
  // ② 확정 이웃 사이 미판독 1권 = 유일 후보
  const B = findCandidates([mk('673.52-가11ㄱ', 0), mk(null, 20), mk('674-다33ㄷ', 40)]);
  // ③ 사이 미판독 2권 = 확률 분할
  const C = findCandidates([mk('673.52-가11ㄱ', 0), mk(null, 20), mk(null, 40), mk('674-다33ㄷ', 60)]);
  // ④ 전부 타깃보다 앞 = 오른쪽 안내
  const D = findCandidates([mk('570-가11ㄱ', 0), mk('600-나22ㄴ', 20)]);
  // ⑤ 찾기 모드 오버레이: 후보만 렌더 (live=false)
  const rows = [mk('673.52-가11ㄱ', 0), mk(null, 20), mk('674-다33ㄷ', 40), mk(null, 60)];
  drawBoxes(mkCanvas(100, 30), rows);
  const arN = document.getElementById('ar').children.length;
  // ⑥ 권수 거리: 카탈로그 정렬에서 같은 구간·중복 없는 창(i, i+15)을 골라 거리=15 검증
  const ord = findOrder();
  let i6 = -1;
  for (let i = 0; i < ord.length - 15; i++)
    if (_findPos.get(ord[i].call) === i && _findPos.get(ord[i + 15].call) === i + 15
        && ord[i].sec === ord[i + 15].sec) { i6 = i; break; }
  findTarget = { call: ord[i6 + 15].call };
  const E = findCandidates([mk(ord[i6].call, 0)]);       // 보이는 책보다 뒤 → 오른쪽 + 거리 15
  // ⑦ 구간 리다이렉트: 다른 sec의 책을 타깃으로
  let j7 = -1;
  for (let j = i6 + 1; j < ord.length; j++)
    if (ord[j].sec !== ord[i6].sec && _findPos.get(ord[j].call) === j) { j7 = j; break; }
  findTarget = { call: ord[j7].call };
  const F = findCandidates([mk(ord[i6].call, 0)]);
  const F_sec = ord[j7].sec;
  findTarget = null;
  return { A, B, C, D, arN, E, F, F_sec };
});
await browser.close();

assert(r.A.mode === 'hit' && r.A.list[0].p === 98, `직독 일치: ${JSON.stringify(r.A).slice(0, 60)}`);
assert(r.B.mode === 'cand' && r.B.list.length === 1 && r.B.list[0].p === 95, `유일 후보: ${JSON.stringify(r.B).slice(0, 60)}`);
assert(r.C.mode === 'cand' && r.C.list.length === 2 && r.C.list[0].p === 45, `후보 2권 분할: ${JSON.stringify(r.C).slice(0, 60)}`);
assert(r.D.mode === 'none' && r.D.dir === '오른쪽', `방향 안내: ${JSON.stringify(r.D)}`);
assert(r.arN === 1, `찾기 오버레이가 후보만 렌더해야 함: ${r.arN}개 (기대 1 — 틈 안 후보만, 틈 밖 미판독 제외)`);
assert(r.E.mode === 'none' && r.E.dir === '오른쪽' && r.E.n === 15 && !r.E.sec,
       `권수 거리: ${JSON.stringify(r.E)} (기대 오른쪽·15권·같은 구간)`);
assert(r.F.mode === 'none' && r.F.sec === r.F_sec, `구간 리다이렉트: ${JSON.stringify(r.F)} (기대 sec=${r.F_sec})`);
assert(errs.length === 0, `페이지 오류: ${errs}`);
console.log(`PASS test_find — 직독 98% · 유일 후보 95% · 2후보 45%씩 · 방향 안내 · 오버레이 후보만 렌더 · 거리 15권 · 구간 리다이렉트`);
