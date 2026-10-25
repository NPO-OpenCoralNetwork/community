/* D3「夕方の写真」 — 参加登録ページの動き
 * 1. 参加登録フォーム: 入力チェック、送信、送信後の案内
 * 2. スマホ下部の参加登録ボタン: 最初の画面とフォームが見えていないときだけ出す
 */
(() => {
  'use strict';

  const MESSAGES = {
    nameMissing: 'お名前を入力してください。ニックネームでもかまいません。',
    nameTooLong: 'お名前は50文字以内で入力してください。',
    mailMissing: 'メールアドレスを入力してください。',
    mailInvalid: 'メールアドレスの形を確かめてください（例：name@example.com）。',
    summary: (n) => `入力内容を確かめてください。直すところが${n}つあります。`,
    sending: '送信しています…',
    failed: '送信できませんでした。時間をおいて、もう一度お試しください。',
  };

  // 計測: Google タグがあれば sign_up を送る。コンバージョンはお礼ページで数える
  const track = () => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ event: 'sign_up', method: 'signup_form' });
    if (typeof window.gtag === 'function') {
      window.gtag('event', 'sign_up', { method: 'signup_form' });
    }
  };

  /* 1. 参加登録フォーム */
  const form = document.querySelector('[data-signup]');
  if (form) {
    // JavaScript が動くときは独自の入力チェックを使う(動かないときはブラウザの標準チェック)
    form.noValidate = true;
    const nameInput = form.querySelector('#f-name');
    const mailInput = form.querySelector('#f-mail');
    const honeypot = form.querySelector('input[name="website"]');
    const submit = form.querySelector('button[type="submit"]');
    const status = form.querySelector('.form-status');
    const done = document.getElementById('join-done');
    const submitLabel = submit.innerHTML;
    let touched = false;

    const errorEl = (input) => document.getElementById(input.getAttribute('aria-describedby'));

    const setError = (input, message) => {
      const el = errorEl(input);
      if (message) {
        input.setAttribute('aria-invalid', 'true');
        el.textContent = message;
      } else {
        input.removeAttribute('aria-invalid');
        el.textContent = '';
      }
    };

    const checkName = () => {
      const value = nameInput.value.trim();
      if (!value) return MESSAGES.nameMissing;
      if (value.length > 50) return MESSAGES.nameTooLong;
      return '';
    };

    const checkMail = () => {
      const value = mailInput.value.trim();
      if (!value) return MESSAGES.mailMissing;
      // ブラウザの判定に加えて、ドメインに「.」があるかも見る
      if (mailInput.validity.typeMismatch || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return MESSAGES.mailInvalid;
      return '';
    };

    // 全角の英数字・記号や全角スペースを半角にそろえる(IME で入力したアドレス向け)
    const normalizeMail = () => {
      const value = mailInput.value.normalize('NFKC').trim();
      if (value !== mailInput.value) mailInput.value = value;
    };
    mailInput.addEventListener('change', normalizeMail);

    const fields = [
      { input: nameInput, check: checkName },
      { input: mailInput, check: checkMail },
    ];

    // 一度送信を試したあとは、直したそばからエラーを消す
    fields.forEach(({ input, check }) => {
      input.addEventListener('input', () => {
        if (touched || input.getAttribute('aria-invalid') === 'true') setError(input, check());
        // 送信時に出したまとめの文も、直した数に合わせて更新する
        if (status.dataset.kind === 'summary') {
          const left = fields.filter((f) => f.check()).length;
          status.textContent = left ? MESSAGES.summary(left) : '';
          status.classList.toggle('is-error', left > 0);
        }
      });
      input.addEventListener('blur', () => {
        if (input.value.trim()) setError(input, check());
      });
    });

    const setBusy = (busy) => {
      submit.disabled = busy;
      submit.innerHTML = busy ? MESSAGES.sending : submitLabel;
      form.setAttribute('aria-busy', busy ? 'true' : 'false');
    };

    // 戻るボタンでページがそのまま復元されたときに、送信中の表示を戻す
    window.addEventListener('pageshow', (event) => {
      if (event.persisted) setBusy(false);
    });

    const finish = () => {
      track();
      const redirect = form.dataset.redirect;
      if (redirect) {
        window.location.assign(redirect);
        return;
      }
      form.hidden = true;
      done.hidden = false;
      done.focus();
    };

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      touched = true;
      normalizeMail();
      status.textContent = '';
      delete status.dataset.kind;
      status.classList.remove('is-error');

      const invalid = fields
        .map(({ input, check }) => {
          const message = check();
          setError(input, message);
          return message ? input : null;
        })
        .filter(Boolean);

      if (invalid.length) {
        status.dataset.kind = 'summary';
        status.textContent = MESSAGES.summary(invalid.length);
        status.classList.add('is-error');
        invalid[0].focus();
        return;
      }

      // 見えない欄が埋まっていたらボット。送らずに終える
      if (honeypot && honeypot.value) {
        form.hidden = true;
        done.hidden = false;
        return;
      }

      const endpoint = (form.dataset.endpoint || '').trim();
      if (!endpoint) {
        // 送信先が未設定のときは確認用の動きだけをする
        console.info('[signup] data-endpoint が空なので送信していません。', Object.fromEntries(new FormData(form)));
        finish();
        return;
      }

      setBusy(true);
      try {
        const body = new FormData(form);
        body.delete('website');
        const response = await fetch(endpoint, {
          method: 'POST',
          body,
          headers: { Accept: 'application/json' },
          // 応答がないまま待ち続けないよう、15秒で打ち切る
          signal: typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(15000) : undefined,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        finish();
      } catch (error) {
        console.error('[signup]', error);
        setBusy(false);
        status.textContent = MESSAGES.failed;
        status.classList.add('is-error');
        submit.focus();
      }
    });
  }

  /* 2. スマホ下部の参加登録ボタン */
  const bar = document.querySelector('[data-sticky-cta]');
  const heroCta = document.querySelector('[data-hero-cta]');
  const join = document.getElementById('join');
  if (bar && heroCta && join && 'IntersectionObserver' in window) {
    const link = bar.querySelector('a');
    const visible = new Map([[heroCta, true], [join, false]]);

    const update = () => {
      const on = !visible.get(heroCta) && !visible.get(join);
      bar.classList.toggle('is-on', on);
      bar.setAttribute('aria-hidden', on ? 'false' : 'true');
      link.tabIndex = on ? 0 : -1;
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => visible.set(entry.target, entry.isIntersecting));
      update();
    });
    observer.observe(heroCta);
    observer.observe(join);
  }
})();
