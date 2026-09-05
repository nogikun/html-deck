#!/usr/bin/env python3
"""レビュー中の検査を、契機に応じた濃さで回す薄いラッパ。

    python3 scripts/review_check.py <deck> --thread fb-003 --level brief   # 修正のたび
    python3 scripts/review_check.py <deck> --thread fb-003 --level full    # マージ前
    python3 scripts/review_check.py <deck> --level deck                    # theme を触った後

やること:
  1. check_deck.py を適切な引数で呼ぶ (brief = 該当枚のみ・スクショなし)
  2. report.json を読んで、前回そのスレッドで記録した結果との差分を出す
  3. 結果を .loop/feedback/checks/<thread>.json に置く
     (review_thread.py post が自動でスレッドに添付する)

**check_deck.py を複製しない。** 基準が2つになった時点で、緩い方を通す評価ハックの
温床になる。ここがやるのは呼び方と出力の圧縮だけ。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_deck_adapter as adapter  # noqa: E402
import review_threads as threads  # noqa: E402

HERE = Path(__file__).resolve().parent
SEV = ("block", "review", "info")


def checks_dir(root: Path) -> Path:
    d = adapter.feedback_dir(root) / "checks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slide_of(root: Path, tid: str) -> str:
    ev = threads.read(root, tid)
    if not ev:
        raise SystemExit(f"error: スレッド {tid} がない")
    sid = (ev[0].get("slide") or {}).get("id")
    if not sid:
        raise SystemExit(f"error: {tid} にスライドが記録されていない")
    return sid


def run(root: Path, *, slide: str | None, shots: bool, out: Path) -> dict:
    extra = (["--slide", slide] if slide else []) + ([] if shots else ["--no-shots"])
    proc = adapter.run_script(HERE / "check_deck.py", root, "--out", out, *extra)
    report = out / "report.json"
    if not report.is_file():
        raise SystemExit("error: check_deck.py が report.json を出さなかった\n"
                         + (proc.stderr or proc.stdout)[-1500:])
    return json.loads(report.read_text(encoding="utf-8"))


def digest(report: dict, slide: str | None) -> dict:
    """report.json を数行に畳む。スレッドに載るのはこれだけ。"""
    counts = {k: 0 for k in SEV}
    findings = []
    for s in report.get("slides", []):
        if slide and s.get("slide") != slide:
            continue
        for k in SEV:
            counts[k] += s.get("counts", {}).get(k, 0)
        for f in s.get("findings", []):
            findings.append({"severity": f.get("severity"), "code": f.get("code"),
                             "message": f.get("message"), "slide": s.get("slide")})
    if not slide:
        for f in report.get("deck_findings", []):
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
            findings.append({"severity": f.get("severity"), "code": f.get("code"),
                             "message": f.get("message"), "slide": "(デッキ全体)"})
    order = {"block": 0, "review": 1, "info": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 9))
    return {**counts, "findings": findings}


def main() -> int:
    adapter.utf8_io()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("--thread", help="スレッド id。スライドはここから引く")
    ap.add_argument("--slide", help="スライド id を直接指定する (--thread の代わり)")
    ap.add_argument("--level", choices=("brief", "full", "deck"), default="brief",
                    help="brief=該当枚・スクショなし / full=該当枚・スクショあり / deck=全枚")
    args = ap.parse_args()

    root = args.deck.resolve()
    if not adapter.is_deck(root):
        print(f"error: {root} に slides/ がありません", file=sys.stderr)
        return 2

    slide = args.slide
    if args.level != "deck":
        if not slide and args.thread:
            slide = slide_of(root, args.thread)
        if not slide:
            print("error: --thread か --slide が要ります (--level deck を除く)", file=sys.stderr)
            return 2

    out = adapter.feedback_dir(root) / "checks" / ("_run" if args.level != "deck" else "_deck")
    report = run(root, slide=slide, shots=(args.level != "brief"), out=out)
    cur = digest(report, slide)

    prev = None
    if args.thread:
        path = checks_dir(root) / f"{args.thread}.json"
        if path.is_file():
            try:
                prev = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                prev = None

    delta = {k: cur[k] - prev[k] for k in SEV} if prev else {k: 0 for k in SEV}
    rec = {
        "v": 1, "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "level": args.level, "slide": slide or "(全枚)",
        **{k: cur[k] for k in SEV},
        "delta": delta if prev else None,
        "top": cur["findings"][:3],
        "findings": cur["findings"] if args.level != "brief" else None,
        "report": str((out / "report.json").relative_to(root)),
    }
    if args.thread:
        (checks_dir(root) / f"{args.thread}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    def d(k):
        return f" ({delta[k]:+d})" if prev and delta[k] else ""
    print(f"{args.level}  {slide or '全枚'}  "
          f"block {cur['block']}{d('block')} / review {cur['review']}{d('review')} / info {cur['info']}{d('info')}")
    for f in cur["findings"][:3]:
        print(f"  {f['severity']:<6} {f['code']:<20} {f['message']}")
    if not cur["findings"]:
        print("  指摘なし")
    if args.thread:
        print(f"  記録: .loop/feedback/checks/{args.thread}.json "
              f"(review_thread.py post が自動で添付する)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
