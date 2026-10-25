#!/usr/bin/env node
// 参加登録フォームとスマホ下部のボタンが、約束どおりに動くかを確かめる。
// lp-build のテンプレートの目印(form[data-signup]、#f-name、#f-mail、.form-status、#join-done、
// [data-hero-cta]、[data-sticky-cta]、#join)を使う。
//
// 使い方:
//   node form_test.js http://localhost:8000/ [review] [--mock-port 8799]
//
// 送信先のかわりに、ローカルに仮の送信先(成功、500 エラー)を立てて確かめる。
// 仮の送信先のポートは、--mock-port で決められる(省くと空いている番号を使う)。
// 終了コード: 失敗があれば 1
'use strict';

const http = require('http');
const path = require('path');
const fs = require('fs');
const { launch, parseArgs, openPage, ensureDir } = require('./lib');

function mockEndpoint(port = 0) {
  const received = [];
  const server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Headers', '*');
    if (req.method === 'OPTIONS') { res.end(); return; }
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      received.push({ url: req.url, body });
      if (req.url === '/fail') { res.statusCode = 500; res.end('{}'); return; }
      res.setHeader('Content-Type', 'application/json');
      res.end('{"ok":true}');
    });
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve({ server, received, base: `http://127.0.0.1:${server.address().port}` })));
}

