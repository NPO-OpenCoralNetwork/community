# エージェント向けの案内

このリポジトリは、特定非営利活動法人 Open Coral Network のコミュニティの参加登録ページと、それを作るためのスキルを置く場所です。Claude Code と Codex の両方で使えるように、スキルは [Agent Skills](https://agentskills.io) の形式で書いています。

## スキル

| スキル | 使うとき |
| --- | --- |
| `lp-build`(`skills/lp-build/`) | 参加登録ページを作る、直す、写真や日時を差し替える、新しい団体のページを作る |
| `design-review`(`skills/design-review/`) | ページやデザインを点検する、レビューする、直す前に問題を確かめる |

本体は `skills/` にあり、Claude Code は `.claude/skills/`、Codex は `.agents/skills/` のリンクから読み込みます。スキルを直すときは `skills/` の中を直します。

## 場所

- `brand/<団体>/`:団体ごとの事実(`facts.md`)、文面(`content.yaml`)、デザインの決まり(`design.md`)、写真(`photos/`)
- `sites/<団体>-lp/`:組み立てたページ。`content.yaml` から作るので、手で直さない
- `docs/reports/`:構想の整理レポートとデザインリサーチ

## 守ること

- **事実は `brand/<団体>/facts.md` にあるものだけを書く。** 人名、数字、地名、日付、実績を新しく書くときは、出典を確かめて `facts.md` に足してから使う。確かめられないことは書かない。
- **人が決めることは聞く。** デザインの方向、決まっていない事実(日時、会場、参加費、名前)、使う写真と写る人の同意、公開。聞けないときは書かないか、角括弧の仮の値にして報告する。
- **仮置きの写真のまま広告に使わない。** AI で生成した人物の写真や、他人の写真を団体の人として見せることもしない。
- **組み立てた HTML は手で直さない。** `content.yaml`、`brand/<団体>/theme.css`、テンプレートを直して組み立て直す。
- **見た目は必ずスクリーンショットで確かめる。** スマホ幅とパソコン幅の両方。
- **頼まれていないのに、公開、push、広告の設定をしない。**
- 文章は日本語で、短い文で書く。和文の中のかっことコロンは全角。

## よく使うコマンド

```sh
# 準備(初回だけ)
pip install -r requirements.txt
npm install && npx playwright install chromium

# ページを組み立てる
python3 skills/lp-build/scripts/build_site.py --brand brand/opencoral --out sites/opencoral-lp

# 点検する(別の端末でサーバーを立ててから)
python3 -m http.server 8000 --directory sites/opencoral-lp
node skills/design-review/scripts/shoot.js http://localhost:8000/ review/shots
node skills/design-review/scripts/audit.js http://localhost:8000/ review
node skills/design-review/scripts/form_test.js http://localhost:8000/ review
```
