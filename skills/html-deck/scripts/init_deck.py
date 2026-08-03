#!/usr/bin/env python3
"""デッキの雛形を作る。

    python scripts/init_deck.py <出力ディレクトリ> --title "デッキ名"

作るもの:
    <dir>/deck.md        契約 (ゴール・対象・ストーリーボード) の正本
    <dir>/theme.css      共有トークン。この後デザインで値を入れ替える
    <dir>/index.html     固定1600x900 scale-only ビューア
    <dir>/slides/        ここに NN-slug.html を1枚ずつ置く
    <dir>/.loop/         検査結果とスクリーンショットの置き場 (自動生成)

theme.css と index.html は既にあれば上書きしない (--force で上書き)。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"

DECK_MD = """# {title}

<!-- この1枚が契約の正本。ここに書いていないことは全て各スライドの自由。
     逆にここに書いたことは、全スライドとレビュアがそのまま合否条件に使う。 -->

## goal
<!-- ユーザーと合意した1文。見終わった人に何を理解・判断してほしいか。
     ここが揺れると評価ループが収束しない。合意前に着工しない。 -->
TBD

## audience
TBD

## takeaway
<!-- デッキ全体の結論。最後の1枚がこれを解いていれば通る -->
TBD

## constraints
- 枚数: TBD
- 言語: 日本語
- 納品形式: HTML (+ 固定PDF)
- 禁止: 外部通信 / スクリプト / 未出典の数値
- しきい値の変更: なし   <!-- gates.json を変える場合はここに理由を書く -->

## design
<!-- 設計パスで決めた内容をここに固定する。以降のラウンドで変えない -->
- palette: TBD
- 書体: TBD
- signature: TBD  <!-- このデッキを憶えてもらう1つの装置 -->

## storyboard

| id | claim (言い切りの見出し) | job | evidence | 問い(入) → 問い(出) |
| --- | --- | --- | --- | --- |
| 01 | TBD | 宣言 | TBD | — → TBD |
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path)
    ap.add_argument("--title", default="Untitled deck")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    deck = args.dir.resolve()
    (deck / "slides").mkdir(parents=True, exist_ok=True)
    (deck / ".loop").mkdir(exist_ok=True)

    created = []

    theme = deck / "theme.css"
    if args.force or not theme.exists():
        shutil.copy(ASSETS / "theme.css", theme)
        created.append(theme)

    index = deck / "index.html"
    if args.force or not index.exists():
        html = (ASSETS / "viewer.html").read_text(encoding="utf-8").replace("__DECK_TITLE__", args.title)
        index.write_text(html, encoding="utf-8")
        created.append(index)

    md = deck / "deck.md"
    if args.force or not md.exists():
        md.write_text(DECK_MD.format(title=args.title), encoding="utf-8")
        created.append(md)

    print(f"deck: {deck}")
    for p in created:
        print(f"  + {p.relative_to(deck)}")
    if not created:
        print("  (既存のまま。上書きするなら --force)")
    print(f"\nスライドの骨格: {ASSETS / 'slide-template.html'}")
    print("次: deck.md の goal をユーザーと合意 → theme.css をデザイン → slides/NN-slug.html を実装")
    return 0


if __name__ == "__main__":
    sys.exit(main())
