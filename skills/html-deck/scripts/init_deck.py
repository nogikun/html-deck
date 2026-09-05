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
import re
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"

SHELL_MARK = "/* __SHELL__ */"


def viewer_html(title: str) -> str:
    """配置するビューア。共通の殻 (shell.css) を埋め込んで1ファイルにする。

    review_server.py が配信するのと同じ review.html を置く。file:// では
    レビュー機能が自分で畳まれて、ただのビューアとして動く。
    ビューアを2本持つと、同じ操作を2回書いて片方だけ直す事故が起きる。
    """
    html = (ASSETS / "review.html").read_text(encoding="utf-8")
    shell = (ASSETS / "shell.css").read_text(encoding="utf-8")
    return html.replace(SHELL_MARK, shell).replace("__DECK_TITLE__", title)

DECK_MD = """# {title}

<!-- この1枚が契約の正本。ここに書いていないことは全て各スライドの自由。
     逆にここに書いたことは、全スライドとレビュアがそのまま合否条件に使う。 -->

## goal
<!-- ユーザーと合意した1文。見終わった人に何を理解・判断してほしいか。
     ここが揺れると評価ループが収束しない。合意前に着工しない。 -->
TBD

## audience
<!-- 誰に向けるか。何を決められる人か。前提をどこから説明するかがここで決まる -->
TBD

## situation
<!-- 手順1のインタビューで聞いた「どう見せる資料か」。1枚の情報量の予算がここで決まる。
     話しながら見せる = 1枚300字 / 置いて読ませる = 420〜520字 / 両方 = 300字 + 話す内容は別持ち -->
- 場面: TBD   <!-- 話しながら / 置いて読ませる / 両方 -->
- 持ち時間: TBD
- 1枚の字数の上限: TBD   <!-- gates.json の max_ja_chars と合わせる -->

## takeaway
<!-- デッキ全体の結論。最後の1枚がこれを解いていれば通る -->
TBD

## constraints
- 枚数: TBD
- 言語: 日本語
- 納品形式: HTML (+ 固定PDF)
- 禁止: 外部通信 / スクリプト / 未出典の数値
- しきい値の変更: なし   <!-- gates.json を変える場合はここに理由を書く。
                            場面に応じた max_ja_chars の変更もここに書く。ラウンド0で1度だけ -->

## design
<!-- 設計パスで決めた内容をここに固定する。以降のラウンドで変えない -->
- palette: TBD
- 書体: TBD
- signature: TBD  <!-- このデッキを憶えてもらう1つの装置 -->

## accepted
<!-- 確定した判断を1行ずつ積む。次のラウンドの批評担当にそのまま渡す。
     渡さないと同じ場所を逆方向に指摘され続けて往復する。
     ユーザーのレビュー由来のものは、ユーザーがマージした時点で [user] 付きで積まれる。 -->

## storyboard

<!-- visual = その枚を何の絵で見せるか。「なし」と書いた行が3つ以上続いたら、
     通しで見たとき文字の壁になる (check_deck.py の text_only_streak)。
     デッキ全体で図のある枚を4割以上にする。 -->

| id | claim (言い切りの見出し) | job | visual | evidence | 問い(入) → 問い(出) |
| --- | --- | --- | --- | --- | --- |
| 01 | TBD | 宣言 | なし | TBD | — → TBD |
"""


SLIDES_RE = re.compile(r"// <slides>.*?// </slides>", re.S)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def refresh_viewer(deck: Path) -> int:
    """index.html を今のビューアに入れ替える。中身 (スライド一覧・タイトル) は引き継ぐ。

    ビューアの見た目を直したときに、既存のデッキが古いままになるのを防ぐ。
    theme.css には触らない — あれはデッキごとのデザインで、テンプレートに戻したら壊れる。
    """
    index = deck / "index.html"
    if not index.is_file():
        print(f"error: {index} がありません", file=sys.stderr)
        return 2

    old = index.read_text(encoding="utf-8")
    m = TITLE_RE.search(old)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else deck.name
    keep = SLIDES_RE.search(old)

    html = viewer_html(title)
    if keep:
        html = SLIDES_RE.sub(lambda _: keep.group(0), html)
    else:
        print("warning: 元の index.html にスライド一覧の印が無かった。"
              "check_deck.py を1回流して再生成すること", file=sys.stderr)
    index.write_text(html, encoding="utf-8")
    print(f"index.html を入れ替えた: {index}")
    print("  タイトルとスライド一覧は引き継いだ。theme.css と slides/ は触っていない。")
    return 0


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
    ap.add_argument("dir", type=Path)
    ap.add_argument("--title", default="Untitled deck")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--refresh-viewer", action="store_true",
                    help="既存デッキの index.html だけを今のビューアに入れ替える "
                         "(theme.css / deck.md / slides は触らない。スライド一覧は引き継ぐ)")
    args = ap.parse_args()

    deck = args.dir.resolve()
    if args.refresh_viewer:
        return refresh_viewer(deck)

    (deck / "slides").mkdir(parents=True, exist_ok=True)
    (deck / ".loop").mkdir(exist_ok=True)

    created = []

    theme = deck / "theme.css"
    if args.force or not theme.exists():
        shutil.copy(ASSETS / "theme.css", theme)
        created.append(theme)

    index = deck / "index.html"
    if args.force or not index.exists():
        index.write_text(viewer_html(args.title), encoding="utf-8")
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
