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
const fs = require('fs');
const { fileURLToPath } = require('url');
const { spawnSync } = require('child_process');
const { parseArgs } = require('./lib');

// 参加登録ページの中の、同じフォルダのページへのリンク(about.html、./privacy.html など)を集める。
// 探せなかったときは null を返す(点検しなかったページがあることを、失敗として知らせる)
async function linkedPages(url) {
  try {
    let html;
    if (url.startsWith('file:')) {
      const file = fileURLToPath(url);
      html = fs.readFileSync(fs.statSync(file).isDirectory() ? path.join(file, 'index.html') : file, 'utf8');
    } else {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      html = await res.text();
    }
    const names = new Set();
    for (const m of html.matchAll(/href=["'](?:\.\/)?([A-Za-z0-9_][A-Za-z0-9._-]*)\.html(?:[?#][^"']*)?["']/g)) {
      if (!['index', 'thanks'].includes(m[1])) names.add(m[1]);
    }
    return [...names];
  } catch (e) {
    console.error(`つないだページを探せませんでした: ${e.message}`);
    return null;
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
  const failed = [];
  const linked = await linkedPages(url);
  if (linked === null) failed.push('つないだページの点検(ページを探せませんでした)');
  for (const name of linked || []) {
    const pageUrl = new URL(`${name}.html`, url).href;
    runs.push(['shoot.js', pageUrl, path.join(outDir, 'pages', name), '--viewports', 'desktop,phone']);
    runs.push(['audit.js', pageUrl, path.join(outDir, 'pages', name)]);
  }

  for (const [script, ...args] of runs) {
    console.log(`\n== ${script} ${args.join(' ')}`);
    const r = spawnSync(process.execPath, [path.join(__dirname, script), ...args], { stdio: 'inherit' });
    if (r.status !== 0) failed.push(`${script} ${args[0]}`);
  }
  console.log(failed.length ? `\nNG や失敗があったもの: ${failed.join('、')}` : '\nすべて終わりました。NG はありません');
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
