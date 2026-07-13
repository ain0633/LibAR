// JS 이식 파리티: golden_cases.json (파이썬 정답) vs libar_rec.js
import { createRequire } from 'module';
import { readFileSync } from 'fs';
const require = createRequire(import.meta.url);
const L = require('./libar_rec.js');

const golden = JSON.parse(readFileSync(new URL('./golden_cases.json', import.meta.url), 'utf-8'));
const cat = JSON.parse(readFileSync(new URL('./demo/catalog.json', import.meta.url), 'utf-8'));
const idx = L.prepCatalog(cat);

let ok = 0, bad = [];
for (const c of golden.match) {
  const [row, sc] = L.matchCall(c.read, idx);
  const call = row ? row.call : null;
  if (call === c.call && Math.abs(sc - c.score) < 1e-3) ok++;
  else bad.push({ read: c.read, py: c.call, pyScore: c.score, js: call, jsScore: +sc.toFixed(4) });
}
console.log(`match: ${ok}/${golden.match.length}`);
for (const b of bad.slice(0, 10)) console.log('  ≠', JSON.stringify(b));

let ok2 = 0, bad2 = [];
for (const c of golden.lis) {
  const mis = [...L.lisMisplaced(c.calls.map(L.sortkey))].sort((a, b) => a - b);
  if (JSON.stringify(mis) === JSON.stringify(c.mis)) ok2++;
  else bad2.push({ calls: c.calls, py: c.mis, js: mis });
}
console.log(`lis: ${ok2}/${golden.lis.length}`);
for (const b of bad2.slice(0, 5)) console.log('  ≠', JSON.stringify(b));
process.exit(bad.length || bad2.length ? 1 : 0);
