#!/usr/bin/env python3
"""デッキをローカル配信し、ブラウザ上の DOM 指定をフィードバック JSON に落とす。

    uvx --from <このスキルのディレクトリ>/tools html-deck-review <deck-dir> [--open] [--port N]

なぜサーバが要るか:
  file:// では親ページから iframe の contentDocument に到達できない (Chrome で実測、
  sandbox 属性を外しても null)。同一オリジンの http で配信して初めて、要素の位置や
  computedStyle を読み、ホバーとクリックを拾える。スライド側の CSP は
  script-src 'none' のままでよい。ピッカーは全部親側で動く。

出すもの:
  <deck>/.loop/feedback/threads/*.jsonl 1指摘 = 1スレッドの会話ログ (これが唯一の正本)

受信するたび標準出力に1行出す。バックグラウンド起動しておけば、
エージェントはその行で「ユーザーが指摘を出した」ことに気づける。
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
import threading
import tempfile
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .setup_export_runtime import ensure_node

from . import review_anchor as anchor  # noqa: E402
from . import review_deck_adapter as adapter  # noqa: E402
from . import review_threads as threads  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"
REVIEW_HTML = ASSETS / "review.html"
SHELL_CSS = ASSETS / "shell.css"

_lock = threading.Lock()
# 1プロセスにつき書き出しは1本だけ。Chromeを同時起動するとmacOSで固まりやすい。
_export_lock = threading.Lock()


# ---------------------------------------------------------------- 解決

def _resolve_ref(root: Path, slide_file: str, ref: dict) -> dict:
    """ブラウザが送ってきた1件の参照を、ソース行まで解決して返す。"""
    src_path = (root / slide_file)
    try:
        src = src_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        src = ""

    out = dict(ref)
    if ref.get("kind") == "region":
        a = ref.get("anchor") or {}
        r = anchor.resolve(
            src, a.get("path"),
            tag=a.get("tag"), classes=a.get("classes"), el_id=a.get("id"),
            text_excerpt=a.get("text_excerpt"),
        )
        a["file_line"] = r["line"]
        a["anchor_confidence"] = r["confidence"]
        out["anchor"] = a
    else:
        r = anchor.resolve(
            src, ref.get("path"),
            tag=ref.get("tag"), classes=ref.get("classes"), el_id=ref.get("id"),
            text_excerpt=ref.get("text_excerpt"),
        )
        out["file_line"] = r["line"]
        out["anchor_confidence"] = r["confidence"]
    return out


def _describe(ref: dict, slide_file: str) -> str:
    """#N が何を指しているかの1行表現。instruction_expanded に埋める。"""
    if ref.get("kind") == "region":
        r = ref.get("rect", {})
        a = ref.get("anchor") or {}
        where = f"{slide_file}:{a['file_line']}" if a.get("file_line") else slide_file
        return (f"領域 x={r.get('x')} y={r.get('y')} w={r.get('w')} h={r.get('h')} "
                f"({where} の <{a.get('tag', '?')}> 内)")
    where = f"{slide_file}:{ref['file_line']}" if ref.get("file_line") else slide_file
    sel = ref.get("selector") or ref.get("tag", "?")
    text = (ref.get("text_excerpt") or "").strip()
    text = f"「{text[:40]}」" if text else ""
    return f"{where} {sel} {text}".strip()


def _expand(instruction: str, refs: list[dict], slide_file: str) -> str:
    """#1 を実体の説明に置き換えた版。スキーマを知らない読み手でも意味が取れる。"""
    out = instruction
    for ref in sorted(refs, key=lambda r: -int(r["n"])):  # #10 を #1 より先に置換
        out = out.replace(f"#{ref['n']}", f"[#{ref['n']} = {_describe(ref, slide_file)}]")
    return out


ID_RE = re.compile(r"fb-(\d+)$")


