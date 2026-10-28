#!/usr/bin/env python3
"""団体の名前で外に出す文章(ページ、広告、メール)の言葉を点検する。

使い方(リポジトリのルートで):
  python3 scripts/check_wording.py brand/opencoral

lp-build の references/content-guide.md の「日本語の書き方」のうち、機械で確かめられることを見る。
- 同じものを別の言葉で呼んでいないか(イベント → 集まり、申し込み → 参加登録)
- 感嘆符、飾りの記号、絵文字がないか
見るもの(ないファイルは飛ばす):
- content.yaml と pages.yaml の文字列(コメントと HTML のタグは見ない)
- ads.md の表のうち、広告に載る列(見出し、説明文、リンクテキスト、説明文1・2、コールアウト、値、文)
- emails.md の文面(```text のかたまり)と件名
NG があれば終了コード 1 で終わる。必要なもの: Python 3.9 以上、PyYAML。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

# (使わない言葉, 使う言葉)。content-guide.md の「同じものは同じ言葉で呼ぶ」
TERMS = [("イベント", "集まり"), ("申し込み", "参加登録"), ("申込み", "参加登録"), ("申込", "参加登録")]
MARKS = re.compile(r"[!！■□◆◇●★☆※【】♪]|[\U0001F300-\U0001FAFF]")
AD_COLUMNS = {"見出し", "説明文", "リンクテキスト", "説明文1", "説明文2", "コールアウト", "値", "文"}


def yaml_texts(path: Path):
    def walk(node, where):
        if isinstance(node, dict):
            for k, v in node.items():
                yield from walk(v, f"{where}.{k}" if where else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from walk(v, f"{where}.{i}")
        elif isinstance(node, str):
            yield where, re.sub(r"<[^>]+>", "", node)
    yield from walk(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, "")


def ad_texts(path: Path):
    lines = path.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines[:-1]):
        if line.startswith("|") and re.match(r"^\|\s*-{3}", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            for j in range(i + 2, len(lines)):
                if not lines[j].startswith("|"):
                    break
                row = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                for name, value in zip(header, row):
                    if name in AD_COLUMNS:
                        yield f"{j + 1}行目の{name}", value


def mail_texts(path: Path):
    text = path.read_text(encoding="utf-8")
    for m in re.finditer(r"^件名:(.+)$", text, re.M):
        yield f"{text[:m.start()].count(chr(10)) + 1}行目の件名", m.group(1)
    for m in re.finditer(r"```text\n(.*?)```", text, re.S):
        first = text[:m.start()].count("\n") + 2
        for k, line in enumerate(m.group(1).split("\n")):
            yield f"{first + k}行目", line


def main() -> int:
    if len(sys.argv) != 2:
        print("使い方: python3 scripts/check_wording.py brand/<団体>")
        return 2
    brand = Path(sys.argv[1])
    sources = [("content.yaml", yaml_texts), ("pages.yaml", yaml_texts), ("ads.md", ad_texts), ("emails.md", mail_texts)]
    errors, checked = [], 0
    for name, reader in sources:
        path = brand / name
        if not path.exists():
            continue
        for where, text in reader(path):
            checked += 1
            for bad, good in TERMS:
                if bad in text:
                    errors.append(f"{name} の {where}: 「{bad}」ではなく「{good}」と書きます: {text}")
                    break
            for mark in sorted(set(MARKS.findall(text))):
                errors.append(f"{name} の {where}: 「{mark}」を使いません: {text}")
    print(f"点検した文: {checked}")
    for e in errors:
        print("NG", e)
    print("NG はありません" if not errors else f"NG {len(errors)}件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
