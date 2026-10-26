#!/usr/bin/env node
// ページを機械的に点検する。目で見る点検の前に、数字で分かることをそろえる。
//
// 使い方:
//   node audit.js http://localhost:8000/ review
//
// 書き出すもの: <書き出し先>/audit.json と audit.md
// 終了コード: NG があれば 1、なければ 0
//
// 点検すること
//   ページ全体: 見出しの順番、画像(最初の画面の読み込み優先度、遅延読み込み、幅と高さ、ファイルの有無)、
//              仮の値と残った記号(閉じた「よくある質問」と送信後の表示も読む)、行き先のないリンク、
//              フォームのラベルと欄の名前、送信先、SNS 用の画像の URL、和文の中の半角かっこ、
//              大見出しの書体で palt が効くか
//   画面の大きさごと: 横のはみ出し、最初の画面のボタンが見えるか、ページの長さ、押せるところの大きさ、
//              改行(1〜2文字だけの行、行頭の句読点)、写真の上の文字のコントラスト、無地の上の文字のコントラスト
'use strict';

const path = require('path');
const fs = require('fs');
const { launch, VIEWPORTS, parseArgs, openPage, ensureDir } = require('./lib');

const NG = 'NG';
const WARN = '要確認';
const OK = 'OK';

async function pageChecks(page) {
  return page.evaluate(() => {
    const NG = 'NG';
    const WARN = '要確認';
    const out = [];
    const add = (level, check, detail) => out.push({ level, check, detail });
    const visible = (el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0;
    };

    // 見出し
    const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')];
    const h1s = hs.filter((h) => h.tagName === 'H1');
    if (h1s.length !== 1) add(NG, '見出し', `h1 が ${h1s.length} 個あります(1つにする)`);
    let prev = 0;
    for (const h of hs) {
      const lv = +h.tagName[1];
      if (prev && lv > prev + 1) add(WARN, '見出し', `「${h.textContent.trim().slice(0, 20)}」で h${prev} から h${lv} に飛んでいます`);
      prev = lv;
    }

    // 画像
    const imgs = [...document.images];
    const hero = document.querySelector('.hero img, img[fetchpriority="high"]');
    if (hero) {
      if (hero.getAttribute('loading') === 'lazy') add(NG, '画像', '最初の画面の写真に loading="lazy" が付いています(表示が遅くなる)');
      if (hero.getAttribute('fetchpriority') !== 'high') add(WARN, '画像', '最初の画面の写真に fetchpriority="high" がありません');
    }
    for (const img of imgs) {
      const name = (img.currentSrc || img.src).split('/').pop();
      if (!img.hasAttribute('alt')) add(NG, '画像', `${name} に alt がありません`);
      else if (!img.alt.trim() && !img.closest('[aria-hidden="true"]')) add(WARN, '画像', `${name} の alt が空です(飾りでなければ内容を書く)`);
      if (!img.getAttribute('width') || !img.getAttribute('height')) add(WARN, '画像', `${name} に width と height がありません(読み込み中に画面がずれる)`);
      if (img !== hero && img.getAttribute('loading') !== 'lazy') add(WARN, '画像', `${name} に loading="lazy" がありません`);
      if (img.complete && img.naturalWidth === 0) add(NG, '画像', `${name} を表示できません`);
    }

    // 仮の値、残った記号、行き先のないリンク
    // 閉じている「よくある質問」の答えと、送信したあとに出る表示(hidden)も読むため、一時的に開く
    const closed = [...document.querySelectorAll('details:not([open])')];
    const hidden = [...document.querySelectorAll('body [hidden]')];
    closed.forEach((d) => d.setAttribute('open', ''));
    hidden.forEach((el) => el.removeAttribute('hidden'));
    const text = document.body.innerText;
    closed.forEach((d) => d.removeAttribute('open'));
    hidden.forEach((el) => el.setAttribute('hidden', ''));
    const ph = [...new Set([...(text.match(/\[[^\[\]\n]{1,60}\]/g) || []), ...(text.match(/[^\s、。]{0,12}(（仮）|\(仮\)|未定|TBD)/g) || [])])];
    if (ph.length) add(WARN, '仮の値', `公開前に決めること: ${ph.join('、')}`);
    if (/\{\{|\}\}/.test(document.documentElement.innerHTML)) add(NG, '仮の値', 'テンプレートの記号 {{ }} が残っています');
    if (/TODO/.test(text)) add(NG, '仮の値', 'TODO が表示されています');
    const broken = [...new Set(text.match(/(^|[^A-Za-z])(None|undefined|null|NaN)(?![A-Za-z])/g) || [])].map((m) => m.trim());
    if (broken.length) add(NG, '仮の値', `組み立ての誤りで出た文字があります: ${broken.join('、')}`);
    const dead = [...new Set([...document.querySelectorAll('a[href="#"]')].map((a) => a.textContent.trim()))];
    if (dead.length) add(WARN, 'リンク', `行き先がまだないリンク: ${dead.join('、')}`);
    for (const a of document.querySelectorAll('a[href^="#"]')) {
      const id = a.getAttribute('href').slice(1);
      if (id && !document.getElementById(id)) add(NG, 'リンク', `「${a.textContent.trim()}」の行き先 #${id} がありません`);
    }

    // フォーム
    for (const form of document.forms) {
      const bad = [...form.elements]
        .filter((el) => el.name && (el.name in HTMLFormElement.prototype || el.name in HTMLElement.prototype || el.name in Element.prototype))
        .map((el) => el.name);
      if (bad.length) add(NG, 'フォーム', `欄の名前がフォームの機能を上書きします: ${bad.join('、')}`);
      for (const el of form.querySelectorAll('input, select, textarea')) {
        if (el.type === 'hidden' || el.closest('[aria-hidden="true"]')) continue;
        if (!el.labels || !el.labels.length) if (!el.getAttribute('aria-label')) add(NG, 'フォーム', `ラベルのない欄があります(name=${el.name})`);
      }
      const mail = form.querySelector('input[type="email"]');
      if (mail && !mail.getAttribute('autocomplete')) add(WARN, 'フォーム', 'メール欄に autocomplete="email" がありません');
      if (form.hasAttribute('data-signup') && !(form.dataset.endpoint || '').trim()) {
        add(WARN, 'フォーム', '参加登録の送信先(data-endpoint)が空です。このまま公開すると、登録がどこにも届きません');
      }
    }

    // SNS で共有したときの画像は、https:// から始まる絶対 URL でないと出ない
    const og = document.querySelector('meta[property="og:image"]');
    if (og && !/^https:\/\//.test(og.content)) add(WARN, 'SNS', `og:image が絶対 URL ではありません(${og.getAttribute('content')})。lp-build では content.yaml の site.url を書いて組み立て直す`);

    // 和文の中の半角のかっことコロン
    const jp = '\\u3040-\\u30ff\\u4e00-\\u9fff';
    const re = new RegExp(`[${jp}][(:]|[)][${jp}]|[(][${jp}]`, 'g');
    const hits = [];
    for (const line of text.split('\n')) {
      let m;
      while ((m = re.exec(line)) && hits.length < 8) hits.push(line.slice(Math.max(0, m.index - 6), m.index + 8));
    }
    if (hits.length) add(WARN, '日本語', `和文の中に半角のかっこやコロンがあります: ${hits.map((h) => `「${h}」`).join(' ')}`);

    // 大見出しの書体で palt が効くか
    // テンプレートが見出しの約物を個別に詰めている(.pt)ときと、見出しに約物がないときは出さない
    const h1 = h1s[0];
    if (h1 && !h1.querySelector('.pt') && /[、。，．「」『』（）]/.test(h1.textContent)) {
      const cs = getComputedStyle(h1);
      const probe = (feature) => {
        const s = document.createElement('span');
        s.textContent = '、。「」（）';
        s.style.cssText = `position:absolute;visibility:hidden;white-space:nowrap;font-family:${cs.fontFamily};font-size:64px;font-weight:${cs.fontWeight};font-feature-settings:${feature}`;
        document.body.appendChild(s);
        const w = s.getBoundingClientRect().width;
        s.remove();
        return w;
      };
      const normal = probe('normal');
      const palt = probe('"palt"');
      if (Math.abs(normal - palt) < 1) add(WARN, '日本語', `大見出しの書体(${cs.fontFamily.split(',').slice(0, 2).join(',').replace(/"/g, '')})では、和文の約物に palt が効きません。字間や個別の詰めで調整しているか見る`);
    }
    return out;
  });
}

async function missingFiles(page, base) {
  const urls = await page.evaluate(() => {
    const set = new Set();
    for (const el of document.querySelectorAll('img[src], source[srcset], img[srcset]')) {
      if (el.getAttribute('src')) set.add(new URL(el.getAttribute('src'), location.href).href);
      for (const part of (el.getAttribute('srcset') || '').split(',')) {
        const u = part.trim().split(/\s+/)[0];
        if (u) set.add(new URL(u, location.href).href);
      }
    }
    for (const el of document.querySelectorAll('link[rel="stylesheet"][href], script[src]')) {
      set.add(new URL(el.getAttribute('href') || el.getAttribute('src'), location.href).href);
    }
    return [...set];
  });
  const missing = [];
  for (const u of urls) {
    if (!u.startsWith(new URL(base).origin)) continue;
    const res = await page.request.fetch(u, { method: 'HEAD' }).catch(() => null);
    if (!res || res.status() >= 400) missing.push(u.split('/').slice(-2).join('/'));
  }
  return missing;
}

async function viewportChecks(page, vp) {
  return page.evaluate(({ vp }) => {
    const NG = 'NG';
    const WARN = '要確認';
    const out = [];
    const add = (level, check, detail) => out.push({ level, check, detail, viewport: vp.name });
    const visible = (el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0;
    };

    const over = document.documentElement.scrollWidth - window.innerWidth;
    if (over > 0) add(NG, 'はみ出し', `横に ${over}px はみ出しています`);

    const cta = document.querySelector('[data-hero-cta]');
    if (cta) {
      const b = cta.getBoundingClientRect().bottom;
      if (b > window.innerHeight) add(NG, '最初の画面', `最初の画面のボタンが画面の外です(下端 ${Math.round(b)}px、画面 ${window.innerHeight}px)`);
    }

    const screens = document.documentElement.scrollHeight / window.innerHeight;
    // 長さの目安は参加登録ページ(最初の画面に写真があるページ)だけに当てる
    if (vp.name === 'phone' && document.querySelector('.hero') && screens > 9.5) add(WARN, '長さ', `スマホで ${screens.toFixed(1)} 画面あります(目安は7〜9画面)`);

    // 押せるところの大きさ(文中のリンクは除く)
    if (vp.width <= 820) {
      const small = [];
      for (const el of document.querySelectorAll('a, button, summary, label.opt, label.consent')) {
        if (!visible(el) || el.closest('.visually-hidden, [aria-hidden="true"]')) continue;
        if (el.tagName === 'A' && el.closest('p, li, dd, figcaption') && !el.classList.contains('btn')) continue;
        const r = el.getBoundingClientRect();
        if (r.height < 43.5) small.push(`「${el.textContent.trim().slice(0, 14)}」(高さ ${Math.round(r.height)}px)`);
      }
      if (small.length) add(WARN, '押しやすさ', `高さ 44px 未満: ${small.slice(0, 8).join('、')}`);
    }

    // 改行: 1〜2文字だけの最後の行、行頭の句読点、数字や時刻の途中、短い語の途中
    // 閉じている「よくある質問」の答えも見るため、一時的に開く
    const closed = [...document.querySelectorAll('details:not([open])')];
    closed.forEach((d) => d.setAttribute('open', ''));
    const punct = /[、。，．」』）〕】！？!?]/;
    const numChar = /[0-9０-９:：〜~]/;
    const seg = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('ja', { granularity: 'word' }) : null;
    const blocks = document.querySelectorAll('h1 > span, h2, h3, p, li, summary, figcaption, dt, dd, legend, .consent > span');
    const widows = [];
    const heads = [];
    const numBreaks = [];
    const wordBreaks = [];
    const around = (text, i) => `「${text.slice(Math.max(0, i - 6), i).trim()}/${text.slice(i, i + 6).trim()}」`;
    for (const el of blocks) {
      if (!visible(el) || el.closest('[aria-hidden="true"], .visually-hidden')) continue;
      if (el.querySelector('h1, h2, h3, p, li')) continue; // 入れ物は数えない
      const tolerance = parseFloat(getComputedStyle(el).fontSize) * 0.5;
      const chars = [];
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        for (let i = 0; i < node.length; i++) {
          const ch = node.data[i];
          let top = null;
          if (!/\s/.test(ch)) {
            const r = document.createRange();
            r.setStart(node, i);
            r.setEnd(node, i + 1);
            const rc = r.getClientRects()[0];
            if (rc) top = rc.top;
          }
          chars.push({ ch, top });
        }
      }
      let line = -1;
      let lineTop = null;
      const breaks = [];
      chars.forEach((c, i) => {
        if (c.top === null) { c.line = line; return; }
        if (lineTop === null || Math.abs(c.top - lineTop) > tolerance) {
          line++;
          lineTop = c.top;
          if (line > 0) breaks.push(i);
        }
        c.line = line;
      });
      if (line < 1) continue;
      const text = chars.map((c) => c.ch).join('');
      const lines = [];
      chars.forEach((c) => { if (c.top !== null) (lines[c.line] = lines[c.line] || []).push(c.ch); });
      const ls = lines.map((l) => l.join(''));
      const last = ls[ls.length - 1];
      if (last.replace(new RegExp(punct.source, 'g'), '').length <= 2) widows.push(`「…${ls[ls.length - 2].slice(-6)}/${last}」`);
      for (const l of ls.slice(1)) if (punct.test(l[0])) heads.push(`「${l.slice(0, 8)}」`);
      for (const i of breaks) {
        let j = i - 1;
        while (j >= 0 && /\s/.test(text[j])) j--;
        if (j >= 0 && numChar.test(text[j]) && numChar.test(text[i])) numBreaks.push(around(text, i));
      }
      if (seg) {
        for (const w of seg.segment(text)) {
          if (!w.isWordLike || w.segment.length < 2 || w.segment.length > 8) continue;
          // ひらがなを含む切れ目は判定が当てにならないので、カタカナ語、漢字の熟語、英数字の語だけを見る
          if (!/^[\p{Script=Katakana}ー]+$|^\p{Script=Han}+$|^[A-Za-z0-9]+$/u.test(w.segment)) continue;
          for (const i of breaks) if (i > w.index && i < w.index + w.segment.length) wordBreaks.push(around(text, i));
        }
      }
    }
    closed.forEach((d) => d.removeAttribute('open'));
    if (widows.length) add(WARN, '改行', `最後の行が1〜2文字: ${widows.slice(0, 10).join(' ')}`);
    if (heads.length) add(NG, '改行', `行頭に句読点: ${heads.slice(0, 6).join(' ')}`);
    if (numBreaks.length) add(NG, '改行', `数字や時刻の途中で改行: ${[...new Set(numBreaks)].slice(0, 6).join(' ')}`);
    if (wordBreaks.length) add(WARN, '改行', `語の途中で改行: ${[...new Set(wordBreaks)].slice(0, 8).join(' ')}`);

    // 無地の上の文字のコントラスト(写真の上は別に測る)
    const parse = (c) => (c.match(/[\d.]+/g) || []).map(Number);
    const lum = ([r, g, b]) => {
      const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const ratio = (a, b) => { const x = lum(a); const y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const bgOf = (el) => {
      for (let e = el; e; e = e.parentElement) {
        const cs = getComputedStyle(e);
        if (cs.backgroundImage !== 'none') return null;
        const c = parse(cs.backgroundColor);
        if (c.length >= 3 && (c.length < 4 || c[3] > 0.95)) return c;
      }
      return [255, 255, 255];
    };
    const low = [];
    for (const el of document.querySelectorAll('body *')) {
      if (!visible(el) || el.closest('.hero, .topbar, [aria-hidden="true"], .visually-hidden')) continue;
      if (![...el.childNodes].some((n) => n.nodeType === 3 && n.data.trim())) continue;
      const cs = getComputedStyle(el);
      const bg = bgOf(el);
      if (!bg) continue;
      const size = parseFloat(cs.fontSize);
      const large = size >= 24 || (size >= 18.66 && +cs.fontWeight >= 700);
      const r = ratio(parse(cs.color), bg);
      if (r < (large ? 3 : 4.5)) low.push(`「${el.textContent.trim().slice(0, 12)}」${r.toFixed(2)}:1`);
    }
    if (low.length) add(NG, 'コントラスト', `基準に届かない文字: ${[...new Set(low)].slice(0, 8).join('、')}`);
    return out;
  }, { vp });
}

// 写真の上の文字のコントラスト。文字だけを消した画面を撮り、文字があった場所の明るさを測る
async function photoTextContrast(page, vp) {
  await page.evaluate(() => window.scrollTo(0, 0));
  const targets = ['.hero h1', '.hero .sub', '.hero-cap', '.topbar .mark', '.topbar .nav a'];
  const items = await page.evaluate((targets) => {
    const out = [];
    for (const sel of targets) {
      for (const el of document.querySelectorAll(sel)) {
        const cs = getComputedStyle(el);
        const rr = el.getBoundingClientRect();
        if (cs.display === 'none' || cs.visibility === 'hidden' || rr.width === 0) continue;
        const range = document.createRange();
        range.selectNodeContents(el);
        const rects = [...range.getClientRects()].filter((r) => r.width > 2 && r.height > 2)
          .map((r) => ({ x: r.left, y: r.top, w: r.width, h: r.height }));
        out.push({ sel, text: el.textContent.trim().slice(0, 16), color: cs.color, size: parseFloat(cs.fontSize), weight: +cs.fontWeight, rects });
      }
    }
    return out;
  }, targets);
  if (!items.length) return [];
  const style = await page.addStyleTag({ content: '.hero *, .topbar * { color: transparent !important; text-shadow: none !important; } .hero .btn { visibility: hidden !important; }' });
  await page.waitForTimeout(150);
  const shot = await page.screenshot();
  await style.evaluate((n) => n.remove());
  return page.evaluate(async ({ b64, items, dpr }) => {
    const img = new Image();
    img.src = 'data:image/png;base64,' + b64;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    const lum = (r, g, b) => {
      const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    return items.map((it) => {
      const m = (it.color.match(/[\d.]+/g) || []).map(Number);
      const lt = lum(m[0], m[1], m[2]);
      const ratios = [];
      for (const r of it.rects) {
        const x0 = Math.max(0, Math.floor(r.x * dpr)); const y0 = Math.max(0, Math.floor(r.y * dpr));
        const w = Math.min(c.width - x0, Math.ceil(r.w * dpr)); const h = Math.min(c.height - y0, Math.ceil(r.h * dpr));
        if (w <= 0 || h <= 0) continue;
        const d = ctx.getImageData(x0, y0, w, h).data;
        for (let i = 0; i < d.length; i += 12) {
          const lb = lum(d[i], d[i + 1], d[i + 2]);
          ratios.push((Math.max(lt, lb) + 0.05) / (Math.min(lt, lb) + 0.05));
        }
      }
      ratios.sort((a, b) => a - b);
      const q = (p) => (ratios.length ? +ratios[Math.floor((ratios.length - 1) * p)].toFixed(2) : null);
      const large = it.size >= 24 || (it.size >= 18.66 && it.weight >= 700);
      return { sel: it.sel, text: it.text, need: large ? 3 : 4.5, min: q(0), p10: q(0.1), median: q(0.5) };
    });
  }, { b64: shot.toString('base64'), items, dpr: vp.dpr });
}

(async () => {
  const { pos } = parseArgs(process.argv.slice(2));
  const [url, outDir = 'review'] = pos;
  if (!url) {
    console.error('使い方: node audit.js <URL> <書き出し先>');
    process.exit(1);
  }
  ensureDir(outDir);
  const browser = await launch();
  const findings = [];
  const contrast = [];

  for (const vp of VIEWPORTS) {
    const { context, page, log } = await openPage(browser, url, vp);
    if (vp.name === 'desktop') {
      findings.push(...(await pageChecks(page)));
      const missing = await missingFiles(page, url);
      if (missing.length) findings.push({ level: NG, check: '画像', detail: `ファイルがありません: ${missing.join('、')}` });
    }
    findings.push(...(await viewportChecks(page, vp)));
    for (const c of await photoTextContrast(page, vp)) {
      contrast.push({ viewport: vp.name, ...c });
      if (c.p10 !== null && c.p10 < c.need) {
        findings.push({ level: NG, check: '写真の上の文字', viewport: vp.name,
          detail: `${c.sel}「${c.text}」: 明るいところで ${c.p10}:1(基準 ${c.need}:1、いちばん悪いところ ${c.min}:1)` });
      } else if (c.min !== null && c.min < c.need) {
        findings.push({ level: WARN, check: '写真の上の文字', viewport: vp.name,
          detail: `${c.sel}「${c.text}」: 一部が ${c.min}:1(基準 ${c.need}:1。9割は ${c.p10}:1 以上)` });
      }
    }
    for (const e of log.errors) findings.push({ level: NG, check: 'エラー', viewport: vp.name, detail: e });
    for (const f of [...new Set(log.failed)]) findings.push({ level: NG, check: '読み込み失敗', viewport: vp.name, detail: f });
    await context.close();
  }
  await browser.close();

  // 同じ指摘が画面の大きさごとに重なるので、まとめる
  const merged = new Map();
  for (const f of findings) {
    const key = `${f.level}|${f.check}|${f.detail}`;
    if (!merged.has(key)) merged.set(key, { ...f, viewports: [] });
    if (f.viewport) merged.get(key).viewports.push(f.viewport);
  }
  const list = [...merged.values()].sort((a, b) => [NG, WARN, OK].indexOf(a.level) - [NG, WARN, OK].indexOf(b.level));

  const md = ['# 機械的な点検', '', `対象: ${url}`, ''];
  md.push(`NG ${list.filter((f) => f.level === NG).length} 件、要確認 ${list.filter((f) => f.level === WARN).length} 件`, '');
  for (const f of list) md.push(`- **${f.level}** ${f.check}${f.viewports.length ? `(${f.viewports.join('・')})` : ''}: ${f.detail}`);
  md.push('', '## 写真の上の文字のコントラスト', '', '| 画面 | 文字 | 基準 | 9割が満たす値 | 中央 | 最低 |', '| --- | --- | --- | --- | --- | --- |');
  for (const c of contrast) md.push(`| ${c.viewport} | ${c.sel}「${c.text}」 | ${c.need}:1 | ${c.p10}:1 | ${c.median}:1 | ${c.min}:1 |`);
  fs.writeFileSync(path.join(outDir, 'audit.md'), md.join('\n') + '\n');
  fs.writeFileSync(path.join(outDir, 'audit.json'), JSON.stringify({ url, findings: list, contrast }, null, 2));
  console.log(md.slice(0, 6 + list.length).join('\n'));
  console.log(`\n書き出しました: ${path.join(outDir, 'audit.md')}`);
  process.exit(list.some((f) => f.level === NG) ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
