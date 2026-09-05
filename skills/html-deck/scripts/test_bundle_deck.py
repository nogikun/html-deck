#!/usr/bin/env python3
"""bundle_deck.py の自己チェック。ブラウザ不要。

    python3 scripts/test_bundle_deck.py

見るのは1点だけ: **デッキの外を畳まないこと。**
バンドルは人に送る1ファイルなので、ここで拾ったものは全部その中に焼き込まれて
出ていく。`../` や絶対パスを素通しすると、そのままローカルファイルの流出になる。
デッキ内の画像がちゃんと畳まれることも、同じテストで裏取りする
(全部弾いてしまっては安全でも役に立たない)。
"""

from __future__ import annotations

import base64
import io
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bundle_deck  # noqa: E402
import init_deck  # noqa: E402

SECRET = "TOP-SECRET-DO-NOT-BUNDLE"

# 1x1 の PNG。中身が data: に入ったことを確かめるために使う。
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "0000004945"
) + b"\x4e\x44\xae\x42\x60\x82"


def build(tmp: Path) -> Path:
    outside = tmp / "outside.txt"
    outside.write_text(SECRET, encoding="utf-8")

    deck = tmp / "deck"
    sys.argv = ["init_deck.py", str(deck), "--title", "漏えい検査"]
    assert init_deck.main() == 0
    (deck / "fig.png").write_bytes(PNG)

    # デッキ内の画像 (畳まれるべき) と、外へ出る参照3種 (畳まれてはいけない)
    (deck / "slides" / "01-x.html").write_text(f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>漏えい検査</title>
<link rel="stylesheet" href="../theme.css">
<style>.a {{ background: url(../fig.png); }}
       .b {{ background: url(../../outside.txt); }}</style></head>
<body><main>
  <img src="../fig.png" alt="デッキ内">
  <img src="../../outside.txt" alt="上に抜ける">
  <img src="{(tmp / 'outside.txt').as_posix()}" alt="絶対パス">
  <img src="/etc/passwd" alt="ルート">
  <img src="https://example.com/remote.png" alt="外部サイト">
  <a href="https://example.com/">外部リンク (これは正当なので数えない)</a>
</main></body></html>
""", encoding="utf-8")
    return deck


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        deck = build(Path(tmp))
        sys.argv = ["bundle_deck.py", str(deck)]
        err, out = io.StringIO(), io.StringIO()
        with redirect_stderr(err), redirect_stdout(out):
            assert bundle_deck.main() == 0
        warn, said = err.getvalue(), out.getvalue()
        html = (deck / f"{deck.name}.html").read_text(encoding="utf-8")

    # --- デッキ外は1バイトも入っていない
    # data: に畳まれると base64 になるので、素の文字列だけ見ても気づけない。
    # 符号化したものでも照合する (最初これを忘れて、漏れているのに通ってしまった)。
    encoded = base64.b64encode(SECRET.encode()).decode()
    assert SECRET not in html, "デッキ外のファイルがそのまま焼き込まれた"
    assert encoded not in html, "デッキ外のファイルが data: として焼き込まれた"
    # 弾いた参照は書き換えずそのまま残す (黙って消すと、なぜ出ないのか追えない)
    assert "../../outside.txt" in html, "弾いた参照が消えている"

    # --- デッキ内は畳まれている
    assert "data:image/png;base64," in html, "デッキ内の画像が畳まれていない"
    assert 'src="../fig.png"' not in html, "デッキ内の画像が参照のまま残っている"
    assert "url(../fig.png)" not in html, "CSS の url() が畳まれていない"

    # --- 畳めなかった読み込み参照は警告に出し、「外部参照なし」と言い切らない
    assert "https://example.com/remote.png" in warn, warn
    assert "../../outside.txt" in warn, warn
    assert "外部参照なしの1ファイル" not in said, said
    assert "外部参照が" in said and "残っている" in said, said
    # href のリンクは数えない (外部サイトへのリンクは正当)
    assert "外部リンク" in html

    # --- 単体の判定も直接確かめる
    root = Path(tempfile.gettempdir()).resolve() / "deck"
    assert bundle_deck.local_file(root / "slides", "../../etc/passwd", root) is None
    assert bundle_deck.local_file(root / "slides", "http://x/y.png", root) is None
    assert bundle_deck.local_file(root / "slides", "data:image/png;base64,AA", root) is None
    print("ok: バンドルはデッキの外を畳まない (デッキ内は畳む)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