(async () => {
  const { pos, opts } = parseArgs(process.argv.slice(2));
  const [url, outDir] = pos;
  if (!url) {
    console.error('使い方: node form_test.js <URL> [書き出し先] [--mock-port 番号]');
    process.exit(1);
  }
  const mock = await mockEndpoint(opts['mock-port'] ? Number(opts['mock-port']) : 0);
  const browser = await launch();
  const results = [];
  const record = (name, ok, detail = '') => {
    results.push({ name, ok, detail });
    console.log(`${ok ? 'OK  ' : 'NG  '} ${name}${detail ? ` … ${detail}` : ''}`);
  };
  const desktop = { name: 'desktop', width: 1440, height: 900, dpr: 1 };
  const phone = { name: 'phone', width: 390, height: 844, dpr: 2 };
  const allErrors = [];

  // expectErrors: わざと送信を失敗させるテストでは、そのエラーを数えない
  const fresh = async (vp = desktop, expectErrors = false) => {
    const o = await openPage(browser, url, vp);
    if (!expectErrors) allErrors.push(o.log.errors);
    return o;
  };
  const state = (page) => page.evaluate(() => ({
    status: document.querySelector('.form-status')?.textContent || '',
    nameErr: document.getElementById('f-name-err')?.textContent || '',
    mailErr: document.getElementById('f-mail-err')?.textContent || '',
    focus: document.activeElement?.id || document.activeElement?.tagName,
    mail: document.getElementById('f-mail')?.value,
    formDisplay: getComputedStyle(document.querySelector('form[data-signup]')).display,
    doneWidth: document.getElementById('join-done')?.getBoundingClientRect().width || 0,
    btnDisabled: document.querySelector('form[data-signup] [type="submit"]')?.disabled,
    signups: (window.dataLayer || []).filter((e) => e && e.event === 'sign_up').length,
  }));
  const setForm = (page, endpoint, redirect) => page.evaluate(([e, r]) => {
    const f = document.querySelector('form[data-signup]');
    f.dataset.endpoint = e;
    f.dataset.redirect = r;
  }, [endpoint, redirect]);
  const submit = (page) => page.click('form[data-signup] [type="submit"]');

  try {
    let o = await fresh();
    if (!(await o.page.$('form[data-signup]'))) {
      record('フォームがある', false, 'form[data-signup] が見つかりません');
      throw new Error('stop');
    }

    // 1. 何も入れずに送る
    await submit(o.page); await o.page.waitForTimeout(250);
    let s = await state(o.page);
    record('空で送るとエラーが出る', !!(s.nameErr && s.mailErr && s.status), `${s.nameErr} / ${s.mailErr}`);
    record('空で送ると最初の欄にフォーカスが移る', s.focus === 'f-name', `フォーカス: ${s.focus}`);

    // 2. 直すとまとめの表示が消える
    await o.page.fill('#f-name', 'テスト');
    await o.page.fill('#f-mail', 'test@example.com');
    s = await state(o.page);
    record('直すと送信時のまとめが消える', s.status === '', `まとめ: 「${s.status}」`);

    // 3. 形の悪いメールアドレス
    await o.page.fill('#f-mail', 'abc@def');
    await submit(o.page); await o.page.waitForTimeout(250);
    s = await state(o.page);
    record('形の悪いメールアドレスを止める', !!s.mailErr && s.focus === 'f-mail', s.mailErr);
    await o.context.close();

    // 4. 全角のメールアドレスと、ページ内に完了を出す動き
    o = await fresh();
    await setForm(o.page, '', '');
    await o.page.fill('#f-name', 'テスト');
    await o.page.fill('#f-mail', 'ｔｅｓｔ＠ｅｘａｍｐｌｅ．ｃｏｍ　');
    await submit(o.page); await o.page.waitForTimeout(400);
    s = await state(o.page);
    record('全角のメールアドレスを半角にそろえる', s.mail === 'test@example.com', `値: ${s.mail}`);
    record('送信先が空で移動先も空なら、ページ内に完了を出す', s.formDisplay === 'none' && s.doneWidth > 200, `フォーム ${s.formDisplay}、完了の幅 ${Math.round(s.doneWidth)}px`);
    record('送信できたら sign_up を記録する', s.signups === 1, `${s.signups} 件`);
    await o.context.close();

    // 5. 送信先がエラーを返す
    o = await fresh(desktop, true);
    await setForm(o.page, `${mock.base}/fail`, 'thanks.html');
    await o.page.fill('#f-name', 'テスト');
    await o.page.fill('#f-mail', 'test@example.com');
    await o.page.focus('form[data-signup] [type="submit"]');
    await o.page.keyboard.press('Enter'); await o.page.waitForTimeout(1200);
    s = await state(o.page);
    record('送信先のエラーを知らせ、ボタンを戻す', !!s.status && s.btnDisabled === false, `表示: ${s.status}`);
    record('エラーのあとボタンにフォーカスを戻す', s.focus === 'BUTTON', `フォーカス: ${s.focus}`);
    await o.context.close();

    // 6. 送信先が成功を返す → 移動先へ
    o = await fresh();
    const before = mock.received.length;
    await setForm(o.page, `${mock.base}/ok`, 'thanks.html');
    await o.page.fill('#f-name', 'テスト');
    await o.page.fill('#f-mail', 'test@example.com');
    await Promise.all([o.page.waitForURL('**/thanks.html', { timeout: 8000 }).catch(() => null), submit(o.page)]);
    const sent = mock.received.slice(before).find((r) => r.url === '/ok');
    record('送信できたら移動先のページへ移る', o.page.url().endsWith('thanks.html'), o.page.url());
    record('見えない欄(website)は送らない', !!sent && !/name="website"/.test(sent.body), sent ? `${sent.body.length} バイト` : '届いていません');
    await o.context.close();

    // 7. ボットが見えない欄を埋めた
    o = await fresh();
    const before2 = mock.received.length;
    await setForm(o.page, `${mock.base}/ok`, '');
    await o.page.fill('#f-name', 'テスト');
    await o.page.fill('#f-mail', 'test@example.com');
    await o.page.evaluate(() => { document.querySelector('input[name="website"]').value = 'spam'; });
    await submit(o.page); await o.page.waitForTimeout(500);
    record('見えない欄が埋まっていたら送らない', mock.received.length === before2);
    await o.context.close();

    // 8. スマホ下部のボタン
    o = await fresh(phone);
    if (await o.page.$('[data-sticky-cta]')) {
      const on = () => o.page.evaluate(() => document.querySelector('[data-sticky-cta]').classList.contains('is-on'));
      const top = await on();
      await o.page.evaluate(() => window.scrollTo({ top: 1600, behavior: 'instant' })); await o.page.waitForTimeout(500);
      const middle = await on();
      await o.page.evaluate(() => document.getElementById('join').scrollIntoView({ behavior: 'instant' })); await o.page.waitForTimeout(500);
      const atForm = await on();
      record('スマホ下部のボタン: 最初の画面では隠す', top === false);
      record('スマホ下部のボタン: 途中では出す', middle === true);
      record('スマホ下部のボタン: フォームが見えたら隠す', atForm === false);
    }
    await o.context.close();
  } catch (e) {
    if (e.message !== 'stop') { console.error(e); record('テストを最後まで実行する', false, String(e).slice(0, 160)); }
  }

  const errors = allErrors.flat();
  record('ページのエラーがない', errors.length === 0, errors.slice(0, 3).join(' / '));
  await browser.close();
  mock.server.close();

  if (outDir) {
    ensureDir(outDir);
    fs.writeFileSync(path.join(outDir, 'form_test.json'), JSON.stringify(results, null, 2));
  }
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed} / ${results.length} 件 OK`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
