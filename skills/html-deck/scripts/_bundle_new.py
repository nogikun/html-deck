#!/usr/bin/env python3
"""デッキ一式を1枚のHTMLに畳む。渡すときはこれ1つで済む。

    python3 scripts/bundle_deck.py <deck-dir> [-o deck.html]

やること:
  1. slides/*.html を1枚ずつ読み、<link href="theme.css"> をその中身に差し替える
  2. ローカル参照 (画像・woff2) を data: URI に畳む
  3. ビューア (assets/review.html) の slides 配列に**本文そのもの**を入れて書き出す

スライドを <section> として1つの文書に並べることはしない。各スライドは自分の
文書スコープ前提で CSS を書いていて (body {} や .claim)、並べれば必ず衝突する。
iframe のまま src を srcdoc に変えれば、分離は今と1ミリも変わらず、
check_deck.py が実測した値がそのまま生きる。

フォントは埋め込む。見た目を完全に固定したいなら PDF (scripts/export_pdf.py)。
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_deck_adapter as adapter  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"

LINK_RE = re.compile(r"""<link\b[^>]*\brel\s*=\s*["']?stylesheet["']?[^>]*>""", re.I)
HREF_RE = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)
ATTR_URL_RE = re.compile(r"""\b(src|href)\s*=\s*["']([^"']+)["']""", re.I)
CSS_URL_RE = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.I)


def is_local(url: str) -> bool:
    return bool(url) and not url.startswith(("http://", "https://", "data:", "#", "mailto:"))


def local_file(base: Path, url: str, root: Path) -> Path | None:
    """デッキの中に収まる実ファイルだけを返す。外に出るものは None。

    ここで拾ったものは全部バンドルに焼き込まれ、そのまま人に送られる。
    `../../.ssh/id_rsa` や絶対パスを素通しすると、デッキ外のファイルが
    成果物に同梱されて出ていく。相対か絶対かを個別に判定するより、
    解決した実パスがデッキ配下に入っているかを1回見るほうが漏れがない。
    """
    if not is_local(url):
        return None
    try:
        p = (base / url).resolve()
    except (OSError, ValueError):
        return None
    if not p.is_relative_to(root):
        print(f"warning: デッキ外への参照を畳まずに残した: {url}", file=sys.stderr)
        return None
    return p if p.is_file() else None


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def inline_css_urls(css: str, base: Path, root: Path) -> str:
    """CSS 内の url(...) を data: に畳む。@font-face の woff2 がこれで入る。"""
    def sub(m):
        f = local_file(base, m.group(1), root)
        return f"url({data_uri(f)})" if f else m.group(0)
    return CSS_URL_RE.sub(sub, css)


def inline_slide(path: Path, root: Path) -> str:
    """1枚のスライドを、外部参照ゼロの HTML 文字列にする。"""
    html = path.read_text(encoding="utf-8")

    def swap_link(m):
        href = HREF_RE.search(m.group(0))
        css_path = local_file(path.parent, href.group(1), root) if href else None
        if not css_path:
            return m.group(0)
        css = inline_css_urls(css_path.read_text(encoding="utf-8"), css_path.parent, root)
        return f"<style>\n{css}\n</style>"
    html = LINK_RE.sub(swap_link, html)

    # 画像など。<link> は上で処理済みなので、ここに残るのは src 参照が主。
    def swap_attr(m):
        attr, url = m.group(1), m.group(2)
        if attr.lower() == "href" or url.endswith(".css"):
            return m.group(0)
        f = local_file(path.parent, url, root)
        return f'{attr}="{data_uri(f)}"' if f else m.group(0)
    html = ATTR_URL_RE.sub(swap_attr, html)

    # スライド内に残った <style> の url() も畳む
    html = inline_css_urls(html, path.parent, root)
    return html


def main() -> int:
    adapter.utf8_io()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=None)
    args = ap.parse_args()

    deck = args.deck.resolve()
    if not adapter.is_deck(deck):
        print(f"error: {deck} に slides/ がありません", file=sys.stderr)
        return 2
    metas = adapter.slides(deck)
    if not metas:
        print("error: slides/*.html がありません", file=sys.stderr)
        return 2

    rows = []
    for meta in metas:
        body = inline_slide(deck / meta["file"], deck)
        left = [u for _, u in ATTR_URL_RE.findall(body) if is_local(u)]
        if left:
            print(f"warning: {meta['file']} に畳めない参照が残った: {', '.join(sorted(set(left))[:4])}",
                  file=sys.stderr)
        rows.append([body, meta["title"]])

    title = adapter.deck_title(deck)
    html = (ASSETS / "review.html").read_text(encoding="utf-8")
    html = html.replace("/* __SHELL__ */", (ASSETS / "shell.css").read_text(encoding="utf-8"))
    html = html.replace("__DECK_TITLE__", title)
    html = html.replace("const BUNDLED = false;", "const BUNDLED = true;")

    # </script> が本文に混ざると外側のスクリプトがそこで終わる。
    payload = json.dumps(rows, ensure_ascii=False).replace("</script", "<\\/script")
    html = re.sub(r"// <slides>.*?// </slides>",
                  lambda _: f"// <slides>\nconst slides0 = {payload};\n// </slides>",
                  html, flags=re.S)

    out = args.out or deck / f"{deck.name}.html"
    out.write_text(html, encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"{len(rows)}枚 → {out}  ({kb:,.0f} KB)")
    print("外部参照なしの1ファイル。そのまま送れる (レビュー機能は付かない)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
