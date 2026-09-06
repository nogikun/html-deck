#!/usr/bin/env python3
"""export_pptx.py のOS依存起動処理を確認する。ブラウザ不要。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

from html_deck import export_pptx  # noqa: E402
from html_deck import review_deck_adapter as adapter  # noqa: E402
from html_deck import review_server  # noqa: E402
from html_deck import setup_export_runtime as setup  # noqa: E402


def test_node_path() -> None:
    assert Path(export_pptx.resolve_node(sys.executable)).is_file()


def test_project_runtime() -> None:
    """Node の置き場所はデッキの外・プロジェクト直下。"""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp).resolve()
        (project / ".git").mkdir()
        deck = project / "work" / "sample-deck"
        (deck / "slides").mkdir(parents=True)
        runtime = project / ".html-deck-runtime"

        assert setup.project_root(deck) == project
        assert setup.runtime_dir(deck) == runtime
        assert setup.node_root(deck) == runtime / "node"
        # デッキは成果物。node_modules をここには置かない
        assert not setup.node_root(deck).is_relative_to(deck)

        # 子プロセスは同じ環境の python -m で叩く (ランタイム探索はもう無い)
        assert adapter.script_cmd("export_pptx") == [sys.executable, "-m", "html_deck.export_pptx"]


def test_export_lock() -> None:
    assert review_server._export_lock.acquire(blocking=False)
    try:
        result = review_server.run_export(Path("/tmp/does-not-matter"), "export_pptx.py")
        assert not result["ok"] and "実行中" in result["error"]
    finally:
        review_server._export_lock.release()


if __name__ == "__main__":
    test_node_path()
    test_project_runtime()
    test_export_lock()
    print("export_pptx self-check: ok")
