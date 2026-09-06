#!/usr/bin/env python3
"""export_pptx.py のOS依存起動処理を確認する。ブラウザ不要。"""

from __future__ import annotations

import sys
from contextlib import ExitStack
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import export_pptx  # noqa: E402
import review_deck_adapter as adapter  # noqa: E402


def test_node_path() -> None:
    assert Path(export_pptx.resolve_node(sys.executable)).is_file()


def test_uv_cache_retry() -> None:
    script = HERE / "export_pptx.py"
    cmd = ["/fake/uv", "run", "script"]
    first = CompletedProcess(cmd, 1, "", "failed to open /x/.cache/uv/sdists-v9/.git: Operation not permitted")
    second = CompletedProcess(cmd, 0, "ok", "")
    with ExitStack() as stack:
        stack.enter_context(patch.object(adapter, "script_cmd", return_value=cmd))
        stack.enter_context(patch.object(adapter, "_uv_cache_dir", return_value=Path("/bad/cache")))
        stack.enter_context(patch.object(adapter, "_writable_dir", return_value=True))
        run = stack.enter_context(patch.object(adapter.subprocess, "run", side_effect=[first, second]))
        result = adapter.run_script(script)
    assert result is second
    assert run.call_count == 2


if __name__ == "__main__":
    test_node_path()
    test_uv_cache_retry()
    print("export_pptx self-check: ok")
