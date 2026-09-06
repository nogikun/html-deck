#!/usr/bin/env python3
"""PPTX書き出し用のデッキ専用ランタイムを作る。uvは使わない。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


RUNTIME = ".html-deck-runtime"


def runtime_python(root: Path) -> Path:
    base = root / RUNTIME
    if sys.platform == "win32":
        return base / "Scripts" / "python.exe"
    return base / "bin" / "python"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    args = parser.parse_args()
    root = args.deck.resolve()
    if not (root / "slides").is_dir():
        print(f"slides/ がありません: {root}", file=sys.stderr)
        return 2

    python = runtime_python(root)
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(root / RUNTIME)], check=True)
    subprocess.run([
        str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
        "playwright>=1.44", "pypdf>=4.2",
    ], check=True)

    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm が見つかりません。Node.js をインストールしてください")
    subprocess.run([
        npm, "install", "--prefix", str(root), "--no-save", "--package-lock=false",
        "pptxgenjs@4.0.1",
    ], check=True)
    print(f"runtime: {root / RUNTIME}")
    print(f"node modules: {root / 'node_modules'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
