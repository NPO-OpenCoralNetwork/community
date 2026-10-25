// design-review のスクリプトで共通に使うもの
'use strict';

const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

// 確かめる画面の大きさ。スマホ2つ、タブレット、ノートパソコン、パソコン
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900, dpr: 1 },
  { name: 'laptop', width: 1366, height: 768, dpr: 1 },
  { name: 'tablet', width: 820, height: 1180, dpr: 1 },
  { name: 'phone', width: 390, height: 844, dpr: 2 },
  { name: 'small', width: 320, height: 640, dpr: 2 },
];

function loadPlaywright() {
  const tries = [
    () => require('playwright'),
    () => require(process.env.PW_PATH),
    () => require(path.join(execSync('npm root -g', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(), 'playwright')),
  ];
  for (const t of tries) {
    try { return t(); } catch (_) { /* 次を試す */ }
  }
  console.error('Playwright が見つかりません。リポジトリのルートで npm install と npx playwright install chromium を実行してください。');
  process.exit(2);
}

async function launch() {
  const { chromium } = loadPlaywright();
  const options = {};
  // プロキシ経由の環境では Google Fonts などをプロキシで取り、ローカルのサーバーは直接見る
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  if (proxy) options.proxy = { server: proxy, bypass: 'localhost,127.0.0.1' };
  return chromium.launch(options);
}

function pickViewports(arg) {
  if (!arg) return VIEWPORTS;
  const names = arg.split(',');
  return VIEWPORTS.filter((v) => names.includes(v.name));
}

function parseArgs(argv) {
  const pos = [];
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) opts[key] = true;
      else { opts[key] = next; i++; }
    } else pos.push(a);
  }
  return { pos, opts };
}

async function openPage(browser, url, vp) {
  const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.dpr });
  const page = await context.newPage();
  const log = { errors: [], failed: [] };
  page.on('console', (m) => { if (m.type() === 'error') log.errors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => log.errors.push('pageerror: ' + String(e).slice(0, 200)));
  page.on('requestfailed', (r) => log.failed.push(r.url()));
  page.on('response', (r) => { if (r.status() >= 400) log.failed.push(`${r.status()} ${r.url()}`); });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
  return { context, page, log };
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

module.exports = { VIEWPORTS, launch, pickViewports, parseArgs, openPage, ensureDir };
