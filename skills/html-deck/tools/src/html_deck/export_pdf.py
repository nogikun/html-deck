#!/usr/bin/env python3
"""全スライドを 1600x900 のまま1本のPDFにまとめる。

    uv run --project <このスキルのディレクトリ>/tools html-deck-pdf <deck-dir> [-o deck.pdf] [--allow-font-fallback]

固定PDFは「渡した先で見た目が動かない」納品形式。Chrome は描画に使った face を
PDF に埋め込むので、**このマシンで描けた通り**が固定される。
逆に言うと、指定した書体がこのマシンに無ければ、黙ってフォールバックした結果が
そのまま固定される。それでは「見た目を固定して渡した」と言えないので、
書き出す前に実使用フォントを CDP で読み、theme.css の第一候補と照合する。

編集可能なPPTXにはならない。PPTXが必須なら最初からPPTX側で作る。
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path


FACE_RE = re.compile(r"--(display|body|mono)\s*:\s*([^;}]+)")


def declared_faces(css: str) -> dict[str, str]:
    """theme.css の各役割の**第一候補**。そこから落ちたら置換が起きている。"""
    out: dict[str, str] = {}
    for role, stack in FACE_RE.findall(css):
        first = stack.split(",")[0].strip().strip("\"'")
        if first and not first.startswith("var("):
            out[role] = first
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s_-]+", "", s).lower()


def used(face: str, platform_fonts: set[str]) -> bool:
    """実使用フォント名との突き合わせ。

    CSS の家族名と OS の家族名は綴りが揺れる ("Yu Gothic Medium" / "Yu Gothic")。
    どちらかがどちらかを含んでいれば、その家族が使われたと見なす。
    """
    f = _norm(face)
    return any(f in _norm(p) or _norm(p) in f for p in platform_fonts)


def platform_fonts(cdp) -> set[str]:
    """いま開いているページで、実際に描画に使われた face。

    CSS.getPlatformFontsForNode は「その要素が自分で抱えている文字」しか返さない。
    body に投げても、中身が要素で包まれていれば空で返ってくる (実測)。
    なので要素を1つずつ舐めて合算する。
    ponytail: 要素数ぶんの CDP 往復。ローカルなので1枚あたり数十msで済む。
    枚数が3桁になって遅いと感じたら、文字を持つ要素だけに絞る。
    """
    root = cdp.send("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
    nodes = cdp.send("DOM.querySelectorAll", {"nodeId": root, "selector": "body, body *"})["nodeIds"]
    out: set[str] = set()
    for nid in nodes:
        try:
            fonts = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": nid})["fonts"]
        except Exception:      # noqa: BLE001 - 消えたノードは飛ばす
            continue
        out |= {f["familyName"] for f in fonts if f.get("glyphCount", 0) > 0}
    return out


def _utf8_io() -> None:
    """日本語しか出さないのに Windows の既定は cp932。パイプに繋ぐと落ちる。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _utf8_io()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--allow-font-fallback", action="store_true",
                    help="指定書体が無くても書き出す (その環境の代替書体で固定される)")
    args = ap.parse_args()

    deck = args.deck.resolve()
    files = sorted((deck / "slides").glob("*.html"))
    if not files:
        print("slides/*.html がない", file=sys.stderr)
        return 2
    out = args.out or deck / f"{deck.name}.pdf"

    theme = deck / "theme.css"
    want = declared_faces(theme.read_text(encoding="utf-8")) if theme.is_file() else {}

    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900}, reduced_motion="reduce")
        cdp = page.context.new_cdp_session(page)
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        for f in files:
            page.goto(f.as_uri())
            page.wait_for_load_state("load")
            page.wait_for_timeout(120)
            seen |= platform_fonts(cdp)
            data = page.pdf(width="1600px", height="900px", print_background=True, margin={
                "top": "0", "right": "0", "bottom": "0", "left": "0"})
            for pg in PdfReader(io.BytesIO(data)).pages:
                writer.add_page(pg)
        browser.close()

    print("実使用フォント: " + (", ".join(sorted(seen)) or "(取得できず)"))
    missing = [(role, face) for role, face in want.items()
               if role != "mono" and not used(face, seen)]
    for role, face in want.items():
        mark = "使われた" if used(face, seen) else "**使われていない**"
        print(f"  --{role:<8} {face:<32} {mark}")

    if missing and not args.allow_font_fallback:
        print("\nこの環境に指定書体が無く、代替書体で描画されている:", file=sys.stderr)
        for role, face in missing:
            print(f"  --{role}: {face}", file=sys.stderr)
        print("この PDF は theme.css で決めた見た目を固定できていない。書体を入れるか、"
              "theme.css を実在する書体に直すか、承知のうえなら --allow-font-fallback を付ける。",
              file=sys.stderr)
        return 1

    with open(out, "wb") as fh:
        writer.write(fh)
    print(f"\n{len(files)}枚 → {out}")
    if missing:
        print("※ 指定書体が無いまま書き出した。渡した先ではなくこのマシンの代替書体で固定されている。")
    print("納品前に必ず1度は開いて、文字化け・欠落・切れがないか目で確認する。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
