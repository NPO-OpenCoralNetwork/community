---
name: lp-build
description: Builds or updates a photo-led Japanese landing page (design D3 夕方の写真 - a full-bleed evening photo hero with one sign-up action) as static HTML, CSS and JS from brand/<org>/content.yaml and its photos, ready for Google Ad Grants search ads. Use when asked to make, rebuild or edit the 参加登録ページ, LP, ランディングページ or 広告の着地ページ; to change its 文面, 写真, 日時, 会場 or 参加費; to swap stand-in photos for real ones; or to set up the page for a new organization.
compatibility: Python 3.9+ with Pillow (11.2+ for AVIF), PyYAML and Jinja2; numpy for photo grading. Node 18+ with Playwright Chromium for the review step.
metadata:
  author: npo-opencoralnetwork
  version: "0.1"
---

# 参加登録ページを組み立てる

広告から来た人に無料の参加登録をしてもらう1ページのサイトを、`brand/<団体>/` の中身から組み立てます。見た目はデザインリサーチで決めた D3「夕方の写真」です。

このスキルの中のファイルは、この `SKILL.md` があるフォルダからの相対パスで書いています(Claude Code では `${CLAUDE_SKILL_DIR}`、このリポジトリでは `skills/lp-build/`)。

## 先に読むもの

- `brand/<団体>/facts.md`:書いてよい事実と出典、決まっていないこと
- `brand/<団体>/content.yaml`:いまの文面と写真の割り当て
- `brand/<団体>/design.md`:その団体で決めたデザイン(あれば)

依頼の内容に応じて、次も読みます。

| こんなとき | 読むもの |
| --- | --- |
| 文面を書く・直す | [references/content-guide.md](references/content-guide.md) |
| 写真を選ぶ・差し替える | [references/photo-rules.md](references/photo-rules.md) |
| 見出しの改行や詰めが気になる | [references/jp-typography.md](references/jp-typography.md) |
| 広告の要件、計測 | [references/ad-grants.md](references/ad-grants.md) |
| テンプレートや CSS・JS を直す | [references/implementation.md](references/implementation.md) |

## 手順

1. **依頼を確かめる。** 何を変えるか(文面、日時などの事実、写真、新しい団体)をはっきりさせる。次のことは人が決めるので、決まっていなければ聞く。聞けないときは書かないか、角括弧のまま残して報告する。
   - デザインの方向(D3 以外にしたいか)
   - 決まっていない事実(日時、会場、参加費、名前など)
   - 使う写真と、写る人の同意
   - 公開すること
2. **新しい団体なら、フォルダを用意する。** `assets/brand-template/` を `brand/<団体>/` にコピーし、`facts.md` に出典つきで事実を書いてから、`content.yaml` の TODO を書き換える。
3. **`content.yaml` を直す。** 事実は `facts.md` の表にあるものだけを使う。表にない事実が要るときは、出典を確かめて `facts.md` に行を足してから使う。
4. **写真を差し替えるときは**、`scripts/images.py grade` で色調をそろえて `brand/<団体>/photos/` に置き、`content.yaml` の `alt`、`caption`、`focal`、`credits` を写真に合わせて直す。
5. **組み立てる。**

   ```sh
   python3 skills/lp-build/scripts/build_site.py --brand brand/<団体> --out sites/<団体>-lp
   ```

   文面だけ直したときは `--skip-images` で写真の書き出しを省ける。エラーが出たら、表示に従って `content.yaml` を直す。最後に、公開前に決める仮の値と、行き先のないリンクが一覧で出る。
6. **確かめる。** design-review スキルで点検する。少なくとも次を必ず行う。
   - `python3 -m http.server` で `sites/<団体>-lp` を配信し、パソコン幅とスマホ幅のスクリーンショットを撮って、自分の目で見る
   - スクリプトの数値(画面数、はみ出し、コントラスト、エラー)を確かめる

   直すときは `content.yaml`、`brand/<団体>/theme.css`、テンプレートのどれかを直して、手順5からやり直す。組み立てた HTML を手で直さない(次に組み立てると消える)。
7. **報告する。** 何を変えたか、残っている仮の値、人が決めること、確かめた結果(スマホでの画面数、見つけて直した問題)を短く伝える。

## してはいけないこと

- 出典のない事実、人名、数字、地名、実績を書く
- 仮置きの写真のまま広告用に公開する。AI で生成した人物の写真を使う
- 他人の写真を、運営者や参加者として見せる
- 組み立てた HTML を手で直す
- 頼まれていないのに、公開、push、広告の設定をする

## 見た目を変えたいとき

- **色や書体を団体に合わせる:** `brand/<団体>/theme.css` に `:root { --ground: …; --ink: …; }` のように変数を書く。組み立てると `style.css` のあとに読み込まれる。
- **節を足す・減らす:** `content.yaml` で節(`meetup`、`activities`、`steps`、`promises`、`faq`)を消せば、その節は出ない。新しい種類の節が要るときは、`assets/site-template/index.html.j2` に足し、[references/implementation.md](references/implementation.md) の約束ごとを守る。
- **D3 とは別の方向にする:** このスキルの範囲の外。方向を人に選んでもらってから、テンプレートを別に作る。

## スクリプト

| スクリプト | 役割 |
| --- | --- |
| `scripts/build_site.py` | `content.yaml` と写真から、`index.html`、`thanks.html`、CSS、JS、画像、README を書き出す。内容の誤り(写真がない、alt がない、見出しが長すぎるなど)も調べる |
| `scripts/images.py grade` | 写真に D3 の共通の色調をかける |
| `scripts/images.py export` | 1枚を幅ごとに AVIF・WebP・JPEG で書き出す(`build_site.py` の中でも使う) |

必要なもの:`pip install pillow pyyaml jinja2 numpy`(AVIF には Pillow 11.2 以上)。
