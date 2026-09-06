#!/usr/bin/env python3
"""指摘1件を1本のスレッドとして持つ層。サーバと CLI がここを共有する。

    .loop/feedback/threads/fb-003.jsonl   追記専用のイベント列 (1指摘 = 1ファイル)
    .loop/feedback/escalations.jsonl      サブ→メインのテーマ判断依頼の台帳
    .loop/feedback/merged.jsonl           マージで確定した意図
    .loop/feedback/cursor.json            エージェントがどこまで読んだか

スレッドが唯一の正本。起票内容も状態もここにしかない (ビューアのピンもここを見る)。
同じ事実を別ファイルにも書くと、必ず片方が古くなって「どちらが本当か」を調べる羽目になる。

なぜ1スレッド1ファイルか:
  追記専用なので競合しない。丸ごと読めばそのスレッドの文脈が過不足なく揃う。
  「他のスレッドの会話は渡さない」という設計上の境界が、そのままファイル境界になる。

状態は最後のイベントの state。エージェントは proposed までしか進められず、
**merged にできるのはユーザーだけ**。
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import review_deck_adapter as adapter

_lock = threading.RLock()

# ---------------------------------------------------------------- 状態

AI_STATES = ("in_progress", "waiting_main", "proposed", "deferred", "rejected")
USER_STATES = ("changes_requested", "merged", "closed")
STATES = ("open",) + AI_STATES + USER_STATES
TERMINAL = ("merged", "closed")

STATE_JA = {
    "open": "未着手", "in_progress": "作業中", "waiting_main": "テーマ判断待ち",
    "proposed": "確認待ち", "changes_requested": "差し戻し", "merged": "マージ済み",
    "deferred": "保留", "rejected": "却下", "closed": "取り下げ",
}

# エスカレーションの固定語彙。自由文にすると集約の判定が曖昧になり、
# メインが会話を読みたくなる。読みたくなった時点で設計が負けている。
ESCALATION_KEYS = {
    "body_font_small": "本文が小さい / 入らない",
    "heading_scale": "見出しと本文の階層比",
    "line_height": "行間・行長",
    "contrast_low": "コントラスト",
    "palette_color": "色そのもの",
    "spacing_rhythm": "余白のリズム",
    "figure_font_small": "図中の文字",
    "other": "上のどれでもない (集約には数えない)",
}


class ThreadError(Exception):
    """呼び出し側の誤り。HTTP なら 400/409 に対応する。"""


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------- パス

def threads_dir(root: Path) -> Path:
    d = adapter.feedback_dir(root) / "threads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def thread_path(root: Path, tid: str) -> Path:
    if not tid or "/" in tid or ".." in tid:
        raise ThreadError(f"不正な id: {tid!r}")
    return threads_dir(root) / f"{tid}.jsonl"


def _fpath(root: Path, name: str) -> Path:
    return adapter.feedback_dir(root) / name


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def _append_jsonl(path: Path, rec: dict) -> dict:
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ---------------------------------------------------------------- 読み

def read(root: Path, tid: str) -> list[dict]:
    return _read_jsonl(thread_path(root, tid))


def state_of(events: list[dict]) -> str:
    for ev in reversed(events):
        if ev.get("state"):
            return ev["state"]
    return "open"


def ids(root: Path) -> list[str]:
    return sorted(p.stem for p in threads_dir(root).glob("*.jsonl"))


def head(root: Path, tid: str) -> dict:
    """スレッドの見出し。起票イベントから取る。"""
    ev = read(root, tid)
    first = ev[0] if ev else {}
    return {
        "id": tid,
        "slide": first.get("slide") or {},
        "instruction": first.get("text") or "",
        "state": state_of(ev),
        "seq": ev[-1]["seq"] if ev else 0,
        "updated_at": ev[-1]["at"] if ev else None,
        "events": len(ev),
    }


def index(root: Path) -> list[dict]:
    return [head(root, t) for t in ids(root)]


def revision(root: Path) -> str:
    """スレッドが1つでも変わったかを1文字列で表す。ポーリング用。"""
    parts = []
    for p in sorted(threads_dir(root).glob("*.jsonl")):
        st = p.stat()
        parts.append(f"{p.stem}:{st.st_mtime_ns}:{st.st_size}")
    return "|".join(parts)


# ---------------------------------------------------------------- 書き

def _next_seq(events: list[dict]) -> int:
    return (events[-1]["seq"] + 1) if events else 1


def append(root: Path, tid: str, ev: dict) -> dict:
    """イベントを1つ積む。state の妥当性はここで見る。"""
    with _lock:
        events = read(root, tid)
        cur = state_of(events)
        state = ev.get("state")
        role = ev.get("role")

        if events and cur in TERMINAL and ev.get("kind") != "note":
            raise ThreadError(f"{tid} は {STATE_JA[cur]} で閉じている (追記できるのは note だけ)")
        if state:
            if state not in STATES:
                raise ThreadError(f"未知の state: {state}")
            if role == "ai" and state in USER_STATES:
                raise ThreadError(f"エージェントは {state} にできない (merged はユーザーだけ)")
            if role == "user" and state in AI_STATES:
                raise ThreadError(f"ユーザーは {state} にできない")

        rec = {"v": 1, "id": tid, "seq": _next_seq(events), "at": now(), **ev}
        return _append_jsonl(thread_path(root, tid), rec)


def start(root: Path, item: dict) -> dict:
    """inbox の1件からスレッドを起こす。起票イベントが seq 1。"""
    tid = item["id"]
    path = thread_path(root, tid)
    if path.is_file() and _read_jsonl(path):
        return head(root, tid)
    append(root, tid, {
        "role": "user", "kind": "comment", "state": "open",
        "slide": item.get("slide") or {},
        "round": item.get("round"),
        "text": item.get("instruction") or "",
        "text_expanded": item.get("instruction_expanded") or "",
        "refs": item.get("refs") or [],
    })
    return head(root, tid)


def post(root: Path, tid: str, *, role: str, text: str, state: str | None = None,
         kind: str = "comment", **extra) -> dict:
    ev = {"role": role, "kind": kind, "text": text}
    if state:
        ev["state"] = state
    ev.update({k: v for k, v in extra.items() if v not in (None, [], {})})
    rec = append(root, tid, ev)
    if role == "ai":
        # 返事を書いた = そのスレッドのユーザー発言を読んだ、ということ。
        ack(root, tid)
    return rec


# ---------------------------------------------------------------- エスカレーション

def escalate(root: Path, tid: str, *, key: str, slide: str, ask: str, local: str = "") -> dict:
    if key not in ESCALATION_KEYS:
        raise ThreadError(f"未知の key: {key}。使えるのは {', '.join(ESCALATION_KEYS)}")
    rec = {"v": 1, "at": now(), "thread": tid, "slide": slide, "key": key,
           "ask": ask, "local": local, "status": "pending"}
    with _lock:
        _append_jsonl(_fpath(root, "escalations.jsonl"), rec)
    post(root, tid, role="ai", kind="escalate", state="waiting_main",
         text=ask, escalation={"key": key, "slide": slide, "ask": ask, "local": local})
    return rec


def ledger(root: Path) -> list[dict]:
    """(thread, key) ごとに最新の状態へ畳んだ台帳。"""
    fold: dict[tuple, dict] = {}
    for rec in _read_jsonl(_fpath(root, "escalations.jsonl")):
        fold[(rec.get("thread"), rec.get("key"))] = {**fold.get((rec.get("thread"), rec.get("key")), {}), **rec}
    return list(fold.values())


def pending_by_key(root: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for rec in ledger(root):
        if rec.get("status") == "pending":
            out.setdefault(rec["key"], []).append(rec)
    return out


def aggregate_min(root: Path, gates: dict | None = None) -> int:
    """しきい値は gates.json に置く。基準の置き場を1箇所にまとめるため。"""
    if gates is None:
        from .check_deck import gates_for
        gates_path = gates_for(root)
        try:
            gates = json.loads(gates_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            gates = {}
    return int(gates.get("theme_aggregate_min", 2))


def decide(root: Path, key: str, *, status: str, note: str) -> list[dict]:
    """メインの裁定。同じ key の pending を全部閉じ、各スレッドに書き戻す。

    2件目が来てから1件目にさかのぼって適用できることが、この台帳の存在理由。
    """
    if status not in ("applied_by_main", "declined"):
        raise ThreadError("status は applied_by_main か declined")
    hits = pending_by_key(root).get(key, [])
    if not hits:
        raise ThreadError(f"{key} の pending がない")
    out = []
    for rec in hits:
        with _lock:
            _append_jsonl(_fpath(root, "escalations.jsonl"),
                          {**rec, "at": now(), "status": status, "note": note})
        # どちらの裁定でも、担当サブは自分のスレッドの作業に戻る
        out.append(post(root, rec["thread"], role="ai", kind="decision", state="in_progress",
                        actor="main", text=note,
                        decision={"key": key, "status": status}))
    return out


# ---------------------------------------------------------------- マージ

def last_check(root: Path, tid: str) -> dict | None:
    for ev in reversed(read(root, tid)):
        if ev.get("check"):
            return ev["check"]
    return None


def merge(root: Path, tid: str, *, intent: str, check: dict | None = None,
          check_skipped: str = "") -> dict:
    """ユーザーの合意。ここで初めて確定する。"""
    events = read(root, tid)
    if not events:
        raise ThreadError(f"{tid} がない")
    cur = state_of(events)
    if cur == "merged":
        raise ThreadError(f"{tid} はすでにマージ済み")
    if cur != "proposed":
        raise ThreadError(f"マージできるのは確認待ち (proposed) のときだけ。いまは {STATE_JA.get(cur, cur)}")
    if not (intent or "").strip():
        raise ThreadError("確定した意図を1行で書いてほしい (## accepted に積む行になる)")

    chk = check or last_check(root, tid)
    if chk and chk.get("block"):
        raise ThreadError(f"block が {chk['block']}件 残っている。gates を割ったままマージはできない")

    first = events[0]
    rec = post(root, tid, role="user", kind="merge", state="merged",
               text=intent, intent=intent, check=chk or None,
               check_skipped=check_skipped or None)

    slide = (first.get("slide") or {}).get("id") or ""
    accepted_line = f"[user] {slide}: {intent} ({tid})".strip()

    with _lock:
        _append_jsonl(_fpath(root, "merged.jsonl"), {
            "v": 1, "id": tid, "merged_at": rec["at"],
            "slide": slide, "slide_file": (first.get("slide") or {}).get("file"),
            "asked": first.get("text") or "",
            "intent": intent,
            "did": _last_ai_text(events) or "",
            "rounds": sum(1 for e in events if e.get("role") == "ai"),
            "files": sorted({c.get("file") for e in events for c in (e.get("changes") or []) if c.get("file")}),
            "check": chk or None,
            "check_skipped": check_skipped or None,
        })

    append_accepted(root / "deck.md", accepted_line)
    return rec


def append_accepted(deck_md: Path, line: str) -> bool:
    """deck.md の ## accepted の末尾に1行足す。節が無ければ作る。

    ここが肝心。積まないと次のラウンドで批評サブエージェントが逆方向に指摘し、
    ユーザーの意思が静かに巻き戻る。
    """
    if not deck_md.is_file():
        return False
    lines = deck_md.read_text(encoding="utf-8").splitlines()
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

    # 節の末尾。ただし節と節の間の空行より前に入れる。
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    insert = end
    while insert > start + 1 and not lines[insert - 1].strip():
        insert -= 1
    lines.insert(insert, entry)
    deck_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def _last_ai_text(events: list[dict]) -> str:
    for ev in reversed(events):
        if ev.get("role") == "ai" and ev.get("text"):
            return ev["text"]
    return ""


def note(root: Path, tid: str, text: str, actor: str = "main") -> dict:
    """状態を動かさない追記。確定後のスレッドにも書ける唯一の種類。"""
    return post(root, tid, role="ai", kind="note", text=text, actor=actor)


def notify(root: Path, *, text: str, slides: list[str] | None = None,
           states: tuple[str, ...] = ("merged",), actor: str = "main") -> list[dict]:
    """条件に合うスレッドに note を配る。

    theme.css を触ると、**すでにマージされた枚の見え方も変わる**。黙って変えると
    ユーザーは自分が確認して合意した絵とは違うものを納品されることになる。
    状態は動かさない (勝手に開き直さない)。気づかせるだけ。
    """
    out = []
    for tid in ids(root):
        events = read(root, tid)
        if not events:
            continue
        if states and state_of(events) not in states:
            continue
        if slides and (events[0].get("slide") or {}).get("id") not in slides:
            continue
        out.append(note(root, tid, text, actor=actor))
    return out


def merged(root: Path) -> list[dict]:
    return _read_jsonl(_fpath(root, "merged.jsonl"))


# ---------------------------------------------------------------- カーソル

def _cursor(root: Path) -> dict:
    path = _fpath(root, "cursor.json")
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def ack(root: Path, tid: str) -> None:
    with _lock:
        cur = _cursor(root)
        cur[tid] = _next_seq(read(root, tid)) - 1
        _fpath(root, "cursor.json").write_text(
            json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")


def unread(root: Path) -> list[dict]:
    """エージェントがまだ返事をしていないユーザー発言。スレッドごとにまとめる。"""
    cur = _cursor(root)
    out = []
    for tid in ids(root):
        events = read(root, tid)
        seen = cur.get(tid, 0)
        new = [e for e in events if e["seq"] > seen and e.get("role") == "user"]
        if new:
            out.append({"id": tid, "state": state_of(events),
                        "slide": (events[0].get("slide") or {}),
                        "new": new, "events": len(events)})
    return out
