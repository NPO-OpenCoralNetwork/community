# 写真の置き場

`content.yaml` の `photos` に書いた名前で置きます。決まりは `skills/lp-build/references/photo-rules.md` にあります。

| ファイル | 枠 | 向きと大きさ |
| --- | --- | --- |
| `hero-h.jpg` | 最初の画面(パソコン) | 横長、幅 2200px 以上 |
| `hero-v.jpg` | 最初の画面(スマホ) | 縦長 9:16 前後、幅 828px 以上 |
| `present.jpg` `work.jpg` `town.jpg` `talk.jpg` | 次の集まり、活動 | 横長 3:2、幅 1600px 以上 |

置く前に `python3 skills/lp-build/scripts/images.py grade 元の写真.jpg <ここ>/<名前>.jpg` で色調をそろえます。
