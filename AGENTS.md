# エージェント向けの案内

このリポジトリは、特定非営利活動法人 Open Coral Network のコミュニティの参加登録ページと、それを作るためのスキルを置く場所です。Claude Code と Codex の両方で使えるように、スキルは [Agent Skills](https://agentskills.io) の形式で書き、ほかのリポジトリでも使えるようにプラグイン `lp-designer` にまとめています。

## スキル

| スキル | 使うとき |
| --- | --- |
| `lp-build`(`plugins/lp-designer/skills/lp-build/`) | 参加登録ページを作る、直す、写真や日時を差し替える、新しい団体のページを作る |
| `design-review`(`plugins/lp-designer/skills/design-review/`) | ページやデザインを点検する、レビューする、直す前に問題を確かめる |

本体はプラグインのフォルダ `plugins/lp-designer/skills/` にあります。このリポジトリでは、Claude Code は `.claude/skills/`、Codex は `.agents/skills/` のリンクから読み込むので、プラグインを入れなくても使えます。スキルを直すときは `plugins/lp-designer/skills/` の中を直します。

## プラグイン

- ほかのリポジトリでは、このリポジトリをマーケットプレイス(名前は `opencoral`)として追加し、`lp-designer` を入れて使う。入れ方は [plugins/lp-designer/README.md](plugins/lp-designer/README.md)。
- **Claude Code 用の `plugins/lp-designer/.claude-plugin/plugin.json` には `version` を書かない。** 書かなければ、`main` に入ったコミットがそのまま新しい版として届く。書くと、その値を変えるまで届かなくなる。Codex など向けの `plugins/lp-designer/plugin.json` の `version` は、中身を大きく変えたときに上げる。
- 変えたら `claude plugin validate plugins/lp-designer` と `claude plugin validate .` で確かめる。
- このリポジトリでは、同じスキルが2つ並ばないよう、プラグインを無効にしてある(`.claude/settings.json`)。それでもプラグイン版(`lp-designer:lp-build` など)が読み込まれているときは、使わない。使うのはリンクから読み込まれる `lp-build`、`design-review`(手元の変更が入っているほう)。

## 場所

- `brand/<団体>/`:団体ごとの事実(`facts.md`)、文面(`content.yaml`)、団体の情報のページ(`pages.yaml`)、デザインの決まり(`design.md`)、写真(`photos/`)、Google 広告の案(`ads.md`)。ページの文面を変えたら、`ads.md` の広告の文とキーワードも見直す
- `sites/<団体>-lp/`:組み立てたページ。`content.yaml` から作るので、手で直さない
- `docs/reports/`:構想の整理レポートとデザインリサーチ

## 守ること

- **事実は `brand/<団体>/facts.md` にあるものだけを書く。** 人名、数字、地名、日付、実績を新しく書くときは、出典を確かめて `facts.md` に足してから使う。確かめられないことは書かない。
- **人が決めることは聞く。** デザインの方向、決まっていない事実(日時、会場、参加費、名前)、使う写真と写る人の同意、公開。聞けないときは書かないか、角括弧の仮の値にして報告する。依頼の中の食い違い(日付と曜日が合わないなど)も、推測で直さずに聞く。
- **仮置きの写真のまま広告に使わない。** AI で生成した人物の写真や、他人の写真を団体の人として見せることもしない。
- **組み立てた HTML は手で直さない。** `content.yaml`、`brand/<団体>/theme.css`、テンプレートを直して組み立て直す。
- **見た目は必ずスクリーンショットで確かめる。** スマホ幅とパソコン幅の両方。
- **頼まれていないのに、公開、push、広告の設定をしない。**
- 文章は日本語で、短い文で書く。ページに載せる文章(`content.yaml`)では、和文の中のかっことコロンを全角にする。

## よく使うコマンド

```sh
# 準備(初回だけ)
pip install -r requirements.txt
npm install && npx playwright install chromium

# ページを組み立てる
python3 plugins/lp-designer/skills/lp-build/scripts/build_site.py --brand brand/opencoral --out sites/opencoral-lp

# 点検する(別の端末でサーバーを立ててから)
python3 -m http.server 8000 --directory sites/opencoral-lp
node plugins/lp-designer/skills/design-review/scripts/review.js http://localhost:8000/ review
```
