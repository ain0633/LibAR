// 배포 게이트: node tests/run_all.mjs — 전부 PASS여야 배포한다.
//
// ◆ 철칙 (07-16 가로모드 먹통 사후 규정) ◆
// 새 기능·수정을 배포하기 전, "그 코드 경로 자체를 두드리는" 테스트를 여기에 추가한다.
// 옛 경로 테스트만 초록인 채 배포하는 것 금지 — 가로모드 레이스는 회전 테스트가
// 없어서 현장(광수쌤 폰)이 첫 테스트가 됐다. 특히 정지→재시작, async 루프, 동시성을
// 건드리면 반드시 "폭풍(연타) 테스트"를 짝으로 만든다.
import { spawn, execSync } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');                 // libar-sample (서버 루트)

// 8791 서버 보장
let server = null;
try { execSync('curl -s -o NUL http://localhost:8791/webdemo/app.html'); }
catch {
  server = spawn('py', ['-3.12', '-m', 'http.server', '8791'], { cwd: ROOT, stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 1500));
}

// 1) 골든 로직 (node, 브라우저 불필요 — 매칭·LIS 파리티 144/5)
const golden = execSync('node test_rec_logic.mjs', { cwd: path.resolve(HERE, '..'), encoding: 'utf8' });
if (!/match: 144\/144/.test(golden) || !/lis: 5\/5/.test(golden)) {
  console.error('FAIL golden:', golden.trim()); process.exit(1);
}
console.log('PASS golden — ' + golden.trim().replace(/\n/g, ' · '));

// 2) 브라우저 E2E — 순차 실행 (WebGPU 세션 경합 방지)
const tests = ['test_scan.mjs', 'test_report.mjs', 'test_live.mjs', 'test_rotate.mjs', 'test_collect.mjs'];
let failed = 0;
for (const t of tests) {
  try {
    execSync(`node ${t}`, { cwd: HERE, encoding: 'utf8', stdio: 'inherit', timeout: 420000 });
  } catch { failed++; console.error(`FAIL ${t}`); }
}
if (server) server.kill();
console.log(failed ? `\n❌ ${failed}개 실패 — 배포 금지` : '\n✅ 전부 통과 — 배포 가능');
process.exit(failed ? 1 : 0);
