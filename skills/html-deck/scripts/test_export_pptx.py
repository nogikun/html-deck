#!/usr/bin/env python3
"""export_pptx.py のOS依存起動処理を確認する。ブラウザ不要。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import export_pptx  # noqa: E402
import review_deck_adapter as adapter  # noqa: E402


def test_node_path() -> None:
    assert Path(export_pptx.resolve_node(sys.executable)).is_file()


def test_deck_runtime() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "slides").mkdir()
        runtime = root / ".html-deck-runtime" / ("Scripts" if sys.platform == "win32" else "bin")
        runtime.mkdir(parents=True)
        executable = runtime / ("python.exe" if sys.platform == "win32" else "python")
        executable.write_bytes(b"")
        command = adapter.script_cmd(HERE / "export_pptx.py", root)
        assert command[0] == str(executable)
        assert "uv" not in command


if __name__ == "__main__":
    test_node_path()
    test_deck_runtime()
    print("export_pptx self-check: ok")
