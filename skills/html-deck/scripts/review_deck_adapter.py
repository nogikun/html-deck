#!/usr/bin/env python3
"""レビュー機構のうち、html-deck 固有の知識をここに閉じ込める。

汎用スキルとして切り出すときは、このファイルと references/review.md だけを
差し替えれば済む状態を保つこと。review_server.py と review_anchor.py は
「ディレクトリを配信して、DOM の位置をソース行に解決する」以上のことを知らない。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def utf8_io() -> None:
    """自分の標準出力を UTF-8 に固定する。

    このスキルのスクリプトは日本語しか出さないのに、Windows の既定は cp932。
    パイプに繋ぐとロケール依存になり、ダッシュや一部の記号で
    UnicodeEncodeError で落ちる。出す側で決めておけばロケールに左右されない。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass          # 差し替えられたストリームなら諦める (出力の問題でしかない)


def runtime_python(root: Path | None) -> Path | None:
    """Return the deck-local Python, if its runtime has been provisioned."""
    if root is None:
        return None
    runtime = root / ".html-deck-runtime"
    candidates = (
        runtime / "Scripts" / "python.exe",
        runtime / "bin" / "python",
    )
    return next((path for path in candidates if path.is_file()), None)


def script_cmd(script: Path, root: Path | None = None) -> list[str]:
    """Run deck scripts with the deck-local runtime; never route through uv."""
    python = runtime_python(root) or Path(sys.executable)
    return [str(python), str(script)]


def run_script(script: Path, *args: str, timeout: float | None = None):
    """同梱スクリプトを起動して結果を返す。**文字コードは UTF-8 に固定する。**

    `text=True` だけだとロケールで復号する。Windows の cp932 で子の UTF-8 出力を
    読むと UnicodeDecodeError で落ちる (実際に落ちた)。日本語を出すスクリプトしか
    無いので、親子ともロケールに任せない。復号エラーは replace で潰す —
    ここで欲しいのは呼び出し側へ見せるログであって、1文字の正確さではない。
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    root = Path(args[0]) if args and (Path(args[0]) / "slides").is_dir() else None
    return subprocess.run(script_cmd(script, root) + [str(a) for a in args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=env, timeout=timeout)


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
