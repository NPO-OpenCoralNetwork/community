#!/usr/bin/env python3
"""brand/<団体>/ads.md(Google 広告の案)を点検する。

使い方(リポジトリのルートで):
  python3 scripts/check_ads.py brand/opencoral/ads.md --site sites/opencoral-lp --write

  --site   組み立てたページのフォルダ。サイトリンクのリンク先のページと位置(#join など)があるかを確かめる
  --write  表の「字数」の列を数え直して書き込む。付けないときは、書いてある字数が実際と違えば NG にする

字数は Google 広告の数え方で数える(半角は1、全角は2)。確かめること:
- 見出し、説明文、サイトリンク、コールアウト、構造化スニペットの値、表示 URL のパスが上限以内か
- 広告グループごとの見出しと説明文の数と重複。本文に書いた数(「次の8つを足して14にします」)と合うか
- 感嘆符、「ここをクリック」、半角のかっこやコロン、確かめてから使う文の外の「無料」
- 確かめてから使う文の条件に「同じ」と書いていないか(行を足すと、指す条件が変わるため)
- 1語だけのキーワード(団体名の広告グループを除く)と、2つの広告グループにあるキーワード
- 除外キーワードが、入れる場所の広告グループのキーワードを止めないか
- サイトリンクのリンクテキストの重複と、別のページへのサイトリンクが2つ以上あるか
NG があれば終了コード 1 で終わる。必要なもの: Python 3.9 以上。
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

LIMITS = {"見出し": 30, "説明文": 90, "リンクテキスト": 25, "説明文1": 35, "説明文2": 35,
          "コールアウト": 25, "値": 25}
PATH_LIMIT = 15
SEPARATOR = re.compile(r"^\|\s*-{3}")


def width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WFA" else 1 for ch in s)


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(lines: list[str]) -> tuple[list[dict], dict[str, list[str]]]:
    """表と、見出し(## と ###)ごとの本文の行を集める。"""
    tables, bodies = [], {}
    h2 = h3 = ""
    fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and line.startswith("## "):
            h2, h3 = line[3:].strip(), ""
        elif not fence and line.startswith("### "):
            h3 = line[4:].strip()
        elif not fence and line.startswith("|") and i + 1 < len(lines) and SEPARATOR.match(lines[i + 1]):
            table = {"h2": h2, "h3": h3, "header": cells(line), "rows": []}
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                table["rows"].append((i, cells(lines[i])))
                i += 1
            tables.append(table)
            continue
        bodies.setdefault(f"{h2} > {h3}", []).append(line)
        i += 1
    return tables, bodies


def column(tables: list[dict], name: str, h2: str | None = None, h3=None) -> list[str]:
    """条件に合う表から、列 name の値を集める。h3 は見出しの文字列か、見出しを受け取る関数。"""
    out = []
    for t in tables:
        if h2 is not None and t["h2"] != h2:
            continue
        if h3 is not None and not (h3(t["h3"]) if callable(h3) else t["h3"] == h3):
            continue
        if name in t["header"]:
            out += [row[t["header"].index(name)] for _, row in t["rows"]]
    return out


def is_group(h3: str) -> bool:
    return bool(re.match(r"^\d+\. ", h3))


def main() -> int:
    ap = argparse.ArgumentParser(description="Google 広告の案(ads.md)を点検する")
    ap.add_argument("ads", type=Path, help="brand/<団体>/ads.md")
    ap.add_argument("--site", type=Path, help="組み立てたページのフォルダ(例: sites/opencoral-lp)")
    ap.add_argument("--write", action="store_true", help="字数の列を数え直して書き込む")
    args = ap.parse_args()

    lines = args.ads.read_text(encoding="utf-8").split("\n")
    tables, bodies = parse(lines)
    errors, notes = [], []

    # 字数の列
    for t in tables:
        header = t["header"]
        for index, row in t["rows"]:
            if len(row) != len(header):
                errors.append(f"表の列の数が見出しと合いません: {lines[index]}")
                continue
            changed = False
            for j, name in enumerate(header):
                if name != "字数":
                    continue
                text = row[j - 1]
                kind = row[header.index("種類")] if header[j - 1] == "文" else header[j - 1]
                if kind not in LIMITS:
                    errors.append(f"字数の上限が分からない列です: {header[j - 1]}({kind})")
                    continue
                w = width(text)
                if row[j] != str(w):
                    if args.write:
                        row[j] = str(w)
                        changed = True
                    else:
                        errors.append(f"書いてある字数が実際と違います: {text}({row[j]}、実際は {w})")
                if w > LIMITS[kind]:
                    errors.append(f"字数が上限を超えています: {text}({w} > {LIMITS[kind]})")
            if changed:
                lines[index] = "| " + " | ".join(row) + " |"
    if args.write:
        args.ads.write_text("\n".join(lines), encoding="utf-8")

    # 広告の文
    shared_h = column(tables, "見出し", "広告の文", lambda h: h.startswith("共通の見出し"))
    shared_d = column(tables, "説明文", "広告の文", lambda h: h.startswith("共通の説明文"))
    ad_text = shared_h + shared_d
    groups = [t["h3"] for t in tables if t["h2"] == "広告の文" and is_group(t["h3"])]
    for g in dict.fromkeys(groups):
        own_h = column(tables, "見出し", "広告の文", g)
        own_d = column(tables, "説明文", "広告の文", g)
        hs, ds = shared_h + own_h, shared_d + own_d
        ad_text += own_h + own_d
        notes.append(f"{g}: 見出し {len(shared_h)}+{len(own_h)}={len(hs)}、説明文 {len(shared_d)}+{len(own_d)}={len(ds)}")
        if not 3 <= len(hs) <= 15:
            errors.append(f"{g}: 見出しの数が3〜15ではありません({len(hs)})")
        if not 2 <= len(ds) <= 4:
            errors.append(f"{g}: 説明文の数が2〜4ではありません({len(ds)})")
        for kind, items in (("見出し", hs), ("説明文", ds)):
            dup = sorted({x for x in items if items.count(x) > 1})
            if dup:
                errors.append(f"{g}: {kind}が重複しています: {'、'.join(dup)}")
        for m in re.finditer(r"共通の見出し(\d+)つに、次の(\d+)つを足して(\d+)にします",
                             "\n".join(bodies.get(f"広告の文 > {g}", []))):
            stated = tuple(int(x) for x in m.groups())
            if stated != (len(shared_h), len(own_h), len(hs)):
                errors.append(f"{g}: 本文の数({stated[0]}+{stated[1]}={stated[2]})が表と合いません")

    for condition in column(tables, "使えるようになる条件", "広告の文", "確かめてから使う文"):
        if re.fullmatch(r"(上と)?同じ|同上", condition):
            errors.append(f"確かめてから使う文の条件に「{condition}」と書いています。条件を行ごとに書きます")

    sitelinks = [{name: row[t["header"].index(name)] for name in ("リンクテキスト", "リンク先", "説明文1", "説明文2")}
                 for t in tables if "リンクテキスト" in t["header"] for _, row in t["rows"]]
    callouts = column(tables, "コールアウト", h3="コールアウト")
    snippets = column(tables, "値", h3="構造化スニペット")
    ad_text += [s[k] for s in sitelinks for k in ("リンクテキスト", "説明文1", "説明文2")] + callouts + snippets

    for text in ad_text:
        if re.search(r"[!！]", text):
            errors.append(f"感嘆符があります: {text}")
        if "無料" in text:
            errors.append(f"確かめてから使う文の外に「無料」があります: {text}")
        if "ここをクリック" in text:
            errors.append(f"どの広告にも使える行動のフレーズがあります: {text}")
        if re.search(r"[():]", text):
            errors.append(f"半角のかっこやコロンがあります: {text}")

    # サイトリンク、構造化スニペット、表示 URL のパス
    link_texts = [s["リンクテキスト"] for s in sitelinks]
    for dup in sorted({x for x in link_texts if link_texts.count(x) > 1}):
        errors.append(f"サイトリンクのリンクテキストが重複しています: {dup}")
    other_pages = [s for s in sitelinks if "#" not in s["リンク先"]]
    if len(other_pages) < 2:
        errors.append(f"別のページへのサイトリンクが2つ未満です({len(other_pages)})")
    if args.site:
        for s in sitelinks:
            target = s["リンク先"].strip("`").replace("[公開するURL]", "")
            page, _, anchor = target.partition("#")
            path = args.site / (page or "index.html")
            if not path.exists():
                errors.append(f"サイトリンクのリンク先のページがありません: {target}")
            elif anchor and f'id="{anchor}"' not in path.read_text(encoding="utf-8"):
                errors.append(f"サイトリンクのリンク先の位置がありません: {target}")
    notes.append(f"サイトリンク {len(sitelinks)}(別のページ {len(other_pages)})、コールアウト {len(callouts)}、"
                 f"構造化スニペットの値 {len(snippets)}")
    if snippets and not 3 <= len(snippets) <= 10:
        errors.append(f"構造化スニペットの値の数が3〜10ではありません({len(snippets)})")
    for value in column(tables, "表示 URL のパス"):
        for part in (p.strip() for p in value.split("/")):
            if width(part) > PATH_LIMIT:
                errors.append(f"表示 URL のパスが{PATH_LIMIT}を超えています: {part}({width(part)})")

    # キーワード
    keywords = {}
    for key, body in bodies.items():
        h2, _, h3 = key.partition(" > ")
        if h2 == "キーワード" and is_group(h3):
            keywords[h3] = [k.strip('"[]') for k in re.findall(r"`([\"\[][^`]+[\"\]])`", "\n".join(body))]
    owner = {}
    for g, kws in keywords.items():
        notes.append(f"{g}: キーワード {len(kws)}")
        for kw in kws:
            if kw in owner and owner[kw] != g:
                errors.append(f"キーワードが2つの広告グループにあります: {kw}({owner[kw]}、{g})")
            owner[kw] = g
            if "団体名" not in g and len(kw.split()) < 2:
                errors.append(f"1語だけのキーワードです: {kw}({g})")
    for t in tables:
        if t["h2"] != "キーワード" or "除外キーワード" not in t["header"]:
            continue
        for _, row in t["rows"]:
            scope = row[t["header"].index("入れる場所")] if "入れる場所" in t["header"] else "キャンペーン全体"
            m = re.search(r"広告グループ(\d+)〜(\d+)", scope)
            targets = [g for g in keywords if not m or int(m.group(1)) <= int(g.split(".")[0]) <= int(m.group(2))]
            for word in (re.sub(r"\(.*?\)", "", w).strip() for w in row[t["header"].index("除外キーワード")].split("、")):
                for g in targets:
                    for kw in keywords[g]:
                        if word and word.lower() in kw.lower():
                            errors.append(f"除外キーワード「{word}」が、{g} のキーワード {kw} を止めます")

    for n in notes:
        print(n)
    for e in errors:
        print("NG", e)
    print("NG はありません" if not errors else f"NG {len(errors)}件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
