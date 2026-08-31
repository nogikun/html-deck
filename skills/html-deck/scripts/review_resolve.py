#!/usr/bin/env python3
"""ユーザーの指摘を処理し終えたことを記録する。エージェント側から呼ぶ。

    python3 scripts/review_resolve.py <deck> --id fb-001 --status applied \
        --action "slides/03-evidence.html:23 の数値を6ヶ月に変更、footer に出典を追加" \
        --accepted "03: 回収期間は6ヶ月表記で確定"

やること:
  1. .loop/feedback/resolved.jsonl に1行追記する (ビューアのピンがこれを見て色を変える)
  2. --accepted があれば deck.md の ## accepted に [user] 行として積む

2 が肝心。積まないと次のラウンドで批評サブエージェントが逆方向に指摘し、
ユーザーの意思が静かに巻き戻る。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_deck_adapter as adapter  # noqa: E402

STATUSES = ("applied", "rejected", "deferred")


def load_inbox(root: Path) -> dict[str, dict]:
    path = adapter.feedback_dir(root) / "inbox.jsonl"
    out: dict[str, dict] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    out[rec["id"]] = rec
                except (json.JSONDecodeError, KeyError):
                    pass
    return out


def append_accepted(deck_md: Path, line: str) -> bool:
    """## accepted の末尾に1行足す。節が無ければ作る。"""
    if not deck_md.is_file():
        return False
    text = deck_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    entry = f"- {line}"
    if entry in lines:
        return True

    try:
        start = next(i for i, l in enumerate(lines) if l.strip().lower() == "## accepted")
    except StopIteration:
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["## accepted",
                  "<!-- 確定した判断。次のラウンドの批評担当にそのまま渡す -->",
                  entry, ""]
        deck_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    insert = end
    while insert > start + 1 and not lines[insert - 1].strip():
        insert -= 1
    lines.insert(insert, entry)
    deck_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("--id", required=True)
    ap.add_argument("--status", required=True, choices=STATUSES)
    ap.add_argument("--action", required=True, help="何をしたか / なぜ却下したかを1文で")
    ap.add_argument("--accepted", help="deck.md の ## accepted に積む1行 (applied のとき推奨)")
    args = ap.parse_args()

    root = args.deck.resolve()
    if not adapter.is_deck(root):
        print(f"error: {root} に slides/ がありません", file=sys.stderr)
        return 2

    inbox = load_inbox(root)
    if args.id not in inbox:
        print(f"error: {args.id} が inbox.jsonl にありません。"
              f"あるのは: {', '.join(inbox) or '(なし)'}", file=sys.stderr)
        return 2
    if args.status == "applied" and not args.accepted:
        print("warning: applied なのに --accepted がありません。"
              "確定した判断を積まないと、次のラウンドで批評担当に巻き戻されます。",
              file=sys.stderr)

    rec = {
        "v": 1,
        "id": args.id,
        "status": args.status,
        "round": adapter.current_round(root),
        "resolved_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "action": args.action,
    }
    if args.accepted:
        rec["accepted_line"] = f"[user] {args.accepted} ({args.id})"

    with (adapter.feedback_dir(root) / "resolved.jsonl").open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"resolved: {args.id} -> {args.status}")

    if args.accepted:
        if append_accepted(root / "deck.md", rec["accepted_line"]):
            print(f"deck.md ## accepted: {rec['accepted_line']}")
        else:
            print("warning: deck.md が見つからず accepted を積めませんでした", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
