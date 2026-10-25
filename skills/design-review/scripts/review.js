#!/usr/bin/env node
// shoot.js、audit.js、form_test.js を、参加登録ページとお礼ページ(thanks.html)についてまとめて実行する。
// 途中で NG が出ても最後まで実行する。
//
// 使い方:
//   node review.js http://localhost:8000/ review/<団体>-<日付> [--mock-port 8799]
//
// 書き出すもの: <書き出し先>/shots/、audit.md、form_test.json、thanks/(お礼ページのスクリーンショットと点検)
// 終了コード: どれかに NG や失敗があれば 1
'use strict';

const path = require('path');
const { spawnSync } = require('child_process');
const { parseArgs } = require('./lib');

const { pos, opts } = parseArgs(process.argv.slice(2));
const [url, outDir = 'review'] = pos;
if (!url) {
  console.error('使い方: node review.js <URL> [書き出し先] [--mock-port 番号]');
  process.exit(1);
}
const thanks = new URL('thanks.html', url).href;
const mock = opts['mock-port'] ? ['--mock-port', String(opts['mock-port'])] : [];
const runs = [
  ['shoot.js', url, path.join(outDir, 'shots')],
  ['audit.js', url, outDir],
  ['form_test.js', url, outDir, ...mock],
  ['shoot.js', thanks, path.join(outDir, 'thanks'), '--viewports', 'desktop,phone'],
  ['audit.js', thanks, path.join(outDir, 'thanks')],
];

const failed = [];
for (const [script, ...args] of runs) {
  console.log(`\n== ${script} ${args.join(' ')}`);
  const r = spawnSync(process.execPath, [path.join(__dirname, script), ...args], { stdio: 'inherit' });
  if (r.status !== 0) failed.push(`${script} ${args[0]}`);
}
console.log(failed.length ? `\nNG や失敗があったもの: ${failed.join('、')}` : '\nすべて終わりました。NG はありません');
process.exit(failed.length ? 1 : 0);
