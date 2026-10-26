#!/usr/bin/env python3
"""brand/<団体>/content.yaml と写真から、参加登録ページ一式を組み立てる。

使い方(ページを置くリポジトリのルートで。<lp-build> は lp-build スキルのフォルダ):
  python3 <lp-build>/scripts/build_site.py --brand brand/opencoral --out sites/opencoral-lp

  --skip-images   書き出し済みの写真を使い回す(文面だけ直したとき。足りない写真だけ書き出す)
  --no-avif       AVIF を書き出さない(Pillow が AVIF に対応していないとき)

brand/<団体>/pages.yaml があれば、団体の情報のページ(about.html など)も組み立てる。
組み立てたあと、公開の前に決めること(仮の値、送信先、公開する URL、計測、下書きのページ、facts.md の要確認の事実)と、
行き先のないリンク(href="#")を一覧にして表示する。
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
# 年のない日付が、この日数のうちに過ぎたばかりなら「過ぎた日付」として知らせる
RECENT_PAST_DAYS = 60

# content.yaml の形。dict は名前の決まった項目、[x] は x のリスト、"*" はどんな名前でもよい項目
TEXT, FLAG, NUM, INT = "文字列", "true か false", "数", "整数"
SHAPE = {
    "site": {"lang": TEXT, "title": TEXT, "description": TEXT, "og_title": TEXT, "og_description": TEXT,
             "theme_color": TEXT, "url": TEXT},
    "org": {"mark": TEXT, "mark_kind": TEXT, "footer_lines": [TEXT], "links": [{"label": TEXT, "href": TEXT}]},
    "cta": TEXT,
    "nav": [{"label": TEXT, "href": TEXT, "phone": FLAG}],
    "hero": {"headline": [TEXT], "sub": TEXT, "caption": TEXT, "photo": TEXT, "photo_phone": TEXT, "alt": TEXT},
    "mission": {"heading": TEXT, "statement": TEXT, "operator": TEXT},
    "meetup": {"heading": TEXT, "intro": TEXT, "details": [{"label": TEXT, "value": TEXT}], "notes": [TEXT],
               "photo": TEXT, "alt": TEXT, "caption": TEXT},
    "activities": {"heading": TEXT,
                   "items": [{"heading": TEXT, "body": TEXT, "photo": TEXT, "alt": TEXT, "caption": TEXT}]},
    "steps": {"heading": TEXT, "items": [{"title": TEXT, "text": TEXT}]},
    "promises": {"heading": TEXT, "items": [TEXT], "voice": {"text": TEXT, "signature": TEXT}},
    "faq": {"heading": TEXT, "items": [{"q": TEXT, "a": TEXT, "open": FLAG}]},
    "join": {"heading": TEXT, "lead": TEXT, "sub": TEXT, "endpoint": TEXT, "redirect": TEXT,
             "name_label": TEXT, "name_hint": TEXT, "email_label": TEXT, "interest_legend": TEXT,
             "interest_hint": TEXT, "interests": [TEXT], "photo_consent": TEXT, "note": TEXT,
             "done_heading": TEXT, "done_text": TEXT},
    "thanks": {"title": TEXT, "heading": TEXT, "text": TEXT, "small": TEXT, "back": TEXT},
    "measure": {"google_tag_id": TEXT, "conversion_send_to": TEXT},
    "photos": {"*": {"file": TEXT, "widths": [INT], "quality": INT, "focal": TEXT}},
    "og_image": {"photo": TEXT, "y": NUM},
    "credits": {"note": TEXT, "items": [{"use": TEXT, "author": TEXT, "works": [{"title": TEXT, "url": TEXT}],
                                         "license": TEXT, "license_url": TEXT}]},
    # pages.yaml から読む、団体の情報のページ。名前(about など)がファイル名(about.html)になる
    "pages": {"*": {"draft": FLAG, "title": TEXT, "heading": TEXT, "lead": TEXT, "footnote": TEXT,
                    "sections": [{"heading": TEXT, "paragraphs": [TEXT], "items": [TEXT],
                                  "details": [{"label": TEXT, "value": TEXT}], "notes": [TEXT]}]}},
}
# pages.yaml のページの名前に使えないもの(ほかのページと重なる)
RESERVED_PAGES = {"index", "thanks"}


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


def check_shape(node, shape, path=()) -> list[str]:
    """値が、テンプレートの読める形(文字列、リスト、項目の表)になっているかを確かめる。

    YAML は引用符のない 18:30 を 1110 という数に、yes や no を true か false に、2026-11-14 を日付に読む。
    文字列のはずの場所がそうなっていたら、引用符で囲むよう知らせる。
    """
    where = ".".join(map(str, path))
    if node is None:
        return []  # 書いていない項目。必ず書く項目かどうかは validate で確かめる
    if isinstance(shape, dict):
        if not isinstance(node, dict):
            return [f"{where} は「名前: 値」の形で書きます"]
        errors = []
        for k, v in node.items():
            sub = shape.get(k, shape.get("*"))
            if sub is not None:
                errors += check_shape(v, sub, path + (k,))
        return errors
    if isinstance(shape, list):
        if not isinstance(node, list):
            return [f"{where} はリストで書きます(1つずつ「- 」で始める)"]
        empty = [f"{where}.{i} が空です(「- 」だけの行を消すか、中身を書く)" for i, v in enumerate(node) if v is None]
        return empty + [e for i, v in enumerate(node) if v is not None for e in check_shape(v, shape[0], path + (i,))]
    is_num = isinstance(node, (int, float)) and not isinstance(node, bool)
    ok = {TEXT: isinstance(node, str), FLAG: isinstance(node, bool), NUM: is_num,
          INT: is_num and isinstance(node, int)}[shape]
    if ok:
        return []
    if shape == TEXT:
        return [f"{where} を、YAML が文字列ではなく {node} と読みました。値を \"…\" で囲んでください"
                "(引用符がないと、18:30 は 1110 という数に、yes や no は true か false に、2026-11-14 は日付になります)"]
    return [f"{where} は{shape}で書きます(いまは {node!r})"]


def describe(path: tuple, c: dict) -> str:
    """content.yaml の場所を、人が読める説明にする。"""
    try:
        if path[:2] == ("meetup", "details"):
            return f"「{c['meetup']['heading']}」の「{c['meetup']['details'][path[2]]['label']}」"
        if path[:2] == ("faq", "items"):
            return f"よくある質問「{c['faq']['items'][path[2]]['q']}」"
        if path[0] == "pages":
            page = c["pages"][path[1]]
            if len(path) > 3 and path[2] == "sections":
                return f"ページ「{page['heading']}」の「{page['sections'][path[3]]['heading']}」"
            return f"ページ「{page['heading']}」"
        if path[0] in ("meetup", "mission", "steps", "promises", "join", "activities"):
            heading = c[path[0]].get("heading", path[0])
            return f"「{heading}」"
    except (KeyError, IndexError, TypeError):
        pass
    return ".".join(str(p) for p in path)


def validate(c, brand: Path) -> list[str]:
    """組み立てられない誤りは BuildError、直したほうがよい点は警告として返す。"""
    if not isinstance(c, dict):
        raise BuildError("content.yaml が空か、「名前: 値」の形になっていません")
    errors = check_shape(c, SHAPE)
    if errors:
        raise BuildError("\n".join(errors))

    warnings = []
    for key in ("site", "org", "cta", "hero", "join", "thanks", "photos"):
        if c.get(key) is None:
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
            if not c[section].get(k):
                errors.append(f"{section}.{k} がありません(必ず書く項目です。書き方は content-guide.md)")
    if not c.get("cta"):
        errors.append("cta(ボタンの文言)がありません")
    if errors:
        raise BuildError("\n".join(errors))

    url = c["site"].get("url")
    if url and not re.fullmatch(r"https://[^\s\"'<>]+/", url):
        errors.append(f"site.url は https:// で始め、/ で終えます(例: https://example.org/join/)。いまは {url}")
    m = c.get("measure") or {}
    if m.get("google_tag_id") and not re.fullmatch(r"(AW|G|GT)-[A-Za-z0-9]+", m["google_tag_id"]):
        errors.append(f"measure.google_tag_id は AW-123456789 のような Google タグの ID にします。いまは {m['google_tag_id']}")
    if m.get("conversion_send_to"):
        if not re.fullmatch(r"AW-\d+/[A-Za-z0-9_-]+", m["conversion_send_to"]):
            errors.append(f"measure.conversion_send_to は AW-123456789/AbCdEf のような形にします。いまは {m['conversion_send_to']}")
        if not m.get("google_tag_id"):
            errors.append("measure.conversion_send_to を使うときは、measure.google_tag_id も書きます")
    if m.get("google_tag_id") and not c["join"].get("endpoint"):
        warnings.append("計測のタグがあるのに、送信先(join.endpoint)が空です。テストの登録がコンバージョンとして数えられます")

    photos = c["photos"]
    for slot, spec in photos.items():
        spec = spec or {}
        f = brand / "photos" / (spec.get("file") or "")
        if not spec.get("file") or not f.exists():
            errors.append(f"写真 {slot} のファイルが見つかりません: {f}")
        if not spec.get("widths"):
            errors.append(f"写真 {slot} に widths がありません")

    uses = [("hero.photo", c["hero"].get("photo"), c["hero"].get("alt"), c["hero"].get("caption")),
            ("hero.photo_phone", c["hero"].get("photo_phone"), c["hero"].get("alt"), c["hero"].get("caption"))]
    if c.get("meetup"):
        mt = c["meetup"]
        uses.append(("meetup", mt.get("photo"), mt.get("alt"), mt.get("caption")))
    if c.get("activities"):
        for i, a in enumerate(c["activities"].get("items") or []):
            uses.append((f"activities.items[{i}]", a.get("photo"), a.get("alt"), a.get("caption")))
    if c.get("og_image"):
        uses.append(("og_image", c["og_image"].get("photo"), "-", "-"))
    for where, slot, alt, cap in uses:
        if slot not in photos:
            errors.append(f"{where} の写真 {slot!r} が photos にありません")
        if not alt:
            errors.append(f"{where} に alt(写っている内容の説明)がありません")
        if not cap:
            errors.append(f"{where} に caption(場所と時間帯)がありません")

    for section in ("activities", "steps", "promises", "faq"):
        if c.get(section) and not c[section].get("items"):
            warnings.append(f"{section} に items がありません。節ごと消すか、項目を書きます")

    for i, line in enumerate(c["hero"]["headline"]):
        if text_width(line) > HEADLINE_LINE_MAX:
            warnings.append(f"見出しの{i + 1}行目が全角{text_width(line):.1f}字です。スマホで3行になります(上限 {HEADLINE_LINE_MAX:.0f} 字)")
    if not 1 <= len(c["hero"]["headline"]) <= 2:
        warnings.append("見出しは1〜2行にします")

    targets = {"#join"}
    if c.get("meetup"):
        targets.add("#meetup")
    if c.get("activities"):
        targets.add("#acts")
    for n in c.get("nav") or []:
        if not n.get("label") or not n.get("href"):
            errors.append("メニュー(nav)の項目には label と href を書きます")
        elif n["href"].startswith("#") and n["href"] not in targets:
            errors.append(f"メニュー「{n['label']}」の行き先 {n['href']} がページにありません")

    pages = c.get("pages") or {}
    for slug, page in pages.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(slug)) or slug in RESERVED_PAGES:
            errors.append(f"pages.yaml のページの名前 {slug!r} は使えません(小文字の英数字とハイフン。index と thanks は使えない)")
            continue
        page = page or {}
        for k in ("title", "heading"):
            if not page.get(k):
                errors.append(f"pages.yaml のページ {slug} に {k} がありません")
        for i, s in enumerate(page.get("sections") or []):
            if not s.get("heading"):
                errors.append(f"pages.yaml のページ {slug} の sections の {i + 1} つ目に heading がありません")

    warnings.extend(check_weekdays(c))

    for path, s in walk_strings(c):
        if "{{" in s or "}}" in s:
            errors.append(f"{'.'.join(map(str, path))} にテンプレートの記号が残っています")
        if "TODO" in s:
            warnings.append(f"{'.'.join(map(str, path))} に TODO が残っています")

    if errors:
        raise BuildError("\n".join(errors))
    return warnings


def page_files(c: dict) -> set[str]:
    """組み立てる HTML のファイル名。"""
    return {"index.html", "thanks.html"} | {f"{slug}.html" for slug in (c.get("pages") or {})}


def check_links(c: dict, known: set[str]) -> None:
    """同じフォルダのページ(about.html、./privacy.html など)へのリンクに、つなぎ先があるかを確かめる。"""
    errors = []
    for path, s in walk_strings(c):
        hrefs = re.findall(r"""href=["']([^"']*)["']""", s) + ([s] if path and path[-1] == "href" else [])
        for h in hrefs:
            target = re.sub(r"^\./", "", re.split(r"[?#]", h)[0])
            if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]*\.html", target) and target not in known:
                errors.append(f"{describe(path, c)} のリンク先 {target} がありません(pages.yaml にページを書くか、リンクを直す)")
    if errors:
        raise BuildError("\n".join(errors))


def _date_or_none(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def check_weekdays(c: dict, today: date | None = None) -> list[str]:
    """日付と曜日が合っているかを確かめる。

    年のない日付は、今日以降でいちばん近いその日付として確かめる(2月29日なら次のうるう年)。
    ただし、2か月以内に過ぎたその日付と曜日が合うなら、曜日の誤りではなく「過ぎた日付」として知らせる。
    """
    today = today or date.today()
    out = []
    for path, s in walk_strings(c):
        plain = re.sub(r"<[^>]+>", "", s)
        for m in DATE_WITH_WEEKDAY.finditer(plain):
            year, month, day, wd = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            if year:
                d = _date_or_none(int(year), month, day)
            else:
                found = [x for y in range(today.year - 1, today.year + 9) if (x := _date_or_none(y, month, day))]
                d = next((x for x in found if x >= today), None)
                prev = max((x for x in found if x < today), default=None)
                if (d and WEEKDAYS[d.weekday()] != wd and prev and WEEKDAYS[prev.weekday()] == wd
                        and (today - prev).days <= RECENT_PAST_DAYS):
                    d = prev
            if d is None:
                out.append(f"{describe(path, c)}: 「{m.group(0)}」は存在しない日付です")
                continue
            actual = WEEKDAYS[d.weekday()]
            if actual != wd:
                out.append(f"{describe(path, c)}: 「{m.group(0)}」の曜日が違います。{d.year}年{month}月{day}日は{actual}曜日です。依頼した人に確かめてください")
            elif d < today:
                out.append(f"{describe(path, c)}: 「{m.group(0)}」は過ぎた日付です({d.year}年{month}月{day}日)。次の日付を依頼した人に確かめてください")
    return out


def unconfirmed_facts(brand: Path) -> list[str]:
    """facts.md の表で「**要確認**」と書いた事実を、公開の前に運営が確かめることとして拾う。"""
    f = brand / "facts.md"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "**要確認**" not in line:
            continue
        fact = line.strip().strip("|").split("|")[0].strip()
        note = line.split("**要確認**", 1)[1].split("|")[0].lstrip(":：").strip()
        out.append(f"{fact}：{note}" if note else fact)
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
    try:
        c = yaml.safe_load(content_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise BuildError(f"content.yaml を読めません。字下げや引用符を確かめてください:\n{e}") from e
    pages_path = brand / "pages.yaml"
    if pages_path.exists() and isinstance(c, dict):
        try:
            c["pages"] = yaml.safe_load(pages_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise BuildError(f"pages.yaml を読めません。字下げや引用符を確かめてください:\n{e}") from e
    warnings = validate(c, brand)
    c["site"]["lang"] = c["site"].get("lang") or "ja"
    c["site"]["theme_color"] = c["site"].get("theme_color") or "#ecebe8"

    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / "assets" / "img"
    exts = ["jpg", "webp"] + (["avif"] if use_avif else [])
    photos = {}
    for slot, spec in c["photos"].items():
        widths = sorted(spec["widths"])
        files = [img_dir / f"{slot}-{w}.{ext}" for w in widths for ext in exts]
        if skip_images and all(f.exists() for f in files):
            from PIL import Image
            with Image.open(img_dir / f"{slot}-{widths[-1]}.jpg") as im:
                w, h = im.size
        else:
            w, h = images.export(brand / "photos" / spec["file"], img_dir, slot, widths,
                                 spec.get("quality") or images.JPEG_QUALITY, use_avif)
        photos[slot] = {"widths": widths, "w": w, "h": h, "mid": widths[len(widths) // 2],
                        "focal": spec.get("focal") or ""}

    og = c.get("og_image") or {"photo": c["hero"]["photo"], "y": 0.55}
    if not (skip_images and (img_dir / "og.jpg").exists()):
        y = og.get("y")
        images.og_image(brand / "photos" / c["photos"][og["photo"]]["file"], img_dir / "og.jpg",
                        0.55 if y is None else y)

    hero, phone = photos[c["hero"]["photo"]], photos[c["hero"]["photo_phone"]]
    r_h, r_v = hero["w"] / hero["h"], phone["w"] / phone["h"]
    theme_css = (brand / "theme.css").exists()
    items = (c.get("activities") or {}).get("items") or []
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

    # すべてのページを組み立ててから書き出す。途中で止まっても、古い HTML と新しい HTML が混ざらない
    pages = c.get("pages") or {}
    rendered = {"index.html": env.get_template("index.html.j2").render(**ctx),
                "thanks.html": env.get_template("thanks.html.j2").render(**ctx)}
    for slug in pages:
        rendered[f"{slug}.html"] = env.get_template("page.html.j2").render(**ctx, page=c_safe["pages"][slug])
    # 手で置いたページ(書き出し先にある HTML)へのリンクは認める
    existing = {p.name for p in out.glob("*.html")}
    check_links(c, page_files(c) | existing)
    for name, text in rendered.items():
        (out / name).write_text(text, encoding="utf-8")
    # pages.yaml から消したページの HTML が残っていると、そのまま公開されてしまう
    stale = sorted(existing - page_files(c))
    if stale:
        warnings.append(f"書き出し先に、今回は組み立てていない HTML があります: {'、'.join(stale)}。前に組み立てたページなら消します")

    for rel in ("assets/css/style.css", "assets/js/main.js"):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE_DIR / rel, out / rel)
    if theme_css:
        shutil.copyfile(brand / "theme.css", out / "assets" / "css" / "theme.css")

    placeholders = []
    for path, s in walk_strings(c):
        for m in PLACEHOLDER.finditer(re.sub(r"<[^>]+>", "", s)):
            placeholders.append({"where": describe(path, c), "text": m.group(0)})
    hash_links = sorted({m for h in rendered.values() for m in re.findall(r'<a href="#">([^<]+)</a>', h)})
    before_publish = []
    if not c["join"].get("endpoint"):
        before_publish.append("参加登録の送信先(join.endpoint)が空です。いまは登録がどこにも届きません")
    if not c["site"].get("url"):
        before_publish.append("公開する URL(site.url)が空です。SNS で共有したときの画像と og:url が出ません")
    if not (c.get("measure") or {}).get("google_tag_id"):
        before_publish.append("Google 広告の計測(measure)が空です。Ad Grants ではコンバージョンの計測が要ります")
    for slug, page in pages.items():
        if page.get("draft"):
            before_publish.append(f"ページ「{page['heading']}」({slug}.html)は下書きです。団体で内容を確かめてから、pages.yaml の draft: true を消します")
    unconfirmed = unconfirmed_facts(brand)

    where = {c["hero"]["photo"]: "パソコンの最初の画面", c["hero"]["photo_phone"]: "スマホの最初の画面"}
    if c.get("meetup"):
        where.setdefault(c["meetup"]["photo"], f"「{c['meetup']['heading']}」")
    for a in items:
        where[a["photo"]] = (where.get(a["photo"], "") + "、" if a["photo"] in where else "") + f"活動「{a['heading']}」"
    photo_rows = [{"slot": f"{slot}-*", "where": where.get(slot, "(使っていない)"),
                   "widths": "・".join(map(str, p["widths"]))} for slot, p in photos.items()]

    # README に書く組み立てのコマンド。どこで実行しても同じ README になるよう、パスは団体のフォルダがある
    # リポジトリのルートから書く。スキルがそのリポジトリの中にあれば相対パス、プラグインとして別の場所
    # (プラグインのキャッシュなど)に入っていれば <lp-build> と書く
    root = _repo_root(brand)
    script = SKILL_DIR / "scripts" / "build_site.py"
    build_script_local = script.resolve().is_relative_to(root) and not _in_plugin_cache(script)
    readme = env.get_template("README.md.j2").render(
        **ctx, brand_rel=_rel(brand, root), out_rel=_rel(out, root), out_name=out.name,
        build_script=_rel(script, root) if build_script_local else "<lp-build>/scripts/build_site.py",
        build_script_local=build_script_local,
        placeholders=placeholders, hash_links=hash_links, photo_rows=photo_rows, unconfirmed=unconfirmed,
        pages=[{"file": f"{slug}.html", "heading": p["heading"], "draft": bool(p.get("draft"))}
               for slug, p in pages.items()],
        credits=bool((c.get("credits") or {}).get("items")))
    (out / "README.md").write_text(readme, encoding="utf-8")

    return {"warnings": warnings, "placeholders": placeholders, "hash_links": hash_links,
            "before_publish": before_publish, "unconfirmed": unconfirmed}


class _Lenient(dict):
    """content.yaml の dict を、テンプレートから c.key で読めるようにする。無い項目は None。"""

    def __init__(self, d):
        super().__init__({k: _wrap(v) for k, v in d.items()})

    def __getattr__(self, key):
        return self.get(key)

    def __missing__(self, key):
        # c.faq['items'] のように dict のメソッドと同じ名前を [] で読むとき、無い項目を None にする
        # (そうしないと Jinja が dict.items を返し、組み立てが止まる)
        return None


def _wrap(v):
    if isinstance(v, dict):
        return _Lenient(v)
    if isinstance(v, list):
        return [_wrap(x) for x in v]
    return v


def _repo_root(p: Path) -> Path:
    """p を含む git リポジトリのルート。リポジトリの外なら、今いるフォルダ。"""
    p = p.resolve()
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return d
    return Path.cwd().resolve()


def _in_plugin_cache(p: Path) -> bool:
    """Claude Code や Codex がプラグインを入れる場所(…/plugins/cache/…)の中か。"""
    parts = p.resolve().parts
    return any(a == "plugins" and b == "cache" for a, b in zip(parts, parts[1:]))


def _rel(p: Path, base: Path) -> str:
    """base からの相対パス。base の外なら、そのままのパス。"""
    p = p.resolve()
    return p.relative_to(base).as_posix() if p.is_relative_to(base) else str(p)


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
    if result["placeholders"] or result["before_publish"]:
        print("  公開の前に決めること:")
        for p in result["placeholders"]:
            print(f"    - {p['where']}: {p['text']}")
        for b in result["before_publish"]:
            print(f"    - {b}")
    if result["unconfirmed"]:
        print("  公開の前に運営が確かめる事実(facts.md の要確認):")
        for u in result["unconfirmed"]:
            print(f"    - {u}")
    if result["hash_links"]:
        print("  行き先がまだないリンク: " + "、".join(result["hash_links"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
