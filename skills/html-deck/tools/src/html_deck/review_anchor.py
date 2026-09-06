#!/usr/bin/env python3
"""DOM の子要素インデックス列を HTML ソースの行番号に解決する。

ブラウザ側は各階層の childElementIndex を並べた path を送ってくる。
    <html><body><article><main><ul><li>B  ->  [1, 0, 0, 1, 1]
ここではソースを html.parser で走査し、同じ規則で path を振り直して突き合わせる。
標準ライブラリのみ。外部依存なし。

path が当たらない場合は本文抜粋で行を探すフォールバックに落ちる。呼び出し側が
どこまで信じてよいか判断できるよう、confidence を必ず返す。
    exact — path とタグ(と id/class)が一致した
    text  — path は外れたが、本文抜粋が1行に見つかった
    none  — 特定できなかった。エージェントはファイル全体を読むこと
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

# 終了タグを持たない要素。スタックに積むと以降の兄弟の index が全部ずれる。
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


@dataclass
class Node:
    tag: str
    path: tuple[int, ...]
    line: int
    col: int
    attrs: dict


class _Indexer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[Node] = []
        # 各フレーム: [tag, 開いた子要素の数, その要素自身の path]
        # 祖先の counter を後から読むと、すでに次の兄弟まで進んでいてずれる。
        # 要素ごとに確定した path を持たせて、子はそれを引き継ぐ。
        self._stack: list[list] = []

    def _record(self, tag: str, attrs) -> tuple[int, ...]:
        if self._stack:
            parent = self._stack[-1]
            path = tuple(parent[2]) + (parent[1],)
            parent[1] += 1
        else:
            path = ()  # ルート (html)
        line, col = self.getpos()
        self.nodes.append(Node(tag, path, line, col, dict(attrs)))
        return path

    def handle_starttag(self, tag, attrs):
        path = self._record(tag, attrs)
        if tag not in VOID:
            self._stack.append([tag, 0, path])

    def handle_startendtag(self, tag, attrs):
        # <br/> のような自己終端。開いて閉じるので積まない。
        self._record(tag, attrs)

    def handle_endtag(self, tag):
        # 閉じ忘れがあっても、対応する開始タグまで一気に畳んで復帰する。
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                return


def index_source(text: str) -> list[Node]:
    p = _Indexer()
    p.feed(text)
    p.close()
    return p.nodes


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _find_line_by_text(text: str, excerpt: str) -> int | None:
    """本文抜粋を含む行を探す。前方から短くしながら試す。"""
    needle = _norm(excerpt)
    if len(needle) < 4:
        return None
    lines = text.splitlines()
    for width in (24, 16, 10, 6):
        if len(needle) < width:
            continue
        probe = needle[:width]
        hits = [i + 1 for i, ln in enumerate(lines) if probe in _norm(ln)]
        if len(hits) == 1:
            return hits[0]
        if hits:
            return hits[0]  # 複数一致でも最初の行を手がかりとして返す
    return None


def resolve(
    text: str,
    path: list[int] | None,
    *,
    tag: str | None = None,
    classes: list[str] | None = None,
    el_id: str | None = None,
    text_excerpt: str | None = None,
) -> dict:
    """path -> {"line": int|None, "confidence": "exact"|"text"|"none"}"""
    if path is not None:
        want = tuple(path)
        hit = next((n for n in index_source(text) if n.path == want), None)
        if hit is not None and (tag is None or hit.tag == tag.lower()):
            ok = True
            if el_id and hit.attrs.get("id") != el_id:
                ok = False
            if classes:
                have = set((hit.attrs.get("class") or "").split())
                if not set(classes).issubset(have):
                    ok = False
            if ok:
                return {"line": hit.line, "confidence": "exact"}

    line = _find_line_by_text(text, text_excerpt or "")
    if line:
        return {"line": line, "confidence": "text"}
    return {"line": None, "confidence": "none"}
