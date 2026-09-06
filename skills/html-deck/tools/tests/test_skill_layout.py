#!/usr/bin/env python3
"""スキルの構成が壊れていないかを検査する。ブラウザ不要。

置き場所を動かしたり、コマンド名を変えたりすると、SKILL.md や references/ の
記述だけが古いまま残る。それは実行するまで気づけないし、実行するのはエージェントで、
古いパスを渡されたエージェントは自力で回避策を編み出してしまう (それが一番まずい)。
ここで機械的に突き合わせる。
"""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent.parent
TOOLS = SKILL / "tools"
PKG = TOOLS / "src/html_deck"
# vendor/ は上流のコピー。こちらの都合でパスを書き換えない。
# tools/.venv は uv が入れた他人のパッケージ (playwright は自前の SKILL.md を同梱している)。
_SKIP = ("vendor/draw-io", "/.venv/")
DOCS = [p for p in SKILL.rglob("*.md")
        if not any(s in p.as_posix() for s in _SKIP)]
# ユーザーがコピーして実行する文面は、散文と同じだけ古びる。review.html の
# 生成コマンドが `python3 scripts/review_server.py` を指したまま残っていて、
# それでもこのテストは ok だった (散文と .py しか見ていなかった)。
SHIPPED = (sorted(PKG.glob("*.py")) + sorted((PKG / "assets").glob("*.html"))
           + sorted(PKG.glob("*.mjs")))


def _scripts() -> dict[str, str]:
    return tomllib.loads((TOOLS / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]


def test_frontmatter() -> None:
    m = re.match(r"^---\n(.*?)\n---\n", (SKILL / "SKILL.md").read_text(encoding="utf-8"), re.S)
    assert m, "SKILL.md に frontmatter が無い"
    for key in ("name", "description"):
        assert re.search(rf"^{key}:", m.group(1), re.M), f"frontmatter に {key} が無い"


def test_commands_resolve() -> None:
    """宣言したコマンドが実在するモジュールの main() に解決できること。"""
    for cmd, target in _scripts().items():
        mod, func = target.split(":")
        assert callable(getattr(importlib.import_module(mod), func, None)), f"{cmd} → {target} が無い"


def test_docs_use_only_declared_commands() -> None:
    """文書が宣言外のコマンドを書いていないこと (打っても動かない)。

    `.html-deck-runtime` はディレクトリ名なので、直前が . や英小文字なら拾わない。
    """
    declared = set(_scripts())
    used: set[str] = set()
    for md in DOCS:
        used |= set(re.findall(r"(?<![.a-z-])html-deck-[a-z]+\b", md.read_text(encoding="utf-8")))
    assert not (used - declared), f"宣言されていないコマンド: {sorted(used - declared)}"


def test_docs_paths_exist() -> None:
    """文書が指すスキル内のパスが実在すること。"""
    pat = re.compile(r'(?:tools/|references/|agents/|evals/|vendor/)[A-Za-z0-9_./-]+')
    missing = []
    for md in DOCS:
        for ref in pat.findall(md.read_text(encoding="utf-8")):
            ref = ref.rstrip(".,)`")
            if not ref.endswith("/") and not (SKILL / ref).exists():
                missing.append(f"{ref} ({md.relative_to(SKILL)})")
    assert not missing, "存在しない参照: " + ", ".join(sorted(set(missing)))


def test_no_stale_script_paths() -> None:
    """`scripts/` はもう無い。docstring (= --help の本文) にも文書にも残さない。

    ここを見ていなかったせいで、移設後も 13 モジュール全部の --help が
    `python3 scripts/xxx.py` を案内していた。エージェントはその案内を信じて
    存在しないパスを叩き、自力で回避策を編み出す。それが一番まずい壊れ方。
    """
    bad = [f"{f.relative_to(SKILL)}:{i}" for f in SHIPPED + DOCS
           for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if "scripts/" in line]
    assert not bad, "存在しない scripts/ への言及: " + ", ".join(bad)


def test_no_bare_interpreter_commands() -> None:
    """`python3 <なにか>.py` を実行例として書かないこと。

    デッキの依存は tools/pyproject.toml にしか無い。素の `python3` は pyenv の
    shim や別のバージョンに当たり、`ModuleNotFoundError: pypdf` で落ちる
    (実際に落ちた)。呼び口は `uv run --project <tools> html-deck-<cmd>` だけ。
    shebang は実行例ではないので拾わない。
    """
    pat = re.compile(r"python3?\s+[\w./-]+\.py")
    bad = [f"{f.relative_to(SKILL)}:{i}" for f in SHIPPED + DOCS
           for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if pat.search(line) and not line.lstrip().startswith("#!")]
    assert not bad, "インタプリタ直呼びの実行例: " + ", ".join(bad)


def test_generated_commands_are_declared() -> None:
    """ユーザーがコピーする文面が、実在するコマンドを呼んでいること。

    review.html の「サーバを起動して」プロンプトが `scripts/` を指したまま
    残っていて、コピーして実行しても何も起きなかった。散文だけ直しても、
    ユーザーの手元に届くのはこの文面のほう。
    """
    declared = set(_scripts())
    for f in SHIPPED:
        # 末尾の `-` まで見る。`html-deck-export-` は tempdir の接頭辞であってコマンドではない
        used = set(re.findall(r"(?<![.a-z-])html-deck-[a-z]+(?![\w-])", f.read_text(encoding="utf-8")))
        assert not (used - declared), f"{f.relative_to(SKILL)}: 宣言されていないコマンド {sorted(used - declared)}"
    review = (PKG / "assets/review.html").read_text(encoding="utf-8")
    assert "uv run --project" in review and "html-deck-review" in review and "--open" in review, \
        "review.html の起動コマンドが uv run --project … html-deck-review … --open ではない"


def test_docs_do_not_name_modules_as_commands() -> None:
    """散文が裸の `xxx.py` を実行コマンドとして書いていないこと。

    同梱物表がパスとして書くのは正しいので、パス接頭辞付きは見逃す。
    裸で出てくるものは、サブエージェントに貼るプロンプトの中にあると
    そのまま実行されて失敗する。
    """
    mods = {p.stem for p in PKG.glob("*.py")} | {"review_deck_adapter"}
    bad = []
    for md in DOCS:
        for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for m in mods:
                for hit in re.finditer(rf"(?<![/\w]){m}\.py", line):
                    bad.append(f"{md.relative_to(SKILL)}:{i} {m}.py")
    assert not bad, "コマンドではなくモジュール名で書かれている: " + ", ".join(sorted(set(bad)))


def test_assets_shipped_with_code() -> None:
    """コードが読む材料がパッケージの中にあること (uv のキャッシュから走るため)。"""
    for name in ("gates.json", "review.html", "shell.css", "theme.css"):
        assert (TOOLS / "src/html_deck/assets" / name).is_file(), name
    assert (TOOLS / "src/html_deck/emit_pptx.mjs").is_file()
    # 骨格はコードが一度も読まない (init_deck は場所を案内するだけ)。
    # モデルが開くものなので散文の側に置く — ホイールに入れる理由がない。
    assert (SKILL / "assets/slide-template.html").is_file()
    assert not (TOOLS / "src/html_deck/assets/slide-template.html").exists()


if __name__ == "__main__":
    for fn in (test_frontmatter, test_commands_resolve, test_docs_use_only_declared_commands,
               test_docs_paths_exist, test_no_stale_script_paths,
               test_no_bare_interpreter_commands, test_generated_commands_are_declared,
               test_docs_do_not_name_modules_as_commands, test_assets_shipped_with_code):
        fn()
    print("skill layout self-check: ok")