def next_id(root: Path) -> str:
    """既存の最大番号 + 1。本数で数えない。

    スレッドが1本消えると本数が減り、生きている id をもう一度発番してしまう。
    `threads.start()` は既存のスレッドがあれば追記せずそれを返すので、
    衝突するとユーザーの新しい指摘が黙って消える。
    """
    nums = [int(m.group(1)) for t in threads.ids(root) if (m := ID_RE.fullmatch(t))]
    return f"fb-{max(nums, default=0) + 1:03d}"


def create_feedback(root: Path, payload: dict) -> dict:
    slide_file = payload.get("slide_file") or ""
    if not re.fullmatch(r"slides/[\w.\-]+\.html", slide_file):
        raise ValueError(f"不正な slide_file: {slide_file!r}")

    refs = [_resolve_ref(root, slide_file, r) for r in payload.get("refs", [])]

    with _lock:
        item = {
            "id": next_id(root),
            "round": adapter.current_round(root),
            "slide": {
                "id": payload.get("slide_id"),
                "file": slide_file,
                "title": payload.get("slide_title"),
            },
            "instruction": (payload.get("instruction") or "").strip(),
            "refs": refs,
        }
        item["instruction_expanded"] = _expand(item["instruction"], refs, slide_file)
        threads.start(root, item)
    return item


def create_reply(root: Path, payload: dict) -> dict:
    """スレッドへのユーザーの返信。指定 (#N) を足せるので参照もここで解決する。"""
    tid = (payload.get("id") or "").strip()
    events = threads.read(root, tid)
    if not events:
        raise ValueError(f"スレッド {tid} がありません")
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("本文が空です")

    slide_file = (events[0].get("slide") or {}).get("file") or ""
    refs = []
    if payload.get("refs"):
        if not re.fullmatch(r"slides/[\w.\-]+\.html", slide_file):
            raise ValueError(f"不正な slide_file: {slide_file!r}")
        refs = [_resolve_ref(root, slide_file, r) for r in payload["refs"]]

    cur = threads.state_of(events)
    # 直したものへの返信は差し戻し。まだ動いていないスレッドへの追記はただのコメント。
    state = "changes_requested" if cur in ("proposed", "waiting_main", "deferred", "rejected") else None
    return threads.post(root, tid, role="user", text=text, state=state,
                        kind="comment", refs=refs,
                        text_expanded=_expand(text, refs, slide_file) if refs else None)


def run_full_check(root: Path, tid: str) -> tuple[dict | None, str]:
    """マージ前の full 検査。落ちても人の合意を止めない (理由を記録して通す)。"""
    try:
        proc = adapter.run_script("review_check", root, "--thread", tid, "--level", "full", timeout=300)
    except Exception as e:      # noqa: BLE001 - 検査が回らない理由は握りつぶさず記録して通す
        return None, f"検査を実行できなかった: {type(e).__name__}: {e}"
    path = adapter.feedback_dir(root) / "checks" / f"{tid}.json"
    if proc.returncode != 0 or not path.is_file():
        tail = [l for l in (proc.stderr or proc.stdout or "").splitlines() if l.strip()]
        return None, f"検査が失敗した: {tail[-1][:200] if tail else '理由不明'}"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, f"検査結果を読めなかった: {e}"
    return {k: rec.get(k) for k in ("at", "level", "slide", "block", "review", "info", "delta", "top")}, ""


def run_export(root: Path, module: str, *args: str) -> dict:
    if not _export_lock.acquire(blocking=False):
        return {"ok": False, "error": "別の書き出しが実行中です。完了後にもう一度お試しください"}
    try:
        return _run_export(root, module, *args)
    finally:
        _export_lock.release()


