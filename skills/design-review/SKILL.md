---
name: design-review
description: Reviews a built web page like a strict senior designer and QA engineer, especially the photo-led Japanese landing page made by lp-build. Takes screenshots at phone, tablet and desktop widths; measures text contrast over photos, horizontal overflow, Japanese line breaks, tap targets, image loading and sign-up form behavior; then checks visual quality, accessibility, Japanese typography and ad landing page conversion, and verifies each finding before reporting or fixing it. Use when asked to review, check, QA or critique a page or design (レビュー, 点検, 確認, ダサい, 見た目を直して), or after building a page with lp-build.
compatibility: Node 18+ with Playwright and Chromium (npm install, then npx playwright install chromium). Python 3 for a local web server.
metadata:
  author: npo-opencoralnetwork
  version: "0.1"
---

# ページを点検する

組み立てたページを、厳しいデザイナーと品質担当の目で点検します。先にスクリプトで数字をそろえ、スクリーンショットを自分の目で見てから、観点ごとに確かめます。指摘は1件ずつ確かめてから報告し、直します。

このスキルの中のファイルは、この `SKILL.md` があるフォルダからの相対パスで書いています(Claude Code では `${CLAUDE_SKILL_DIR}`、このリポジトリでは `skills/design-review/`)。

## 手順

1. **ページを配信する。** スクリプトはブラウザで実際に開いて測るので、ローカルのサーバーを立てる。

   ```sh
   python3 -m http.server 8000 --directory sites/<団体>-lp
   ```

2. **スクリプトを実行する。** 書き出し先は `review/<日付>/` などにする。

   ```sh
   node skills/design-review/scripts/shoot.js http://localhost:8000/ review/<日付>/shots
   node skills/design-review/scripts/audit.js http://localhost:8000/ review/<日付>
   node skills/design-review/scripts/form_test.js http://localhost:8000/ review/<日付>
   ```

   | スクリプト | 分かること |
   | --- | --- |
   | `shoot.js` | 5つの画面の大きさのスクリーンショット、ページの長さ(画面数)、横のはみ出し、最初の画面のボタンが見えるか、転送量、エラー |
   | `audit.js` | 写真の上と無地の上の文字のコントラスト、改行(1〜2文字だけの行、行頭の句読点)、押せるところの大きさ、画像の読み込み、仮の値、行き先のないリンク、フォームのラベルと欄の名前、見出しの順番、和文の中の半角のかっこ |
   | `form_test.js` | 参加登録フォームの入力チェック、送信、失敗したとき、ボット対策、スマホ下部のボタンの出し入れ |

3. **スクリーンショットを見る。** 少なくとも `desktop_first.png`、`phone_first.png`、`desktop_full.png`、`phone_full.png` を開いて見る。数字だけで判断しない。
4. **観点ごとに確かめる。** [references/lenses.md](references/lenses.md) の5つの観点(見た目、使いやすさ、日本語、広告の着地ページ、コード)を順に見て、指摘を [references/verify.md](references/verify.md) の形で書き出す。
   - Claude Code では、観点ごとにサブエージェントへ並行して任せてもよい。ほかの環境では順に見る。
5. **指摘を確かめる。** 1件ずつ、もう一度見る・測る、反証を探す、直し方が悪さをしないかを考える。確かめられなかった指摘は捨てる。
6. **報告する、または直す。**
   - 点検だけを頼まれたら、確かめた指摘を重さの順に報告する。
   - 直すことも頼まれたら、lp-build の `content.yaml`、`theme.css`、テンプレートのどれかを直して組み立て直し、手順2からやり直して、直ったことと悪くなったところがないことを確かめる。

## 判断の基準

- 文字のコントラストは 4.5:1 以上(24px 以上の大きな文字は 3:1 以上)。
- 押せるところの高さは 44px 以上。
- スマホのページの長さは7〜9画面。
- 横のはみ出し、コンソールのエラー、読み込みの失敗は0。
- 仮の値は、決められた場所(次の集まりの詳細、よくある質問)にだけ。

## してはいけないこと

- スクリーンショットを見ずに、見た目について判断する
- 確かめていない指摘を、事実のように報告する
- 好みだけで直す(数値や見たことで説明できるものだけを直す)
- 組み立てた HTML を手で直す
