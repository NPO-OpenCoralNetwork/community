# lp-designer

写真を主役にした参加登録ページ（デザイン D3「夕方の写真」）を、団体の事実と写真から組み立てて、点検するプラグインです。Google Ad Grants の検索広告の着地ページを想定しています。

| スキル | Claude Code での呼び方 | すること |
| --- | --- | --- |
| lp-build | `/lp-designer:lp-build` | `brand/<団体>/content.yaml` と写真から、ページ一式（HTML・CSS・JS・画像・README）を組み立てる。新しい団体のひな形も置く |
| design-review | `/lp-designer:design-review` | スクリーンショット、機械的な点検、フォームの動作テストで、ページを点検する |

名前で呼ばなくても、「参加登録ページを作って」「ページを点検して」のように頼めば動きます。

## 入れ方

### Claude Code(パソコンのターミナル、デスクトップアプリ、VS Code)

セッションの中で、次を実行します。

```
/plugin install lp-designer --marketplace NPO-OpenCoralNetwork/community
```

Claude Code 2.1.275 より前の版では、2回に分けます。

```
/plugin marketplace add NPO-OpenCoralNetwork/community
/plugin install lp-designer@opencoral
```

シェルからは `claude plugin marketplace add NPO-OpenCoralNetwork/community` と `claude plugin install lp-designer@opencoral` です。

あるリポジトリで作業する全員に使ってもらうときは、そのリポジトリの `.claude/settings.json` に次を書いてコミットします。フォルダを信頼した人の Claude Code に、マーケットプレイスが登録され、プラグインが読み込まれます。

```json
{
  "extraKnownMarketplaces": {
    "opencoral": {
      "source": { "source": "github", "repo": "NPO-OpenCoralNetwork/community" }
    }
  },
  "enabledPlugins": {
    "lp-designer@opencoral": true
  }
}
```

### Claude Code on the web(claude.ai/code)

クラウドのセッションは、パソコンで入れたプラグインも、リポジトリの `.claude/settings.json` で有効にしたプラグインも読み込みません。使う方法は2つです。

- **組織の管理者が配る:** claude.ai の管理画面(Organization settings > Claude Code > Managed settings)に、上と同じ `extraKnownMarketplaces` と `enabledPlugins` を書きます。組織の全員の、クラウドとパソコンのセッションで読み込まれます。Owner の権限が要ります。
- **リポジトリにスキルを置く:** このプラグインの `skills/lp-build` と `skills/design-review` を、ページを作るリポジトリの `.claude/skills/` にコピーしてコミットします。プラグインを更新しても、コピーは自動では新しくなりません。

### Codex

```
codex plugin marketplace add NPO-OpenCoralNetwork/community
```

追加したマーケットプレイス「Open Coral Network」から lp-designer を入れます。Codex での動作は、まだ確かめていません。

## ページを作るリポジトリに用意するもの

- Python 3.9 以上と、`pip install pillow pyyaml jinja2 numpy`(AVIF の書き出しには Pillow 11.2 以上)
- 点検に使う Node 18 以上と Playwright:`npm install -D playwright` と `npx playwright install chromium`

## 使い方

1. 新しい団体なら、「○○の参加登録ページを作りたい」と頼みます。lp-build が `brand/<団体>/` にひな形を置き、事実(`facts.md`)と文面(`content.yaml`)を一緒に埋めます。決まっていないことは聞かれます。
2. 写真を `brand/<団体>/photos/` に置きます。
3. 「ページを組み立てて点検して」と頼みます。`sites/<団体>-lp/` にページができ、点検の結果と、公開の前に決めることが報告されます。

ページを作るリポジトリは、次の形になります。

```
<リポジトリ>/
├─ brand/<団体>/      事実、文面、写真(lp-build がひな形を置く)
└─ sites/<団体>-lp/   組み立てたページ
```

## 更新

- 新しい版を入れるには、`/plugin` の「Marketplaces」で opencoral を選び、「Update marketplace」を選びます。シェルからは `claude plugin update lp-designer@opencoral` です。
- 自動で更新するには、同じ画面で「Enable auto-update」を選びます。

## プラグインを直す人へ

- 中身は、このフォルダの `skills/` にあります。直したら、`.claude-plugin/plugin.json` と `plugin.json` の `version` を同じ値に上げます。上げないと、入れている人に変更が届きません。
- `plugin.json` は Codex などが読む共通の形式(Agent Plugins)、`.claude-plugin/plugin.json` は Claude Code が読む形式です。
- 確かめるコマンド(リポジトリのルートで):`claude plugin validate plugins/lp-designer` と `claude plugin validate .`
- `NPO-OpenCoralNetwork/community` の中では、プラグインを入れなくても、`.claude/skills/` と `.agents/skills/` のリンクからスキルが読み込まれます。同じスキルが2つ並ばないよう、このリポジトリではプラグインを無効にしてあります(`.claude/settings.json`)。
