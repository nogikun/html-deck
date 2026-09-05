#!/usr/bin/env python3
"""レビュー経路の自己チェック。ブラウザも HTTP も要らない部分だけを通す。

    python3 scripts/test_review_flow.py

見るのは「スレッドが唯一の正本になっているか」。起票・返信・提案・マージを
順に通し、状態遷移・ガード・deck.md への積み上げを確かめる。
検査 (check_deck.py) は Playwright が要るので、ここでは結果を差し込んで代用する。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import init_deck  # noqa: E402
import review_server as server  # noqa: E402
import review_threads as T  # noqa: E402

SLIDE = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>回収期間</title></head><body><main><h1>回収は3ヶ月</h1>
<p class="body">初期費用は6週間で回収できる見込み。</p></main></body></html>
"""


def make_deck(root: Path) -> None:
    sys.argv = ["init_deck.py", str(root), "--title", "テストデッキ"]
    assert init_deck.main() == 0
    (root / "slides" / "03-evidence.html").write_text(SLIDE, encoding="utf-8")


def check(root: Path) -> None:
    # --- ビューアは共通の殻を埋め込んだ状態で置かれる (印が残っていたら未展開)
    index = (root / "index.html").read_text(encoding="utf-8")
    assert "__SHELL__" not in index, "shell.css が展開されていない"
    assert "--brand:" in index and ".toolbar" in index, "共通CSSが入っていない"
    assert "__DECK_TITLE__" not in index

    # --- 起票。id はスレッドの本数から採る
    item = server.create_feedback(root, {
        "slide_id": "03-evidence", "slide_file": "slides/03-evidence.html",
        "slide_title": "回収期間", "instruction": "#1 の数値を6ヶ月に直して",
        "refs": [{"n": 1, "kind": "element", "tag": "h1", "path": [1, 0, 0],
                  "text_excerpt": "回収は3ヶ月"}],
    })
    assert item["id"] == "fb-001", item["id"]
    assert server.create_feedback(root, {
        "slide_id": "03-evidence", "slide_file": "slides/03-evidence.html",
        "instruction": "本文が小さい", "refs": [],
    })["id"] == "fb-002"

    # 参照はソース行まで解決されて起票イベントに載る
    ref = T.read(root, "fb-001")[0]["refs"][0]
    assert ref["file_line"] and ref["anchor_confidence"] in ("exact", "text"), ref
    assert T.state_of(T.read(root, "fb-001")) == "open"

    # --- 並行ストアを作らない (ここが今回の主眼)
    fdir = root / ".loop" / "feedback"
    for gone in ("inbox.jsonl", "resolved.jsonl"):
        assert not (fdir / gone).exists(), f"{gone} を作ってはいけない"

    # --- 未読はユーザー発言のぶんだけ。返事を書けば消える
    assert {u["id"] for u in T.unread(root)} == {"fb-001", "fb-002"}
    T.post(root, "fb-001", role="ai", text="6ヶ月に直した", state="proposed",
           changes=[{"file": "slides/03-evidence.html", "line": 3, "note": "3ヶ月 → 6ヶ月"}])
    assert {u["id"] for u in T.unread(root)} == {"fb-002"}

    # --- ユーザーの返信は差し戻しになる
    server.create_reply(root, {"id": "fb-001", "text": "出典も足して"})
    assert T.state_of(T.read(root, "fb-001")) == "changes_requested"
    assert {u["id"] for u in T.unread(root)} == {"fb-001", "fb-002"}

    # --- エージェントは merged にできない
    try:
        T.post(root, "fb-001", role="ai", text="確定", state="merged")
        raise AssertionError("エージェントが merged にできてしまった")
    except T.ThreadError:
        pass

    # --- proposed でなければマージできない
    try:
        T.merge(root, "fb-001", intent="回収は6ヶ月表記")
        raise AssertionError("changes_requested のままマージできてしまった")
    except T.ThreadError:
        pass

    T.post(root, "fb-001", role="ai", text="出典を footer に足した", state="proposed")

    # --- block が残っているマージは止まる
    try:
        T.merge(root, "fb-001", intent="回収は6ヶ月表記", check={"block": 2})
        raise AssertionError("block が残ったままマージできてしまった")
    except T.ThreadError:
        pass

    # --- マージ = 確定。merged.jsonl と deck.md の ## accepted に積まれる
    T.merge(root, "fb-001", intent="回収期間は6ヶ月表記で確定", check={"block": 0})
    assert T.state_of(T.read(root, "fb-001")) == "merged"
    merged = T.merged(root)
    assert len(merged) == 1 and merged[0]["slide"] == "03-evidence"
    accepted = (root / "deck.md").read_text(encoding="utf-8")
    assert "- [user] 03-evidence: 回収期間は6ヶ月表記で確定 (fb-001)" in accepted
    # ## accepted の節の中に入っている (次の節へこぼれていない)
    body = accepted.split("## accepted")[1].split("## storyboard")[0]
    assert "[user]" in body, body

    # --- 確定後に動かせるのは note だけ
    try:
        T.post(root, "fb-001", role="ai", text="やっぱり直す", state="in_progress")
        raise AssertionError("merged のスレッドを開き直せてしまった")
    except T.ThreadError:
        pass
    T.note(root, "fb-001", "theme の本文を22→24pxにした")
    assert T.state_of(T.read(root, "fb-001")) == "merged"

    # --- エスカレーションの集約。同じ key が基準に達したら1回の裁定で全部に返る
    T.escalate(root, "fb-002", key="body_font_small", slide="03-evidence",
               ask="本文22pxだと1行溢れる")
    assert T.state_of(T.read(root, "fb-002")) == "waiting_main"
    out = T.decide(root, "body_font_small", status="applied_by_main", note="本文を24pxにした")
    assert len(out) == 1
    assert T.state_of(T.read(root, "fb-002")) == "in_progress"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "deck"
        make_deck(root)
        check(root)
    print("ok: レビュー経路 (起票 → 返信 → 提案 → マージ → 確定後) は通っている")
    return 0


if __name__ == "__main__":
    sys.exit(main())
