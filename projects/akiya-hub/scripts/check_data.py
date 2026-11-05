#!/usr/bin/env python3
"""空き家活用・コミュニティ拠点プロジェクトのデータ(data/*.csv)を点検する。

使い方(リポジトリのルートで):
  python3 projects/akiya-hub/scripts/check_data.py
  python3 projects/akiya-hub/scripts/check_data.py --today 2026-11-20   # 今日の日付を変えて試す

運用ルール(projects/akiya-hub/CLAUDE.md)のうち、機械で確かめられることを見る。決まりは data/README.md。

NG(終了コード 1):
- 列名が決まりと違う。ID の形がおかしい、重なっている
- 値が決まった列に、決まりにない値がある。日付の形がおかしい、未来の日付がある
- 確度が「確認済み」「未確認」なのに、出典URL か確認日がない
- 出典URL が URL でも連絡ID(O-001 など)でもない。関連ID の行がない
- 募集終了の物件を、現行候補として扱っている。受付終了の資金を、応募の候補にしている
- メールアドレスや電話番号らしいもの、番地らしいものがある(公開のリポジトリなので)
- 送ったことになっている問い合わせに、承認日か送信日がない
注意(終了コードは変えない):
- 募集中の物件の確認日が14日より古い。現行候補の募集状況が「不明」
- 制度や資金の確認日が、今の年度(4月始まり)より前
- 締切を過ぎたのに「受付中」「受付前」のまま
- 期日を過ぎた問い合わせ
必要なもの:Python 3.9 以上(標準ライブラリだけ)。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
STALE_LISTING_DAYS = 14

CONFIDENCE = {"確認済み", "未確認", "推測"}
ABILITY = {"可", "相談可", "不可", "不明"}
RECEIPT = {"受付中", "受付前", "受付終了", "通年", "不明"}
URL_COLUMNS = {"掲載URL", "出典URL", "交通の出典URL"}

SCHEMAS = {
    "properties.csv": {
        "id": ("物件ID", "P"),
        "columns": "物件ID,検討段階,募集状況,取引,入手経路,物件名,都道府県,市区町村,町名,最寄り駅,駅から,都心まで,交通の出典URL,交通の確認日,家賃_月額_円,価格_円,初期費用_円,間取り,建物面積_㎡,土地面積_㎡,築年,建物の状態,用途地域,事業利用,音出し,改修,契約の形,所有者と直接,両立の見込み,掲載URL,出典URL,確認日,確度,未確認の項目,次の行動,メモ",
        "required": ["検討段階", "募集状況", "確度"],
        "enums": {
            "検討段階": {"候補", "問い合わせ中", "内見予定", "内見済み", "交渉中", "契約", "見送り", "参考"},
            "募集状況": {"募集中", "募集終了", "不明", "非公開"},
            "取引": {"賃貸", "売買", "賃貸・売買", "不明"},
            "入手経路": {"空き家バンク", "所有者と直接", "不動産会社", "不動産サイト", "自治体の紹介", "人の紹介", "その他"},
            "建物の状態": {"すぐ住める", "小さな修繕", "大きな改修", "不明"},
            "事業利用": ABILITY, "音出し": ABILITY, "改修": ABILITY,
            "所有者と直接": {"はい", "仲介あり", "不明"},
            "両立の見込み": {"高い", "ある", "低い", "不明"},
            "確度": CONFIDENCE,
        },
        "dates": ["交通の確認日", "確認日"],
        "ints": ["家賃_月額_円", "価格_円", "初期費用_円", "築年"],
        "numbers": ["建物面積_㎡", "土地面積_㎡"],
        "refs": [],
    },
    "municipalities.csv": {
        "id": ("制度ID", "M"),
        "columns": "制度ID,都道府県,市区町村,種類,制度名,内容,対象・条件,金額・上限,法人の利用,両立への影響,受付状況,受付期間,締切,窓口,関連物件ID,出典URL,確認日,確度,未確認の項目,次の行動,メモ",
        "required": ["都道府県", "種類", "制度名", "受付状況", "確度"],
        "enums": {
            "種類": {"空き家バンク", "所有者マッチング", "改修の補助", "取得の補助", "家賃の補助", "移住の支援", "お試し居住", "地域活動の支援", "相談窓口", "規制・手続き", "その他"},
            "法人の利用": {"可", "個人のみ", "不明"},
            "受付状況": RECEIPT,
            "確度": CONFIDENCE,
        },
        "dates": ["締切", "確認日"],
        "ints": [], "numbers": [],
        "refs": ["関連物件ID"],
    },
    "funding.csv": {
        "id": ("資金ID", "F"),
        "columns": "資金ID,種類,名称,実施主体,対象,使い道,金額・上限,補助率・自己負担,法人の応募,居住部分,受付状況,締切,応募の状態,関連ID,出典URL,確認日,確度,未確認の項目,次の行動,メモ",
        "required": ["種類", "名称", "受付状況", "応募の状態", "確度"],
        "enums": {
            "種類": {"助成金", "補助金", "融資", "寄付", "クラウドファンディング", "協賛", "その他"},
            "法人の応募": {"可", "不可", "不明"},
            "居住部分": {"対象", "対象外", "不明"},
            "受付状況": RECEIPT,
            "応募の状態": {"調査中", "候補", "準備中", "応募済み", "採択", "不採択", "見送り"},
            "確度": CONFIDENCE,
        },
        "dates": ["締切", "確認日"],
        "ints": [], "numbers": [],
        "refs": ["関連ID"],
    },
    "outreach.csv": {
        "id": ("連絡ID", "O"),
        "columns": "連絡ID,作成日,相手の種類,相手,関連ID,手段,要旨,下書き,状態,承認日,承認した人,送信日,返事の要旨,次の行動,期日,メモ",
        "required": ["作成日", "相手の種類", "相手", "手段", "状態"],
        "enums": {
            "相手の種類": {"所有者", "不動産会社", "自治体", "空き家バンク", "支援団体", "助成団体", "専門家", "その他"},
            "手段": {"メール", "問い合わせフォーム", "電話", "訪問", "郵送", "その他"},
            "状態": {"下書き", "承認待ち", "承認済み", "送信済み", "返事あり", "やりとり中", "終了", "見送り"},
        },
        "dates": ["作成日", "承認日", "送信日", "期日"],
        "ints": [], "numbers": [],
        "refs": ["関連ID"],
    },
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\d-])0\d{1,4}-\d{1,4}-\d{3,4}(?![\d-])|(?<![\d-])0\d{9,10}(?![\d-])")
BANCHI_RE = re.compile(r"\d+\s*(番地|番|号)|\d+\s*[-‐−ー－]\s*\d+")
URL_RE = re.compile(r"^https?://\S+$")
ACTIVE_STAGES = {"候補", "問い合わせ中", "内見予定", "内見済み", "交渉中", "契約"}
APPROVED = {"承認済み", "送信済み", "返事あり", "やりとり中", "終了"}
SENT = {"送信済み", "返事あり", "やりとり中", "終了"}
NEEDS_APPROVAL = {"メール", "問い合わせフォーム", "郵送", "その他"}


def tokens(value: str) -> list[str]:
    return [t.strip() for t in value.split(";") if t.strip()]


def parse_date(value: str):
    if not DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def fiscal_year_start(today: date) -> date:
    return date(today.year if today.month >= 4 else today.year - 1, 4, 1)


def load(name: str):
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        rows = []
        for cells in reader:
            if not any(c.strip() for c in cells):
                continue
            rows.append((reader.line_num, cells))
    return header, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="data/*.csv を点検する")
    parser.add_argument("--today", help="今日の日付(YYYY-MM-DD)。試すときだけ")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    fy_start = fiscal_year_start(today)

    errors: list[str] = []
    notes: list[str] = []
    tables: dict[str, list[tuple[int, dict]]] = {}

    for name, schema in SCHEMAS.items():
        if not (DATA / name).exists():
            errors.append(f"{name}: ファイルがない")
            continue
        header, rows = load(name)
        expected = schema["columns"].split(",")
        if header != expected:
            missing = [c for c in expected if c not in header]
            extra = [c for c in header if c not in expected]
            errors.append(f"{name}: 列名が決まりと違う(足りない列:{missing or 'なし'}、余分な列:{extra or 'なし'}。順番も決まりのとおりに)")
            continue
        tables[name] = []
        for line, cells in rows:
            if len(cells) != len(expected):
                errors.append(f"{name} {line}行目: 列の数が {len(cells)}(決まりは {len(expected)})")
                continue
            tables[name].append((line, {k: v.strip() for k, v in zip(expected, cells)}))

    all_ids: set[str] = set()
    for name, rows in tables.items():
        id_col, prefix = SCHEMAS[name]["id"]
        seen: set[str] = set()
        for line, row in rows:
            rid = row[id_col]
            if not re.fullmatch(rf"{prefix}-\d{{3,}}", rid):
                errors.append(f"{name} {line}行目: {id_col} は {prefix}-001 の形にする(今は「{rid}」)")
            elif rid in seen:
                errors.append(f"{name} {line}行目: {id_col} {rid} が重なっている")
            seen.add(rid)
        all_ids |= seen
    outreach_ids = {row["連絡ID"] for _, row in tables.get("outreach.csv", [])}
    property_ids = {row["物件ID"] for _, row in tables.get("properties.csv", [])}

    for name, rows in tables.items():
        schema = SCHEMAS[name]
        for line, row in rows:
            where = f"{name} {line}行目({row[schema['id'][0]] or 'IDなし'})"
            ng = lambda msg: errors.append(f"{where}: {msg}")  # noqa: E731
            note = lambda msg: notes.append(f"{where}: {msg}")  # noqa: E731

            for col in schema["required"]:
                if not row[col]:
                    ng(f"{col} が空")
            for col, allowed in schema["enums"].items():
                if row[col] and row[col] not in allowed:
                    ng(f"{col} の「{row[col]}」は決まりにない(使える値:{'、'.join(sorted(allowed))})")
            dates = {}
            for col in schema["dates"]:
                if row[col]:
                    d = parse_date(row[col])
                    if d is None:
                        ng(f"{col} は YYYY-MM-DD にする(今は「{row[col]}」)")
                    elif col != "締切" and col != "期日" and d > today:
                        ng(f"{col} {row[col]} が今日より後")
                    dates[col] = d
            for col in schema["ints"]:
                if row[col] and not re.fullmatch(r"\d+", row[col]):
                    ng(f"{col} は半角の整数にする(カンマや「万」を使わない。今は「{row[col]}」)")
            for col in schema["numbers"]:
                if row[col] and not re.fullmatch(r"\d+(\.\d+)?", row[col]):
                    ng(f"{col} は半角の数にする(今は「{row[col]}」)")

            for col, value in row.items():
                if col in URL_COLUMNS or not value:
                    continue
                text = unicodedata.normalize("NFKC", value)
                if EMAIL_RE.search(text):
                    ng(f"{col} にメールアドレスらしいものがある。公開のリポジトリなので書かない")
                if PHONE_RE.search(text):
                    ng(f"{col} に電話番号らしいものがある。公開のリポジトリなので書かない")
            for col in URL_COLUMNS & row.keys():
                for t in tokens(row[col]):
                    if URL_RE.match(t):
                        continue
                    if col == "出典URL" and re.fullmatch(r"O-\d{3,}", t):
                        if t not in outreach_ids:
                            ng(f"出典URL の {t} が outreach.csv にない")
                        continue
                    ng(f"{col} の「{t}」は URL(https://…)か連絡ID(O-001 など)にする")

            if "確度" in row and row["確度"] in {"確認済み", "未確認"}:
                if not row["出典URL"]:
                    ng(f"確度が{row['確度']}なのに、出典URL がない")
                if not row["確認日"]:
                    ng(f"確度が{row['確度']}なのに、確認日がない")
            for col in schema["refs"]:
                for t in tokens(row[col]):
                    pool = property_ids if col == "関連物件ID" else all_ids
                    if t not in pool:
                        ng(f"{col} の {t} がどのデータにもない")

            if name == "properties.csv":
                if BANCHI_RE.search(unicodedata.normalize("NFKC", row["町名"])):
                    ng("町名に番地らしいものがある。町名までにする")
                status, stage = row["募集状況"], row["検討段階"]
                if status == "募集終了" and stage not in {"参考", "見送り"}:
                    ng(f"募集終了なのに、検討段階が「{stage}」。現行候補にしない(参考か見送りにする)")
                if status in {"募集中", "非公開"} and not row["確認日"]:
                    ng(f"募集状況が{status}なのに、確認日がない")
                checked = dates.get("確認日")
                if status == "募集中" and checked and today - checked > timedelta(days=STALE_LISTING_DAYS):
                    note(f"募集中の確認日 {row['確認日']} から{STALE_LISTING_DAYS}日を過ぎた。判断に使う前に確かめ直す")
                if status == "不明" and stage in ACTIVE_STAGES:
                    note("現行候補の募集状況が不明。確かめるまで候補として扱わない")
                if row["都心まで"] and not (row["交通の出典URL"] and row["交通の確認日"]):
                    ng("都心まで を書いたのに、交通の出典URL か交通の確認日がない")

            if name in {"municipalities.csv", "funding.csv"}:
                checked = dates.get("確認日")
                if checked and checked < fy_start and row["受付状況"] != "受付終了":
                    note(f"確認日 {row['確認日']} は今の年度({fy_start.year}年度)より前。確かめ直す")
                deadline = dates.get("締切")
                if deadline and deadline < today and row["受付状況"] in {"受付中", "受付前"}:
                    note(f"締切 {row['締切']} を過ぎたのに、受付状況が「{row['受付状況']}」。確かめ直す")
            if name == "funding.csv" and row["受付状況"] == "受付終了" and row["応募の状態"] in {"候補", "準備中"}:
                ng(f"受付終了なのに、応募の状態が「{row['応募の状態']}」。次の回を待つなら受付前にし、確かめた出典を書く")

            if name == "outreach.csv":
                state, means = row["状態"], row["手段"]
                if state in APPROVED and means in NEEDS_APPROVAL and not row["承認日"]:
                    ng(f"状態が{state}なのに、承認日がない。送る前に人の承認が要る")
                if state in APPROVED and row["承認日"] and not row["承認した人"]:
                    ng("承認した人(役割)がない")
                if state in SENT and not row["送信日"]:
                    ng(f"状態が{state}なのに、送信日がない")
                a, s = dates.get("承認日"), dates.get("送信日")
                if a and s and s < a:
                    ng(f"送信日 {row['送信日']} が承認日 {row['承認日']} より前")
                if row["下書き"] and not (PROJECT / row["下書き"]).exists():
                    ng(f"下書き {row['下書き']} がない(projects/akiya-hub/ からの場所で書く)")
                due = dates.get("期日")
                if due and due < today and state not in {"終了", "見送り"}:
                    note(f"期日 {row['期日']} を過ぎた。次の行動:{row['次の行動'] or '(空)'}")

    props = [r for _, r in tables.get("properties.csv", [])]
    current = [r for r in props if r["募集状況"] in {"募集中", "非公開"} and r["検討段階"] in ACTIVE_STAGES]
    waiting = [r for _, r in tables.get("outreach.csv", []) if r["状態"] == "承認待ち"]
    print(f"物件 {len(props)}件(現行候補 {len(current)}件)、"
          f"制度 {len(tables.get('municipalities.csv', []))}件、資金 {len(tables.get('funding.csv', []))}件、"
          f"問い合わせ {len(tables.get('outreach.csv', []))}件(承認待ち {len(waiting)}件)")
    for msg in notes:
        print(f"注意 {msg}")
    for msg in errors:
        print(f"NG   {msg}")
    print("OK" if not errors else f"NG が {len(errors)}件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
