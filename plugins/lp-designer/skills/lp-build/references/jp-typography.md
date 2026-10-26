# 日本語の組版

書体の選び方より、組み方で差がつきます。D3 は現代的な角ゴシックを見出しだけ詰めて組み、本文は大きめの文字と広めの行間で組みます。

## 書体

- 和文は Murecho、欧文と数字は Geist(どちらも Google Fonts)。CSS では `font-family: 'Geist', 'Murecho', …` の順に書き、英数字は Geist、仮名と漢字は Murecho で出す。
- 太さ:本文 400、強調と小見出し 500〜600、大見出し 600。200〜300 の細い太さは漢字が弱くなるので使わない。
- 丸ゴシック、等幅書体、手書き風の書体は使わない(子ども向けや業務システムに見える)。

## 詰め組み

- `font-feature-settings: "palt"` が効くかは書体による。Google Fonts 版で実際に測ると、効いたのは Noto Sans JP、Noto Serif JP、IBM Plex Sans JP、Klee One だけで、Murecho、Shippori Mincho B1、Zen Kaku Gothic New、Zen Maru Gothic、Dela Gothic One は全く詰まらなかった。
- palt が効かない書体の大見出しは、`letter-spacing: -0.02em` 前後で詰める。さらに行の途中の「、」「。」は全角幅のまま残って穴が空くので、`<span class="pt">、</span>` に `margin-right: -0.42em` をかけて詰める。`build_site.py` は見出しの行に自動でこれをかける。
- 本文は詰めない。`letter-spacing: 0.03em` 前後。

## 大きさと行間

| 場所 | パソコン | スマホ |
| --- | --- | --- |
| 最初の画面の見出し | 34〜64px(画面幅に合わせる)、行間 1.32 | `min(34px, 8.9vw)` |
| 目的の文 | 30px、行間 1.8 | 22px、行間 1.85 |
| 節の見出し | 22px | 18px |
| 本文 | 17px、行間 1.9 | 16px |
| 補足 | 16px、行間 1.8 | 16px |
| キャプション | 14px | 14px |

本文は 16px より小さくしません。

## 改行

- `word-break: auto-phrase` で、文節の切れ目で改行させる(Chrome と Edge だけで効く。ほかのブラウザでは普通の改行になる)。`line-break: strict` で、行頭に「、」「。」が来ないようにする。
- 見出しは行を `content.yaml` で明示的に分ける。
- 1〜2文字だけが次の行に落ちるとき、語の途中で切れるときは、`<span class="nw">…</span>` で語をまとめるか、`<wbr>` で切ってよい位置を示す。スマホ幅 320px、390px と、パソコン幅で確かめる。
- 長い英字(団体名など)は `<span class="nw">` でまとめる。

## 句読点

- 和文の中のかっこ、コロンは全角(「（無料）」「運営：」)。
- 英数字は半角。数字と単位の間はあけない(「15以上」「1つ」)。
