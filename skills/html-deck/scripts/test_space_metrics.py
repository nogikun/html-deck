#!/usr/bin/env python3
"""余白計測の自己チェック。ブラウザ不要。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from check_deck import evaluate, _layout_geometry, _space_metrics, _union_area  # noqa: E402


LAYOUT_GATES = {
    "layout_overlap_area_min_px": 64,
    "layout_overlap_share_block": 0.02,
    "layout_center_tolerance_px": 16,
    "layout_child_shift_tolerance_px": 16,
    "connector_track_max_px": 96,
    "connector_track_max_ratio": 0.12,
    "redundant_gap_min_px": 12,
}


def region(children, *, box=(0, 0, 100, 40), frame="composition", gap_x=0,
           table_like=False):
    x, y, w, h = box
    return {
        "sel": ".composition", "box": {"x": x, "y": y, "w": w, "h": h},
        "inner": {"x": x, "y": y, "w": w, "h": h},
        "frame": frame, "tableLike": table_like, "direction": "row",
        "align": "", "intent": "", "gapX": gap_x, "gapY": 0,
        "children": children,
    }


def child(sel, x, y, w, h, *, connector=False, margin=None):
    return {
        "sel": sel, "box": {"x": x, "y": y, "w": w, "h": h},
        "connector": connector, "intent": "", "margin": margin or {},
    }


def main() -> int:
    assert _union_area([(0, 0, 10, 10), (5, 5, 15, 15)]) == 175

    data = {
        "spaceProfile": "oral",
        "spaceItems": [
            {
                "kind": "text", "sel": "h1", "x": 10, "y": 10, "w": 30, "h": 10,
                "role": "primary", "group": "left", "intent": "", "inFigure": False,
                "semantic": True, "fontSize": 32, "fg": {"r": 0, "g": 0, "b": 0, "a": 1},
                "bg": {"r": 255, "g": 255, "b": 255, "a": 1},
            },
            {
                "kind": "text", "sel": "p", "x": 10, "y": 40, "w": 30, "h": 20,
                "role": "body", "group": "left", "intent": "", "inFigure": False,
                "semantic": True, "fontSize": 20, "fg": {"r": 0, "g": 0, "b": 0, "a": 1},
                "bg": {"r": 255, "g": 255, "b": 255, "a": 1},
            },
            {
                "kind": "figure", "sel": "svg", "x": 60, "y": 10, "w": 30, "h": 50,
                "role": "figure", "group": "right", "intent": "", "inFigure": False,
                "semantic": True,
            },
        ],
    }
    metrics = _space_metrics(
        data, 100, 100,
        {"void_grid_cols": 10, "void_grid_rows": 10, "group_gap_ratio_min": 1.5},
    )
    assert round(metrics["occupied_ratio"], 2) == 0.24
    assert metrics["outer_margin_min_px"] == 10
    assert metrics["group_count"] == 2
    assert round(metrics["group_separation_ratio"], 2) == 1.0
    assert metrics["largest_void_ratio"] > 0.30
    assert metrics["profile"] == "oral"

    overlap = _layout_geometry(
        {"layoutRegions": [region([
            child(".a", 0, 0, 60, 20), child(".b", 50, 0, 50, 20),
        ])]},
        100, 100, LAYOUT_GATES,
    )
    assert len(overlap["overlaps"]) == 1

    off_center = _layout_geometry(
        {"layoutRegions": [region([
            child("tr:nth-child(1)", 0, 0, 60, 10),
            child("tr:nth-child(2)", 0, 10, 60, 10),
        ], box=(0, 0, 60, 20), frame="table", table_like=True)]},
        100, 100, LAYOUT_GATES,
    )
    assert len(off_center["off_center"]) == 1

    child_shift = _layout_geometry(
        {"layoutRegions": [region([
            child(".left", 0, 0, 30, 20), child(".right", 30, 0, 30, 20),
        ])]},
        100, 100, LAYOUT_GATES,
    )
    assert len(child_shift["child_shifts"]) == 1

    wide_connector = _layout_geometry(
        {"layoutRegions": [region([
            child(".left", 0, 0, 30, 20),
            child(".arrow", 30, 0, 20, 20, connector=True),
            child(".right", 50, 0, 30, 20),
        ])]},
        100, 100, LAYOUT_GATES,
    )
    assert len(wide_connector["wide_connectors"]) == 1

    duplicate_gap = _layout_geometry(
        {"layoutRegions": [region([
            child(".a", 0, 0, 40, 20, margin={"right": 12}),
            child(".b", 60, 0, 40, 20, margin={"left": 12}),
        ], gap_x=20)]},
        100, 100, LAYOUT_GATES,
    )
    assert len(duplicate_gap["redundant_gaps"]) == 1

    gates = json.loads((HERE.parent / "assets" / "gates.json").read_text(encoding="utf-8"))
    report = evaluate(
        {
            "title": "fixture", "headings": [{"tag": "h2", "text": "fixture"}],
            "scroll": {"w": 100, "h": 100}, "elements": [], "colorUse": [],
            "families": [], "overlaps": [], "figures": [], "spaceItems": [],
            "layoutRegions": [{
                **region([
                    child(".left", 0, 0, 30, 20),
                    child(".arrow", 30, 0, 20, 20, connector=True),
                    child(".right", 50, 0, 30, 20),
                ]),
            }],
            "spaceProfile": "", "bullets": 0, "bulletTexts": [],
            "textArea": 0, "allText": "",
        },
        gates, "<!doctype html>", "fixture",
    )
    assert report["metrics"]["layout"]["wide_connector_count"] == 1
    assert any(f["code"] == "connector_track_wide" for f in report["findings"])

    print("ok: 余白のunion・群化比・最大空白を計測できる")
    print("ok: 重なり・中央寄せ・子群の片寄り・コネクタ幅・gap二重所有を検出できる")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
