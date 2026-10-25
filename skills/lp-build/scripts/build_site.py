#!/usr/bin/env python3
"""brand/<団体>/content.yaml と写真から、参加登録ページ一式を組み立てる。

使い方(リポジトリのルートで):
  python3 skills/lp-build/scripts/build_site.py --brand brand/opencoral --out sites/opencoral-lp

  --skip-images   写真の書き出しを省く(文面だけ直したとき。書き出し済みの写真が要る)
  --no-avif       AVIF を書き出さない(Pillow が AVIF に対応していないとき)

組み立てたあと、残っている仮の値([日時] など)と、行き先のないリンク(href="#")を一覧にして表示する。
必要なもの: Python 3.9 以上、Pillow、PyYAML、Jinja2(色調をかけるときは numpy)。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

sys.path.insert(0, str(Path(__file__).resolve().parent))
import images  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "site-template"

# 見出しの1行の上限(全角換算)。スマホ幅 320px でも2行に収まる長さ
HEADLINE_LINE_MAX = 10.0
# 写真の枠の大きさ(style.css と合わせる)。sizes 属性の計算に使う
HERO_MAX_H_DESKTOP = 1000
HERO_MAX_H_PHONE = 844
SIZES_HALF = "(max-width: 760px) calc(100vw - 32px), (max-width: 1023px) calc(46vw - 12px), 680px"
SIZES_WIDE = "(max-width: 760px) calc(100vw - 32px), (max-width: 1270px) 92vw, 1168px"

# 仮の値: [日時] のような角括弧と、「（仮）」「未定」などの印
PLACEHOLDER = re.compile(r"\[[^\[\]<>\n]{1,60}\]|[^\s、。\[\]<>]{0,12}(?:（仮）|\(仮\)|未定|TBD)")
# 日付と曜日: 「2026年11月14日（土）」「11月14日(土)」
DATE_WITH_WEEKDAY = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*[（(]([月火水木金土日])[)）]")
WEEKDAYS = "月火水木金土日"


class BuildError(Exception):
    pass


def text_width(s: str) -> float:
    """全角を1、半角を0.55として長さを数える(タグは数えない)。"""
    s = re.sub(r"<[^>]+>", "", s)
    return sum(0.55 if ord(ch) < 0x2E80 else 1.0 for ch in s)


def kern(line: str) -> str:
    """大きな見出しの行の途中にある「、」「。」を詰める(Murecho などは palt が効かないため)。"""
    return re.sub(r"([、。])(?=.)", r'<span class="pt">\1</span>', line)


def fmt_num(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def walk_strings(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, path + (i,))
    elif isinstance(node, str):
        yield path, node


def describe(path: tuple, c: dict) -> str:
    """content.yaml の場所を、人が読める説明にする。"""
    try:
        if path[:2] == ("meetup", "details"):
            return f"「{c['meetup']['heading']}」の「{c['meetup']['details'][path[2]]['label']}」"
        if path[:2] == ("faq", "items"):
            return f"よくある質問「{c['faq']['items'][path[2]]['q']}」"
        if path[0] in ("meetup", "mission", "steps", "promises", "join", "activities"):
            heading = c[path[0]].get("heading", path[0])
            return f"「{heading}」"
    except (KeyError, IndexError, TypeError):
        pass
    return ".".join(str(p) for p in path)


def validate(c: dict, brand: Path) -> list[str]:
    """組み立てられない誤りは BuildError、直したほうがよい点は警告として返す。"""
    errors, warnings = [], []
    for key in ("site", "org", "cta", "nav", "hero", "join", "thanks", "photos"):
        if key not in c:
            errors.append(f"content.yaml に {key} がありません")
    if errors:
        raise BuildError("\n".join(errors))

    required = {
        "site": ["title", "description", "og_title", "og_description"],
        "org": ["mark", "footer_lines"],
        "hero": ["headline", "sub", "caption", "photo", "photo_phone", "alt"],
        "join": ["heading", "lead", "name_label", "email_label", "done_heading", "done_text"],
        "thanks": ["title", "heading", "text", "back"],
    }
    for section, keys in required.items():
        for k in keys:
            if not (c.get(section) or {}).get(k):
                errors.append(f"{section}.{k} がありません(必ず書く項目です。書き方は content-guide.md)")
    if not c.get("cta"):
        errors.append("cta(ボタンの文言)がありません")
    if errors:
        raise BuildError("\n".join(errors))

    photos = c["photos"]
    for slot, spec in photos.items():
        f = brand / "photos" / spec.get("file", "")
        if not spec.get("file") or not f.exists():
            errors.append(f"写真 {slot} のファイルが見つかりません: {f}")
        if not spec.get("widths"):
            errors.append(f"写真 {slot} に widths がありません")

    uses = [("hero.photo", c["hero"].get("photo"), c["hero"].get("alt"), c["hero"].get("caption")),
            ("hero.photo_phone", c["hero"].get("photo_phone"), c["hero"].get("alt"), c["hero"].get("caption"))]
    if c.get("meetup"):
        m = c["meetup"]
        uses.append(("meetup", m.get("photo"), m.get("alt"), m.get("caption")))
    if c.get("activities"):
        for i, a in enumerate(c["activities"].get("items", [])):
            uses.append((f"activities.items[{i}]", a.get("photo"), a.get("alt"), a.get("caption")))
    for where, slot, alt, cap in uses:
        if slot not in photos:
            errors.append(f"{where} の写真 {slot!r} が photos にありません")
        if not alt:
            errors.append(f"{where} に alt(写っている内容の説明)がありません")
        if not cap:
            errors.append(f"{where} に caption(場所と時間帯)がありません")

    for i, line in enumerate(c["hero"].get("headline", [])):
        if text_width(line) > HEADLINE_LINE_MAX:
            warnings.append(f"見出しの{i + 1}行目が全角{text_width(line):.1f}字です。スマホで3行になります(上限 {HEADLINE_LINE_MAX:.0f} 字)")
    if not 1 <= len(c["hero"].get("headline", [])) <= 2:
        warnings.append("見出しは1〜2行にします")

    targets = {"#join"}
    if c.get("meetup"):
        targets.add("#meetup")
    if c.get("activities"):
        targets.add("#acts")
    for n in c["nav"]:
        if n["href"].startswith("#") and n["href"] not in targets:
            errors.append(f"メニュー「{n['label']}」の行き先 {n['href']} がページにありません")

    warnings.extend(check_weekdays(c))

    for path, s in walk_strings(c):
        if "{{" in s or "}}" in s:
            errors.append(f"{'.'.join(map(str, path))} にテンプレートの記号が残っています")
        if "TODO" in s:
            warnings.append(f"{'.'.join(map(str, path))} に TODO が残っています")

    if errors:
        raise BuildError("\n".join(errors))
    return warnings


def check_weekdays(c: dict, today: date | None = None) -> list[str]:
    """日付と曜日が合っているかを確かめる。年がなければ、今日から1年以内のその日付で確かめる。"""
    today = today or date.today()
    out = []
    for path, s in walk_strings(c):
        plain = re.sub(r"<[^>]+>", "", s)
        for m in DATE_WITH_WEEKDAY.finditer(plain):
            year, month, day, wd = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            try:
                if year:
                    d = date(int(year), month, day)
                else:
                    d = date(today.year, month, day)
                    if d < today:
                        d = date(today.year + 1, month, day)
            except ValueError:
                out.append(f"{describe(path, c)}: 「{m.group(0)}」は存在しない日付です")
                continue
            actual = WEEKDAYS[d.weekday()]
            if actual != wd:
                out.append(f"{describe(path, c)}: 「{m.group(0)}」の曜日が違います。{d.year}年{month}月{day}日は{actual}曜日です。依頼した人に確かめてください")
    return out


def act_layouts(n: int) -> list[str]:
    layouts = ["normal" if i % 2 == 0 else "flip" for i in range(n)]
    if n >= 3 and n % 2 == 1:
        layouts[-1] = "wide"
    return layouts


def build(brand: Path, out: Path, skip_images: bool, use_avif: bool) -> dict:
    content_path = brand / "content.yaml"
    if not content_path.exists():
        raise BuildError(f"{content_path} がありません")
    c = yaml.safe_load(content_path.read_text(encoding="utf-8"))
    warnings = validate(c, brand)

    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / "assets" / "img"
    photos = {}
    for slot, spec in c["photos"].items():
        widths = sorted(spec["widths"])
        largest = img_dir / f"{slot}-{widths[-1]}.jpg"
        if skip_images and largest.exists():
            from PIL import Image
            with Image.open(largest) as im:
                w, h = im.size
        else:
            w, h = images.export(brand / "photos" / spec["file"], img_dir, slot, widths,
                                 spec.get("quality", images.JPEG_QUALITY), use_avif)
        photos[slot] = {"widths": widths, "w": w, "h": h, "mid": widths[len(widths) // 2],
                        "focal": spec.get("focal", "")}

    og = c.get("og_image") or {"photo": c["hero"]["photo"], "y": 0.55}
    if not (skip_images and (img_dir / "og.jpg").exists()):
        images.og_image(brand / "photos" / c["photos"][og["photo"]]["file"], img_dir / "og.jpg", og.get("y", 0.55))

    hero, phone = photos[c["hero"]["photo"]], photos[c["hero"]["photo_phone"]]
    r_h, r_v = hero["w"] / hero["h"], phone["w"] / phone["h"]
    theme_css = (brand / "theme.css").exists()
    items = (c.get("activities") or {}).get("items", [])
    ctx = {
        "c": c,
        "photos": photos,
        "avif": use_avif,
        "theme_css": theme_css,
        "act_layouts": act_layouts(len(items)),
        "sizes_half": SIZES_HALF,
        "sizes_wide": SIZES_WIDE,
        "hero_sizes": f"max(100vw, min({fmt_num(r_h * 100)}vh, {round(r_h * HERO_MAX_H_DESKTOP)}px))",
        "hero_sizes_phone": f"max(100vw, min({fmt_num(r_v * 100)}vh, {round(r_v * HERO_MAX_H_PHONE)}px))",
    }

    # finalize: 書かれていない任意の項目(None)を「None」と出さず、空にする
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False,
                      keep_trailing_newline=True, undefined=StrictUndefined,
                      finalize=lambda v: "" if v is None else v)
    env.filters["kern"] = kern
    # StrictUndefined でも、任意の項目は if で確かめられるように「無い」を None で返す
    c_safe = _Lenient(c)
    ctx["c"] = c_safe

    html = env.get_template("index.html.j2").render(**ctx)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "thanks.html").write_text(env.get_template("thanks.html.j2").render(**ctx), encoding="utf-8")

    for rel in ("assets/css/style.css", "assets/js/main.js"):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE_DIR / rel, out / rel)
    if theme_css:
        shutil.copyfile(brand / "theme.css", out / "assets" / "css" / "theme.css")

    placeholders = []
    for path, s in walk_strings(c):
        for m in PLACEHOLDER.finditer(re.sub(r"<[^>]+>", "", s)):
            placeholders.append({"where": describe(path, c), "text": m.group(0)})
    hash_links = sorted(set(re.findall(r'<a href="#">([^<]+)</a>', html)))

    where = {c["hero"]["photo"]: "パソコンの最初の画面", c["hero"]["photo_phone"]: "スマホの最初の画面"}
    if c.get("meetup"):
        where.setdefault(c["meetup"]["photo"], f"「{c['meetup']['heading']}」")
    for a in items:
        where[a["photo"]] = (where.get(a["photo"], "") + "、" if a["photo"] in where else "") + f"活動「{a['heading']}」"
    photo_rows = [{"slot": f"{slot}-*", "where": where.get(slot, "(使っていない)"),
                   "widths": "・".join(map(str, p["widths"]))} for slot, p in photos.items()]

    readme = env.get_template("README.md.j2").render(
        **ctx, brand_name=brand.name, out_rel=_rel(out), out_name=out.name,
        placeholders=placeholders, hash_links=hash_links, photo_rows=photo_rows,
        credits=bool((c.get("credits") or {}).get("items")))
    (out / "README.md").write_text(readme, encoding="utf-8")

    return {"warnings": warnings, "placeholders": placeholders, "hash_links": hash_links}


class _Lenient(dict):
    """content.yaml の dict を、テンプレートから c.key で読めるようにする。無い項目は None。"""

    def __init__(self, d):
        super().__init__({k: _wrap(v) for k, v in d.items()})

    def __getattr__(self, key):
        return self.get(key)


def _wrap(v):
    if isinstance(v, dict):
        return _Lenient(v)
    if isinstance(v, list):
        return [_wrap(x) for x in v]
    return v


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brand", type=Path, required=True, help="brand/<団体> のフォルダ")
    ap.add_argument("--out", type=Path, required=True, help="書き出すフォルダ(例: sites/<団体>-lp)")
    ap.add_argument("--skip-images", action="store_true")
    ap.add_argument("--no-avif", action="store_true")
    args = ap.parse_args()

    use_avif = not args.no_avif
    if use_avif and not images.avif_supported():
        print("この Pillow は AVIF を書き出せません。pip install -U pillow で更新するか、--no-avif を付けてください。",
              file=sys.stderr)
        return 2
    try:
        result = build(args.brand, args.out, args.skip_images, use_avif)
    except BuildError as e:
        print("組み立てられませんでした:\n" + str(e), file=sys.stderr)
        return 1

    print(f"組み立てました: {args.out}")
    for w in result["warnings"]:
        print(f"  注意: {w}")
    if result["placeholders"]:
        print("  公開前に決める仮の値:")
        for p in result["placeholders"]:
            print(f"    - {p['where']}: {p['text']}")
    if result["hash_links"]:
        print("  行き先がまだないリンク: " + "、".join(result["hash_links"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
