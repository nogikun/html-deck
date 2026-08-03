#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.44", "pypdf>=4.2"]
# ///
"""全スライドを 1600x900 のまま1本のPDFにまとめる。

    uv run scripts/export_pdf.py <deck-dir> [-o deck.pdf]

固定PDFは「対象環境でフォントが違っても崩れない」納品形式。
HTMLをそのまま渡す場合と違い、閲覧側のフォント有無に左右されない。
編集可能なPPTXにはならない。PPTXが必須なら最初からPPTX側で作る。
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=None)
    args = ap.parse_args()

    deck = args.deck.resolve()
    files = sorted((deck / "slides").glob("*.html"))
    if not files:
        print("slides/*.html がない", file=sys.stderr)
        return 2
    out = args.out or deck / f"{deck.name}.pdf"

    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900}, reduced_motion="reduce")
        for f in files:
            page.goto(f.as_uri())
            page.wait_for_load_state("load")
            page.wait_for_timeout(120)
            data = page.pdf(width="1600px", height="900px", print_background=True, margin={
                "top": "0", "right": "0", "bottom": "0", "left": "0"})
            for pg in PdfReader(io.BytesIO(data)).pages:
                writer.add_page(pg)
        browser.close()

    with open(out, "wb") as fh:
        writer.write(fh)
    print(f"{len(files)}枚 → {out}")
    print("納品前に必ず1度は開いて、文字化け・欠落・切れがないか目で確認する。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
