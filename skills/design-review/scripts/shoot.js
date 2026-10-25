#!/usr/bin/env node
// 画面の大きさごとにスクリーンショットを撮り、基本の数値を測る。
//
// 使い方:
//   node shoot.js http://localhost:8000/ review/shots
//   node shoot.js <URL> <書き出し先> --viewports desktop,phone --full desktop,phone
//
// 書き出すもの:
//   <名前>_first.png  最初の画面
//   <名前>_full.png   ページ全体(--full で指定した大きさだけ。既定は desktop と phone)
//   shoot.json        数値(ページの高さ、画面数、横のはみ出し、最初の画面のボタンが見えるか、エラーなど)
'use strict';

const path = require('path');
const fs = require('fs');
const { launch, pickViewports, parseArgs, openPage, ensureDir } = require('./lib');

(async () => {
  const { pos, opts } = parseArgs(process.argv.slice(2));
  const [url, outDir = 'review/shots'] = pos;
  if (!url) {
    console.error('使い方: node shoot.js <URL> <書き出し先> [--viewports desktop,phone] [--full desktop,phone]');
    process.exit(1);
  }
  ensureDir(outDir);
  const fullFor = (opts.full && opts.full !== true ? opts.full : 'desktop,phone').split(',');
  const browser = await launch();
  const results = [];

  for (const vp of pickViewports(opts.viewports)) {
    const { context, page, log } = await openPage(browser, url, vp);
    const m = await page.evaluate(() => {
      const rect = (s) => { const el = document.querySelector(s); return el ? el.getBoundingClientRect() : null; };
      const hero = rect('.hero');
      const cta = rect('[data-hero-cta]');
      const sticky = document.querySelector('[data-sticky-cta]');
      const res = performance.getEntriesByType('resource');
      const nav = performance.getEntriesByType('navigation')[0];
      const bytes = res.reduce((n, r) => n + (r.transferSize || 0), 0) + (nav ? nav.transferSize || 0 : 0);
      const imgs = res.filter((r) => /\.(avif|webp|jpe?g|png|gif|svg)(\?|$)/.test(r.name))
        .map((r) => ({ file: r.name.split('/').pop(), kb: Math.round((r.transferSize || r.encodedBodySize || 0) / 1024) }));
      return {
        pageHeight: document.documentElement.scrollHeight,
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
        heroHeight: hero ? Math.round(hero.height) : null,
        heroCtaBottom: cta ? Math.round(cta.bottom) : null,
        stickyDisplay: sticky ? getComputedStyle(sticky).display : null,
        transferKB: Math.round(bytes / 1024),
        images: imgs,
      };
    });
    const r = {
      viewport: vp.name, width: vp.width, height: vp.height,
      ...m,
      screens: +(m.pageHeight / vp.height).toFixed(1),
      heroCtaVisible: m.heroCtaBottom == null ? null : m.heroCtaBottom <= vp.height,
      consoleErrors: log.errors, failedRequests: log.failed,
    };
    results.push(r);
    await page.screenshot({ path: path.join(outDir, `${vp.name}_first.png`) });
    if (fullFor.includes(vp.name)) await page.screenshot({ path: path.join(outDir, `${vp.name}_full.png`), fullPage: true });
    await context.close();

    const flags = [];
    if (r.overflowX > 0) flags.push(`横に ${r.overflowX}px はみ出し`);
    if (r.heroCtaVisible === false) flags.push('最初の画面のボタンが画面の外');
    if (r.consoleErrors.length) flags.push(`エラー ${r.consoleErrors.length}件`);
    if (r.failedRequests.length) flags.push(`読み込み失敗 ${r.failedRequests.length}件`);
    console.log(`${vp.name.padEnd(8)} ${vp.width}x${vp.height}  高さ ${r.pageHeight}px(${r.screens}画面)  転送 ${r.transferKB}KB  ${flags.join('、') || '問題なし'}`);
  }

  await browser.close();
  fs.writeFileSync(path.join(outDir, 'shoot.json'), JSON.stringify(results, null, 2));
  console.log(`書き出しました: ${outDir}`);
})().catch((e) => { console.error(e); process.exit(1); });
