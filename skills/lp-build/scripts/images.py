#!/usr/bin/env python3
"""写真の色調をそろえ、ページ用に AVIF・WebP・JPEG を幅ごとに書き出す。

使い方:
  # 撮った写真(または仮置きの写真)に、D3 の共通の色調をかける
  python3 images.py grade 元の写真.jpg brand/<団体>/photos/hero-h.jpg

  # 1枚を幅ごとに書き出す(build_site.py が内部で同じ処理をする)
  python3 images.py export brand/<団体>/photos/work.jpg out/assets/img --slot work --widths 800 1200 1600

必要なもの: Pillow(AVIF を書き出すには 11.2 以上)、grade には numpy。
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageOps, features

JPEG_QUALITY = 78
AVIF_QUALITY = 55


def avif_supported() -> bool:
    try:
        return bool(features.check("avif"))
    except Exception:  # 古い Pillow には avif の項目自体がない
        return False


def load(path: Path) -> Image.Image:
    """写真を開き、撮ったときの向きに直して、sRGB の RGB にそろえる。

    iPhone などの写真は Display P3 などの色で保存されていることがある。書き出す JPEG・WebP・AVIF には
    色のプロファイルを付けず、ブラウザは sRGB として表示するので、先に sRGB に変換しておく。
    """
    with Image.open(path) as src:
        icc = src.info.get("icc_profile")
        im = ImageOps.exif_transpose(src)
    if icc:
        im = to_srgb(im, icc)
    im = im.convert("RGB")
    im.info.pop("icc_profile", None)  # AVIF だけにプロファイルが付かないよう、どの形式にも付けない
    return im


def to_srgb(im: Image.Image, icc: bytes) -> Image.Image:
    try:
        from PIL import ImageCms
    except ImportError:  # littlecms のない Pillow
        print("注意: この Pillow は色のプロファイルを変換できません。色がずれることがあります", file=sys.stderr)
        return im
    if im.mode not in ("RGB", "CMYK", "L"):
        im = im.convert("RGB")
    try:
        return ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                         ImageCms.createProfile("sRGB"), outputMode="RGB")
    except (ImageCms.PyCMSError, OSError, ValueError) as e:
        print(f"注意: 色のプロファイルを読めないので、sRGB として扱います({e})", file=sys.stderr)
        return im


def grade(im: Image.Image) -> Image.Image:
    """D3 の共通の色調。

    写真ごとに白の基準を合わせず、全部に同じ処理だけをかける。
    1. 彩度を全体で 15% 下げる。黄〜橙(30〜65°)はさらに 20%、緑(70〜170°)は 50% 下げる
    2. 明るいところを少し暖かく、暗いところを少し冷たくする
    3. 中間のコントラストを 8% 下げ、黒を 12/255 まで持ち上げ、白を 245/255 で止める
    """
    import numpy as np

    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    hsv = np.asarray(im.convert("HSV")).astype(np.float32) / 255.0
    hue = hsv[..., 0] * 360
    s_mul = np.full(hue.shape, 0.85, np.float32)
    s_mul = np.where((hue >= 30) & (hue < 65), 0.85 * 0.80, s_mul)
    s_mul = np.where((hue >= 70) & (hue < 170), 0.85 * 0.50, s_mul)
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    a = lum + (a - lum) * s_mul[..., None]
    shadow = (1 - lum) ** 2
    high = lum ** 2
    a = a + np.concatenate(
        [-0.012 * shadow + 0.018 * high, 0 * shadow + 0.006 * high, 0.022 * shadow - 0.020 * high],
        axis=-1,
    )
    a = 0.5 + (a - 0.5) * 0.92
    a = 12 / 255 + a * (233 / 255)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def export(src: Path, out_dir: Path, slot: str, widths: list[int], quality: int = JPEG_QUALITY,
           avif: bool = True) -> tuple[int, int]:
    """slot-幅.{avif,webp,jpg} を書き出し、いちばん大きい書き出しの幅と高さを返す。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    im = load(src)
    size = (0, 0)
    for w in sorted(widths):
        r = im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        r.save(out_dir / f"{slot}-{w}.jpg", "JPEG", quality=quality, optimize=True, progressive=True)
        r.save(out_dir / f"{slot}-{w}.webp", "WEBP", quality=quality, method=6)
        if avif:
            r.save(out_dir / f"{slot}-{w}.avif", "AVIF", quality=AVIF_QUALITY)
        size = r.size
    return size


def og_image(src: Path, out_path: Path, y: float = 0.55) -> None:
    """SNS 用の 1200×630 を切り出す。y は切り出す縦位置(0=上、1=下)。"""
    im = load(src)
    w, h = im.size
    crop_h = round(w * 630 / 1200)
    if crop_h > h:  # 縦が足りないときは横を詰める
        crop_w = round(h * 1200 / 630)
        left = (w - crop_w) // 2
        box = (left, 0, left + crop_w, h)
    else:
        top = int((h - crop_h) * y)
        box = (0, top, w, top + crop_h)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.crop(box).resize((1200, 630), Image.LANCZOS).save(out_path, "JPEG", quality=82, optimize=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grade", help="D3 の共通の色調をかけて保存する")
    g.add_argument("src", type=Path)
    g.add_argument("dst", type=Path)
    g.add_argument("--max-width", type=int, default=2400, help="この幅より大きければ縮める(既定 2400)")

    e = sub.add_parser("export", help="幅ごとに AVIF・WebP・JPEG を書き出す")
    e.add_argument("src", type=Path)
    e.add_argument("out_dir", type=Path)
    e.add_argument("--slot", required=True, help="書き出すファイル名の先頭(例: hero-h)")
    e.add_argument("--widths", type=int, nargs="+", required=True)
    e.add_argument("--quality", type=int, default=JPEG_QUALITY)
    e.add_argument("--no-avif", action="store_true")

    args = p.parse_args()
    if args.cmd == "grade":
        im = load(args.src)
        if im.width > args.max_width:
            im = im.resize((args.max_width, round(im.height * args.max_width / im.width)), Image.LANCZOS)
        args.dst.parent.mkdir(parents=True, exist_ok=True)
        grade(im).save(args.dst, "JPEG", quality=90, optimize=True)
        print(f"保存しました: {args.dst} ({im.width}×{im.height})")
        return 0

    use_avif = not args.no_avif
    if use_avif and not avif_supported():
        print("この Pillow は AVIF を書き出せません。pip install -U pillow で更新するか、--no-avif を付けてください。",
              file=sys.stderr)
        return 2
    w, h = export(args.src, args.out_dir, args.slot, args.widths, args.quality, use_avif)
    print(f"書き出しました: {args.slot} {args.widths} (最大 {w}×{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
