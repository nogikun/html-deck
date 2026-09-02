#!/usr/bin/env python3
"""レビュー機構のうち、html-deck 固有の知識をここに閉じ込める。

汎用スキルとして切り出すときは、このファイルと references/review.md だけを
差し替えれば済む状態を保つこと。review_server.py と review_anchor.py は
「ディレクトリを配信して、DOM の位置をソース行に解決する」以上のことを知らない。
"""

from __future__ import annotations

import re
from pathlib import Path

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def is_deck(root: Path) -> bool:
    return (root / "slides").is_dir()


def slides(root: Path) -> list[dict]:
    """slides/*.html をファイル名順に並べ、<title> を見出しとして返す。

    index.html のスライド一覧を再生成する check_deck.py と同じ順序規則。
    """
    out = []
    for path in sorted((root / "slides").glob("*.html")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = TITLE_RE.search(text)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else path.stem
        out.append({
            "id": path.stem,
            "file": f"slides/{path.name}",
            "title": title,
        })
    return out


def current_round(root: Path) -> int:
    """.loop/round-N のうち最大の N。まだ検査していなければ 0。"""
    loop = root / ".loop"
    if not loop.is_dir():
        return 0
    rounds = [
        int(m.group(1))
        for p in loop.iterdir()
        if (m := re.fullmatch(r"round-(\d+)", p.name)) and p.is_dir()
    ]
    return max(rounds) if rounds else 0


def feedback_dir(root: Path) -> Path:
    d = root / ".loop" / "feedback"
    d.mkdir(parents=True, exist_ok=True)
    return d


def deck_title(root: Path) -> str:
    """deck.md の見出し。なければディレクトリ名。"""
    md = root / "deck.md"
    if md.is_file():
        for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return root.name
