#!/usr/bin/env node
// shoot.js、audit.js、form_test.js を、参加登録ページとお礼ページ(thanks.html)についてまとめて実行する。
// 参加登録ページからつないだ同じフォルダのページ(about.html など、lp-build の pages.yaml で作るページ)も、
// スクリーンショットを撮って点検する。途中で NG が出ても最後まで実行する。
//
// 使い方:
//   node review.js http://localhost:8000/ review/<団体>-<日付> [--mock-port 8799]
//
// 書き出すもの: <書き出し先>/shots/、audit.md、form_test.json、thanks/(お礼ページ)、pages/<名前>/(つないだページ)
// 終了コード: どれかに NG や失敗があれば 1
'use strict';

const path = require('path');
const { spawnSync } = require('child_process');
const { parseArgs } = require('./lib');

// 参加登録ページの中の、同じフォルダのページへのリンク(about.html など)を集める
async function linkedPages(url) {
  try {
    const html = await (await fetch(url)).text();
    const names = new Set();
    for (const m of html.matchAll(/href="([a-z0-9][a-z0-9-]*)\.html(?:#[^"]*)?"/g)) {
      if (!['index', 'thanks'].includes(m[1])) names.add(m[1]);
    }
    return [...names];
  } catch (e) {
    console.error(`つないだページを探せませんでした: ${e.message}`);
    return [];
  }
}

(async () => {
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
  for (const name of await linkedPages(url)) {
    const pageUrl = new URL(`${name}.html`, url).href;
    runs.push(['shoot.js', pageUrl, path.join(outDir, 'pages', name), '--viewports', 'desktop,phone']);
    runs.push(['audit.js', pageUrl, path.join(outDir, 'pages', name)]);
  }

  const failed = [];
  for (const [script, ...args] of runs) {
    console.log(`\n== ${script} ${args.join(' ')}`);
    const r = spawnSync(process.execPath, [path.join(__dirname, script), ...args], { stdio: 'inherit' });
    if (r.status !== 0) failed.push(`${script} ${args[0]}`);
  }
  console.log(failed.length ? `\nNG や失敗があったもの: ${failed.join('、')}` : '\nすべて終わりました。NG はありません');
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
