# community

特定非営利活動法人 Open Coral Network のコミュニティの、参加登録ページとデザインの作業場です。ページは、AI エージェント(Claude Code や Codex)に頼めばいつでも作り直せるように、「スキル」と「団体の資料」に分けて置いています。

## 中身

```
community/
├─ skills/                  AI エージェントに渡す手順書と道具(Agent Skills 形式)
│  ├─ lp-build/            参加登録ページを組み立てる
│  └─ design-review/       ページを点検する
├─ brand/opencoral/        団体の事実(出典つき)、文面、デザインの決まり、写真
├─ sites/opencoral-lp/     組み立てたページ(公開するファイル一式)
├─ docs/reports/           構想の整理レポート、デザインリサーチ
├─ .claude/skills/         Claude Code 用のリンク(中身は skills/)
├─ .agents/skills/         Codex 用のリンク(中身は skills/)
└─ AGENTS.md               エージェント向けの案内(CLAUDE.md からも読む)
```

## 使い方

このリポジトリを Claude Code か Codex で開き、ふつうの言葉で頼みます。スキルは頼んだ内容から自動で選ばれます。

- 「次の集まりの日時が 11月14日(土)18時半からに決まったので、ページを直して」
- 「撮影した写真を photos に入れたので、仮置きの写真と差し替えて」
- 「ページをスマホで点検して、問題があれば直して」
- 「別の団体用に、同じデザインの参加登録ページを作りたい」

名前を指定して呼ぶこともできます。Claude Code では `/lp-build`、`/design-review`、Codex では `$lp-build`、`$design-review` です。

エージェントは、事実を `brand/opencoral/facts.md` から取り、決まっていないことは聞くか仮の値のまま残します。ページは `brand/opencoral/content.yaml` から組み立て、スクリーンショットと自動の点検で確かめてから報告します。

## 手で組み立てるとき

```sh
pip install -r requirements.txt
npm install && npx playwright install chromium

python3 skills/lp-build/scripts/build_site.py --brand brand/opencoral --out sites/opencoral-lp
```

公開前に書き換えるところと、フォームの送信先、Google 広告の計測の設定は [sites/opencoral-lp/README.md](sites/opencoral-lp/README.md) にあります。

## これから足すもの

1. 構想資料から整理レポートを作るスキルと、参考サイトを撮影・分析してデザインリサーチを作るスキル
2. 全体の流れ(整理 → リサーチ → 方向を選ぶ → 組み立て → 点検)をまとめて呼ぶ入口と、Claude Code のプラグインとしての配布
3. スキルの品質を毎回確かめる自動テスト(`claude plugin eval`)
4. Codex での動作確認
