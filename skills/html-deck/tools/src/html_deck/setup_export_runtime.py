#!/usr/bin/env python3
"""Node 側の依存 (pptxgenjs) をプロジェクトの中だけに用意する。

Python 側はここに無い — パッケージの依存として uv (uvx / uv sync) が入れる。
残っているのは Node だけで、uv の管轄外だからここで面倒を見る。

置き場所は `<プロジェクト>/.html-deck-runtime/node/`。デッキの中には作らない —
デッキは人に渡す成果物で、そこに数十MBを置かないし、1デッキごとに入れ直すのも無駄。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DIR_NAME = ".html-deck-runtime"
NODE_DEPS = ("pptxgenjs@4.0.1",)
MARKERS = (".git", ".claude", ".agents")


def project_root(deck: Path) -> Path:
    """デッキから上に辿ってプロジェクトの根を探す。無ければデッキの親。"""
    deck = deck.resolve()
    for d in (deck, *deck.parents):
        if any((d / m).exists() for m in MARKERS):
            return d
    return deck.parent


def runtime_dir(deck: Path) -> Path:
    return project_root(deck) / DIR_NAME


def node_root(deck: Path) -> Path:
    """npm --prefix の宛先。実体は <ここ>/node_modules に入る。"""
    return runtime_dir(deck) / "node"


def ensure_node(deck: Path) -> Path:
    """pptxgenjs が入った場所を返す。入っていれば何もしない (冪等)。

    ponytail: ロックは張らない。サーバ側は書き出しロックで直列化済みで、
    CLI と同時に叩くのは想定外。競合が実際に起きたらファイルロックを足す。
    """
    node = node_root(deck)
    stamp = runtime_dir(deck) / "node.txt"
    want = "\n".join(NODE_DEPS)
    if (stamp.is_file() and stamp.read_text(encoding="utf-8") == want
            and (node / "node_modules" / "pptxgenjs").is_dir()):
        return node

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm が見つかりません。Node.js を入れてください (https://nodejs.org)")
    print(f"[html-deck] pptxgenjs を用意する: {node}", file=sys.stderr, flush=True)
    node.mkdir(parents=True, exist_ok=True)
    subprocess.run([npm, "install", "--prefix", str(node), "--no-save",
                    "--package-lock=false", *NODE_DEPS], check=True)
    stamp.write_text(want, encoding="utf-8")
    return node


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    args = ap.parse_args()
    deck = args.deck.resolve()
    if not (deck / "slides").is_dir():
        print(f"slides/ がありません: {deck}", file=sys.stderr)
        return 2
    print(f"node: {ensure_node(deck) / 'node_modules'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
