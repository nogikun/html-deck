#!/usr/bin/env python3
"""export_pdf.py のフォント照合の自己チェック。ブラウザ不要。

    python3 scripts/test_export_pdf.py

見るのは2つだけ: theme.css から第一候補を取り出せるか、CSS の家族名と
OS の家族名の綴りの揺れを吸収できるか。ここが壊れると、書体が置換された
PDF を「固定済み」として納品してしまう。
"""

from __future__ import annotations

import sys
from pathlib import Path

from html_deck.export_pdf import declared_faces, used  # noqa: E402

CSS = """
:root {
  --display: "BIZ UDPGothic", "Yu Gothic Medium", system-ui, sans-serif;
  --body:    'Yu Gothic', "YuGothic", system-ui, sans-serif;
  --mono:    Consolas, "SFMono-Regular", monospace;
  --ink: #101418;
}
h1 { font-family: var(--display); }
"""


def main() -> int:
    f = declared_faces(CSS)
    # 第一候補だけを取る。引用符の種類は問わない。裸の家族名も拾う。
    assert f == {"display": "BIZ UDPGothic", "body": "Yu Gothic", "mono": "Consolas"}, f
    # 色トークンを書体と間違えない
    assert "ink" not in f

    # 実使用フォントとの突き合わせ
    assert used("BIZ UDPGothic", {"BIZ UDPGothic", "Segoe UI"})
    assert used("Yu Gothic Medium", {"Yu Gothic"})      # OS 側が短い綴りで返す
    assert used("Yu Gothic", {"YuGothic"})              # 空白の有無を吸収
    assert not used("BIZ UDPGothic", {"Yu Gothic", "Meiryo"})   # 置換された
    assert not used("Consolas", set())                  # 何も取れなかった

    # 書体が1つも取れない theme.css でも落ちない
    assert declared_faces("") == {}
    print("ok: フォント照合 (第一候補の抽出 / 綴り揺れの吸収 / 置換の検出)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
