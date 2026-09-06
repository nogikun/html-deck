#!/usr/bin/env python3
"""ユーザーの発言が現れるまで待ち、現れたら中身を出して終了する。

    uvx --from <このスキルのディレクトリ>/tools html-deck-wait <deck> [--timeout 1800]

なぜ要るか:
  review_server.py は止めるまで動き続けるので、「ユーザーが何か言った」という
  出来事を知らせる終端がない。このスクリプトは**発言が届いた時点で終了する**ので、
  エージェントはこれをバックグラウンドで走らせておくだけで気づける。

拾うもの (どれもユーザー発)。エージェントがまだ返事をしていないものだけ:
  新規の起票 / スレッドへの返信 / 差し戻し / マージ / 取り下げ

  返事 (review_thread.py post) を書いた時点でそのスレッドは読んだ扱いになる。
  マージはエージェントの作業を要さないが、**報告のために**通知する。

挙動:
  起動時にすでに未読があれば、待たずにそれを出して終了する。無ければ現れるまで待つ。
  タイムアウトしても異常終了はしない (待ちが空振りしただけなので)。

出力: JSON を1つ。 {"waited_sec": .., "timeout": false, "threads": [...]}
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import review_deck_adapter as adapter  # noqa: E402
from . import review_threads as threads  # noqa: E402


def main() -> int:
    adapter.utf8_io()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("--timeout", type=float, default=1800, help="秒。既定30分")
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()

    root = args.deck.resolve()
    if not adapter.is_deck(root):
        print(f"error: {root} に slides/ がありません", file=sys.stderr)
        return 2

    start = time.monotonic()
    while True:
        items = threads.unread(root)
        if items:
            print(json.dumps({
                "waited_sec": round(time.monotonic() - start, 1),
                "timeout": False,
                "count": len(items),
                "threads": items,
                "note": "1スレッド = 1サブエージェント。context は "
                        "`review_thread.py <deck> context <id>` で取る。"
                        "他のスレッドは読まない。",
            }, ensure_ascii=False, indent=2))
            return 0
        if time.monotonic() - start >= args.timeout:
            print(json.dumps({
                "waited_sec": round(time.monotonic() - start, 1),
                "timeout": True, "count": 0, "threads": [],
                "note": "指摘は届かなかった。ユーザーがまだ見ている可能性がある。"
                        "再度待つならこのスクリプトをもう一度走らせる。",
            }, ensure_ascii=False, indent=2))
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
