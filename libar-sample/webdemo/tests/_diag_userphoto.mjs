// 진단: 현장 문제 사진을 배포 파이프라인 그대로 돌려 단계별(검출→밴드 인식 원문→매칭) 분해
// 사용법: node _diag_userphoto.mjs <demo/ 안 파일명> [batch]
//   기본 = 단건 rec(현재 배포판=원복판과 동일 경로), 'batch' 인자 시 배치 경로(사설 브랜치 코드)
import { openApp } from './util.mjs';
import { writeFileSync } from 'fs';

const file = process.argv[2] || '_diag_user.jpg';
const useBatch = process.argv.includes('batch');

const { browser, page, errs } = await openApp();
await page.evaluate(async () => { await sessReady; await ensureRec(() => {}); });

const r = await page.evaluate(async ([file, useBatch]) => {
  if (!useBatch) recBackend = '단건에뮬';            // 배포(원복)판과 같은 단건 recLine 경로 강제 — 세션은 그대로
  const orig = stripTokens;
  window._bandToks = [];
  stripTokens = async (...a) => { const t = await orig(...a); _bandToks.push(t.map(k => k.t)); return t; };
  const img = document.getElementById('photo');
  show('scan');
  img.src = 'demo/' + encodeURIComponent(file); await img.decode();
  const t0 = performance.now();
  await scanImage(img, '진단');
  const ms = Math.round(performance.now() - t0);
  snapReport(img, lastRows);                         // 0권이어도 리포트 합성 가능하게 명시 스냅
  const rep = await buildReport();
  const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(',')[1]); fr.readAsDataURL(rep.blob); });
  return {
    사진: `${img.naturalWidth}×${img.naturalHeight}`, 전체ms: ms, recMs: Math.round(lastRecMs),
    백엔드: backend + '/' + recBackend, 검출박스: lastRows.length, rec줄: lastRecN,
    확인: rep.ok, 오배열: rep.mis,
    rows: lastRows.map(x => ({ xc: Math.round((x.box[0] + x.box[2]) / 2), band: x.band,
                               call: x.call, how: x.how, mis: !!x.mis })).sort((a, b) => a.xc - b.xc),
    밴드별인식원문: _bandToks, rep: b64,
  };
}, [file, useBatch]);
writeFileSync(`_진단리포트_${useBatch ? 'batch' : 'single'}.jpg`, Buffer.from(r.rep, 'base64'));
delete r.rep;
console.log(JSON.stringify(r, null, 1));
if (errs.length) console.log('페이지 오류:', errs);
console.log(`리포트 저장: tests/_진단리포트_${useBatch ? 'batch' : 'single'}.jpg`);
