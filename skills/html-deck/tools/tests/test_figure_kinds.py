#!/usr/bin/env python3
"""図の判定の自己チェック。ブラウザ不要。

SVG でもラスタでもない図 (divとCSSで組んだ比較表・流れ図) を
`data-space-role="figure"` で明示したとき、それが「図のある枚」として
数えられること。ここが抜けると、検査を通すためだけの飾りSVGを足す方向へ動く。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from html_deck.check_deck import DEFAULT_GATES, evaluate

GATES = json.loads(DEFAULT_GATES.read_text(encoding="utf-8"))
W = GATES["canvas"]["width"]
H = GATES["canvas"]["height"]
JA = "図" * (GATES["text_only_ja_chars"] + 10)


def data(figures):
    return {
        "title": "fixture", "headings": [{"tag": "h2", "text": "fixture"}],
        "scroll": {"w": W, "h": H}, "elements": [], "colorUse": [],
        "families": [], "overlaps": [], "figures": figures, "spaceItems": [],
        "layoutRegions": [], "spaceProfile": "", "bullets": 0, "bulletTexts": [],
        "textArea": 0, "allText": JA,
    }


def codes(figures):
    report = evaluate(data(figures), GATES, "<!doctype html>", "fixture")
    return {f["code"] for f in report["findings"]}, report


def main() -> int:
    # 図が無ければ text_only が出る (この検査自体が生きていることの確認)
    assert "text_only" in codes([])[0]

    # data-space-role="figure" を付けた非SVGの塊は「図」に数える
    side = (GATES["figure_min_area_ratio"] * W * H) ** 0.5 + 10
    block = {"kind": "block", "sel": ".flow", "w": side, "h": side,
             "named": True, "hidden": False}
    found, report = codes([block])
    assert "text_only" not in found, found
    # img 用の検査 (naturalW など) に落ちて KeyError にならない
    assert "image_not_loaded" not in found and "image_low_res" not in found

    # 小さすぎるものは飾り扱いのまま。1つ置けば通る、にはしない
    tiny = {**block, "w": 40, "h": 40}
    assert "text_only" in codes([tiny])[0]

    print("ok: 非SVGの図を data-space-role=\"figure\" で図として数える")
    print("ok: 小さすぎる塊は図に数えない / img 用検査に落ちない")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