def _run_export(root: Path, module: str, *args: str) -> dict:
    """書き出し系スクリプトをそのまま叩く。ロジックはサーバに持たせない。

    ブラウザから起動できるのはサーバが動いているときだけ。デッキ同梱の
    index.html を file:// で開いた場合は、起動方法をポップアップで案内する。
    """
    if module == "export_pdf":
        ext, content_type = "pdf", "application/pdf"
    elif module == "export_pptx":
        ext, content_type = "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        ext, content_type = "html", "text/html; charset=utf-8"
    filename = f"{re.sub(r'[^A-Za-z0-9._-]+', '-', root.name).strip('.-') or 'deck'}.{ext}"
    with tempfile.TemporaryDirectory(prefix="html-deck-export-") as tmp:
        out_path = Path(tmp) / filename
        try:
            timeout = 60 if module == "export_pptx" else 600
            proc = adapter.run_script(module, root, "-o", out_path, *args, timeout=timeout)
        except Exception as e:      # noqa: BLE001 - 起動できない理由は全部ここでボタンに返す
            return {"ok": False, "error": f"{module} を実行できなかった: {type(e).__name__}: {e}"}
        if proc.returncode == 0 and not out_path.is_file():
            return {"ok": False, "error": f"{module} は出力ファイルを作成しなかった"}
        data = out_path.read_bytes() if proc.returncode == 0 else None
    out = "\n".join(l for l in (proc.stdout or "").splitlines() if l.strip())
    err = "\n".join(l for l in (proc.stderr or "").splitlines() if l.strip())
    if proc.returncode != 0:
        return {"ok": False, "error": (err or out or "理由不明")[-600:]}
    # 成功でも警告は出る (畳めなかった参照など)。捨てるとブラウザ側からは
    # 何も無かったように見える。stderr を先に置いて、最後の行が結果になるようにする
    # (ブラウザは最後の1行をトーストに出す)。
    return {"ok": True, "log": "\n".join(x for x in (err, out) if x)[-600:],
            "data": data, "filename": filename, "content_type": content_type}


def set_state(root: Path, payload: dict) -> dict:
    tid = (payload.get("id") or "").strip()
    state = payload.get("state")
    if not threads.read(root, tid):
        raise ValueError(f"スレッド {tid} がありません")
    if state == "merged":
        chk, skipped = run_full_check(root, tid)
        return threads.merge(root, tid, intent=(payload.get("intent") or "").strip(),
                             check=chk, check_skipped=skipped)
    if state == "closed":
        return threads.post(root, tid, role="user", kind="close", state="closed",
                            text=(payload.get("text") or "取り下げ").strip())
    raise ValueError(f"ここで指定できるのは merged / closed だけ: {state!r}")


# ---------------------------------------------------------------- HTTP

