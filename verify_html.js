// 铁律一验证：V1/V2 RAW求和须与total一致（V2），V1求和在0-100范围
// V2RAW 结构: [code,name,type,board, C1..H1(13维, idx4-16), delisted(17), note(18), controller(19), controller_cat(20), total(21)]
const fs = require('fs');
const html = fs.readFileSync('baokeng-rank.html', 'utf8');

function extractArray(name) {
  const re = new RegExp('const ' + name + ' = (\\[[\\s\\S]*?\\n\\]);');
  const m = html.match(re);
  if (!m) throw new Error(name + ' not found');
  return JSON.parse(m[1].replace(/,(\s*\n\])/, '$1'));
}

const RAW = extractArray('RAW');
const V2RAW = extractArray('V2RAW');

let bad1 = 0, bad2 = 0, mismatch = 0;
RAW.forEach(r => {
  const s = r.slice(5, 19).reduce((a, b) => a + b, 0);
  if (s < 0 || s > 100) { bad1++; console.log('V1 out-of-range', r[0], s); }
});
V2RAW.forEach(r => {
  let s = r.slice(4, 17).reduce((a, b) => a + b, 0);
  if (r[4] === 0) s = Math.min(s, 50);
  if (r[13] === 0) s = Math.min(s, 50);
  if (r[12] === 0) s = Math.min(s, 30);
  const t = r[21];
  if (s !== t) { bad2++; console.log('V2 sum!=total', r[0], 'sum=', s, 'total=', t); }
});
const c1 = new Set(RAW.map(r => r[0])), c2 = new Set(V2RAW.map(r => r[0]));
c1.forEach(c => { if (!c2.has(c)) mismatch++; });
console.log('V1 rows:', RAW.length, '| V2 rows:', V2RAW.length, '| row len:', V2RAW[0].length);
console.log('V1 out-of-range:', bad1, '| V2 sum!=total:', bad2, '| V2 missing codes:', mismatch);

// 统计卡等级分布（V2口径、非退市）
const lv = { A: 0, B: 0, C: 0, D: 0 };
V2RAW.forEach(r => {
  if (r[17]) return;
  let s = r.slice(4, 17).reduce((a, b) => a + b, 0);
  if (r[4] === 0) s = Math.min(s, 50);
  if (r[13] === 0) s = Math.min(s, 50);
  if (r[12] === 0) s = Math.min(s, 30);
  lv[s > 70 ? 'A' : s > 50 ? 'B' : s > 30 ? 'C' : 'D']++;
});
console.log('V2 active level dist:', JSON.stringify(lv));

// 莫高原样核对
const mg = V2RAW.find(r => r[0] === '600543');
const mgs = mg.slice(4, 17).reduce((a, b) => a + b, 0);
console.log('莫高V2 sum=' + mgs, '| total=' + mg[21], '| level=' + (mgs > 70 ? 'A' : mgs > 50 ? 'B' : mgs > 30 ? 'C' : 'D'), '| 实控人=' + mg[19], '| 分类=' + mg[20]);

// JS 语法检查
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
fs.writeFileSync('_check.js', script);
try {
  require('child_process').execSync('node --check _check.js', { stdio: 'pipe' });
  console.log('JS syntax: OK');
} catch (e) {
  console.log('JS syntax ERROR:', e.stderr ? e.stderr.toString() : e.message);
}
