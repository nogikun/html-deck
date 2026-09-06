#!/usr/bin/env python3
"""`.drawio` を、スライドへインライン展開できるSVGに変換する。

    uvx --from <このスキルのディレクトリ>/tools html-deck-drawio <deck>/figures/loop.drawio [--title "図の説明"]

なぜ `<img src="figure.svg">` ではなくインライン展開なのか:

  1. `<img>` の中身はDOMから見えない。文字サイズもコントラストも重なりも測れず、
     このスキルの検査が図に対してだけ無力になる
  2. インラインなら図の色を `var(--accent)` などのトークンで書ける。
     デッキの配色を変えたときに図だけ取り残されない
  3. 外部ファイル参照が1つ減る。CSPとオフライン配布の面でも素直

出力:
  <name>.svg          書き出しと整形が済んだSVG (そのまま貼れる)
  標準出力            スライドに貼るための注意書き

draw.io 本体が要る (macOS: `brew install --cask drawio`)。
`DRAWIO_BIN` で明示指定もできる。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CANDIDATES = [
    os.environ.get("DRAWIO_BIN", ""),
    "/Applications/draw.io.app/Contents/MacOS/draw.io",
    "/Applications/drawio.app/Contents/MacOS/drawio",
    shutil.which("drawio") or "",
    shutil.which("draw.io") or "",
]


def find_drawio() -> str | None:
    for c in CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def pad_viewbox(attrs: str, pad: float) -> str:
    """viewBox を四方へ広げる。

    draw.io は内容にぴったり切り詰めて書き出すため、いちばん外側の要素が
    そのまま図の縁に接する。スライドに貼ると切れて見えるので、
    書き出しの時点で余白を持たせる。ここでやらないと毎回手で直すことになる。
    """
    m = re.search(r'viewBox="\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*"', attrs)
    if not m or pad <= 0:
        return attrs
    x, y, w, h = (float(v) for v in m.groups())
    new = f'viewBox="{x - pad:g} {y - pad:g} {w + pad * 2:g} {h + pad * 2:g}"'
    return attrs[: m.start()] + new + attrs[m.end():]


def clean_svg(svg: str, title: str | None, pad: float = 32.0) -> str:
    """書き出したSVGをスライドに貼れる形へ整える。"""
    # XML宣言とDOCTYPEはHTMLへインラインすると邪魔になる
    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg, flags=re.I)

    # color-scheme: light dark が残ると、閲覧側のダークモードで色が反転する。
    # スライドは固定キャンバスなので、見え方を環境に委ねない。
    svg = svg.replace("color-scheme: light dark;", "")
    svg = re.sub(r"background(-color)?:\s*transparent;\s*", "", svg)
    svg = re.sub(r'\sstyle="\s*"', "", svg)

    # draw.io は <switch> のフォールバック側に、自社FAQへの外部リンクを埋め込む。
    # 画面には出ないが、オフライン配布とCSPの観点では外部参照そのものなので落とす。
    svg = re.sub(r'<a\b[^>]*xlink:href="https?://[^"]*"[^>]*>.*?</a>', "", svg, flags=re.S)
    svg = re.sub(r'\sxlink:href="https?://[^"]*"', "", svg)

    m = re.search(r"<svg\b([^>]*)>", svg)
    if not m:
        raise SystemExit("SVGのルート要素が見つからない。書き出しに失敗している")
    attrs = m.group(1)

    # width/height の固定値を外し、CSS側で大きさを決められるようにする。
    # viewBox が残っていれば比率は保たれる。
    if "viewBox" not in attrs:
        wm = re.search(r'width="([\d.]+)', attrs)
        hm = re.search(r'height="([\d.]+)', attrs)
        if wm and hm:
            attrs += f' viewBox="0 0 {wm.group(1)} {hm.group(1)}"'
        else:
            raise SystemExit("viewBox も width/height も無い。比率を保てないので中断")
    attrs = re.sub(r'\s(width|height)="[^"]*"', "", attrs)
    attrs = pad_viewbox(attrs, pad)

    # 読み上げ用。図は装飾ではないので、必ず名前を持たせる
    if "role=" not in attrs:
        attrs += ' role="img"'
    new_open = f"<svg{attrs}>"
    if title:
        esc = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        new_open += f"<title>{esc}</title>"
    return svg[: m.start()] + new_open + svg[m.end():]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help=".drawio ファイル")
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--title", default=None, help="<title> に入れる図の説明 (読み上げ用)")
    ap.add_argument("--pad", type=float, default=32.0,
                    help="viewBox を四方へ広げる余白(user unit)。既定32。0で無効。"
                         "検査の内側余白24pxは画面上の実効値なので、縮小して貼る分の"
                         "余裕を見て少し大きめに取ってある")
    args = ap.parse_args()

    src = args.source.resolve()
    if not src.is_file():
        print(f"見つからない: {src}", file=sys.stderr)
        return 2

    binary = find_drawio()
    if not binary:
        print(
            "draw.io が見つからない。\n"
            "  macOS : brew install --cask drawio\n"
            "  その他: DRAWIO_BIN に実行ファイルのパスを設定する\n"
            "図が1〜2個で構造が単純なら、draw.io を使わず手書きのインラインSVGでよい。"
            "判断基準は references/figures.md。",
            file=sys.stderr,
        )
        return 3

    raw = src.with_suffix(".raw.svg")
    out = args.out or src.with_suffix(".svg")
    cmd = [binary, "-x", "-f", "svg", "--svg-theme", "light", "-o", str(raw), str(src)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not raw.exists():
        print(f"書き出しに失敗した:\n{proc.stdout}\n{proc.stderr}", file=sys.stderr)
        return 4

    cleaned = clean_svg(raw.read_text(encoding="utf-8"), args.title, args.pad)
    out.write_text(cleaned, encoding="utf-8")
    raw.unlink(missing_ok=True)

    vb = re.search(r'viewBox="([^"]+)"', cleaned)
    box = vb.group(1).split() if vb else ["?", "?", "?", "?"]
    print(f"{out}  viewBox={' '.join(box)}")
    print()
    print("スライドへの貼り方:")
    print(f"  1. {out.name} の中身をそのまま <figure> の中へ貼る (<img> では中身を測れない)")
    print("  2. CSS で外側の箱の大きさを決める。例:")
    print("       figure svg { width: 100%; height: auto; display: block; }")
    print("  3. 色は .drawio 側に theme と同じ16進値を書いておけばそれで通る")
    print("     (draw.io XML では var() が使えない)。トークンに無い値だけ palette_drift で出る")
    print("  4. check_deck.py で図の中の文字サイズ・重なり・線幅まで測る")
    return 0


if __name__ == "__main__":
    sys.exit(main())