def make_handler(root: Path, token: str):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        # 既定のアクセスログは黙らせる。受信通知だけを標準出力に出したい。
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _download(self, res):
            body = res.pop("data")
            self.send_response(200)
            self.send_header("Content-Type", res["content_type"])
            self.send_header("Content-Disposition", f'attachment; filename="{res["filename"]}"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authed(self, query) -> bool:
            return (self.headers.get("X-Review-Token") == token
                    or (query.get("t") or [None])[0] == token)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/favicon.ico":
                # 置かないと毎回 404 がコンソールに出て、本物のエラーが埋もれる
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not u.path.startswith("/__review"):
                return super().do_GET()

            if not self._authed(q):
                return self._json({"error": "token が違います"}, 403)

            if u.path in ("/__review", "/__review/"):
                html = REVIEW_HTML.read_text(encoding="utf-8")
                # 共通の殻はビューア (index.html) と同じものを埋め込む
                html = html.replace("/* __SHELL__ */", SHELL_CSS.read_text(encoding="utf-8"))
                html = html.replace("__DECK_TITLE__", adapter.deck_title(root))
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            if u.path == "/__review/api/slides":
                return self._json({
                    "deck": adapter.deck_title(root),
                    "round": adapter.current_round(root),
                    "slides": adapter.slides(root),
                })

            if u.path == "/__review/api/threads":
                rev = threads.revision(root)
                if (q.get("since") or [None])[0] == rev:
                    return self._json({"rev": rev, "changed": False})
                return self._json({
                    "rev": rev, "changed": True,
                    "threads": [{**threads.head(root, tid), "log": threads.read(root, tid)}
                                for tid in threads.ids(root)],
                })

            if u.path.startswith("/__review/api/thread/"):
                tid = u.path.rsplit("/", 1)[-1]
                try:
                    log = threads.read(root, tid)
                except threads.ThreadError as e:
                    return self._json({"error": str(e)}, 400)
                if not log:
                    return self._json({"error": "not found"}, 404)
                return self._json({**threads.head(root, tid), "log": log})

            return self._json({"error": "not found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path not in ("/__review/api/feedback", "/__review/api/reply",
                              "/__review/api/state", "/__review/api/export"):
                return self._json({"error": "not found"}, 404)
            if not self._authed(q):
                return self._json({"error": "token が違います"}, 403)

            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                return self._json({"error": "payload が大きすぎます"}, 413)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as e:
                return self._json({"error": str(e)}, 400)

            if u.path == "/__review/api/feedback":
                try:
                    item = create_feedback(root, payload)
                except (ValueError, threads.ThreadError) as e:
                    return self._json({"error": str(e)}, 400)
                n = len(item["refs"])
                head = item["instruction"].replace("\n", " ")[:60]
                print(f'[feedback] {item["id"]} slide={item["slide"]["id"]} refs={n} :: {head}',
                      flush=True)
                return self._json({"ok": True, "item": item})

            if u.path == "/__review/api/export":
                kind = payload.get("kind")
                if kind == "pdf":
                    res = run_export(root, "export_pdf",
                                     *(["--allow-font-fallback"] if payload.get("force") else []))
                elif kind == "pptx":
                    res = run_export(root, "export_pptx")
                elif kind == "html":
                    res = run_export(root, "bundle_deck")
                else:
                    return self._json({"error": f"pdf、pptx、html のいずれか: {kind!r}"}, 400)
                print(f'[export] {kind} {"ok" if res["ok"] else "失敗"}', flush=True)
                if res["ok"]:
                    return self._download(res)
                return self._json(res, 200 if res["ok"] else 409)

            if u.path == "/__review/api/reply":
                try:
                    ev = create_reply(root, payload)
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
                except threads.ThreadError as e:
                    return self._json({"error": str(e)}, 409)
                print(f'[reply] {ev["id"]} #{ev["seq"]} state={ev.get("state") or "-"} '
                      f':: {ev["text"].replace(chr(10), " ")[:60]}', flush=True)
                return self._json({"ok": True, "event": ev})

            try:
                ev = set_state(root, payload)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            except threads.ThreadError as e:
                # gates を割ったままのマージ / 状態の順序違反はここで止まる
                return self._json({"error": str(e)}, 409)
            print(f'[state] {ev["id"]} #{ev["seq"]} → {ev.get("state")}'
                  + (f' :: {ev.get("intent")}' if ev.get("intent") else ''), flush=True)
            return self._json({"ok": True, "event": ev})

    return Handler


def main() -> int:
    adapter.utf8_io()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("--port", type=int, default=0, help="既定はランダムな空きポート")
    ap.add_argument("--open", action="store_true", help="ブラウザを自動で開く")
    args = ap.parse_args()

    root = args.deck.resolve()
    if not adapter.is_deck(root):
        print(f"error: {root} に slides/ がありません", file=sys.stderr)
        return 2

    # 書き出しボタンを押した瞬間に30秒黙る、を避けるため先に用意しておく。
    # 失敗してもサーバは立てる — レビュー本体は Node も Playwright も要らない。
    try:
        ensure_node(root)
    except Exception as e:      # noqa: BLE001 - 理由は全部そのまま見せる
        print(f"warning: 書き出し用ランタイムを用意できなかった: {e}", file=sys.stderr)
        print("  レビューは使えます。PDF/PPTX ボタンを押したときに再試行します。",
              file=sys.stderr, flush=True)

    token = secrets.token_urlsafe(12)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(root, token))
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/__review/?t={token}"

    print(f"deck   : {root}")
    print(f"review : {url}")
    print(f"threads: {adapter.feedback_dir(root) / 'threads'}")
    print("使い方 : E でレビューモード。要素をクリックすると入力欄に #1 のブロックが入る。"
          "空白をドラッグすると領域指定。P でピンだけ隠す。T で白/ナイト切替。"
          "Cmd/Ctrl+Enter で送信。E で閉じると枠は全部消える。", flush=True)

    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
