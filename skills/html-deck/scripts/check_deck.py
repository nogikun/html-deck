#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.44"]
# ///
"""固定1600x900キャンバスでHTMLスライドを実測し、決定的な合否と数値指標を返す。

使い方:
    uv run scripts/check_deck.py <deck-dir> [--round N] [--slide 03] [--no-shots]

やること:
  1. slides/*.html を走査して index.html のスライド一覧を再生成する
  2. 各スライドを 1600x900 のヘッドレスChromeで開き、DOMを実測する
  3. block / review / info の3段階で所見を返す
  4. スクリーンショットとコンタクトシートを .loop/round-N/ に保存する

出力: .loop/round-N/report.json と標準出力のサマリ。終了コードは block 件数>0 で 1。
このスクリプトは「見た目の良し悪し」を判定しない。物理的に壊れているものだけを落とす。
良し悪しは agents/slide-critic.md と agents/deck-critic.md の担当。
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GATES = SKILL_DIR / "assets" / "gates.json"

# ---------------------------------------------------------------- 計測用JS

EXTRACT_JS = r"""
() => {
  const parseColor = (s) => {
    if (!s) return null;
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map((x) => parseFloat(x));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };

  const shortSel = (el) => {
    const parts = [];
    let cur = el;
    for (let i = 0; cur && cur.nodeType === 1 && i < 4; i += 1) {
      let s = cur.tagName.toLowerCase();
      if (cur.id) { parts.unshift(s + '#' + cur.id); break; }
      if (cur.classList.length) s += '.' + [...cur.classList].slice(0, 2).join('.');
      parts.unshift(s);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  };

  const effectiveBg = (el) => {
    let cur = el;
    let uncertain = false;
    while (cur && cur.nodeType === 1) {
      const cs = getComputedStyle(cur);
      const c = parseColor(cs.backgroundColor);
      // 不透明な色に当たったらそこで確定。その要素自身の背景画像は
      // 「色の上に乗る装飾」であることが多いので不確実扱いにしない。
      // 途中の祖先に背景画像があったときだけ推定値とする。
      if (c && c.a > 0.98) return { color: c, uncertain };
      if (cs.backgroundImage && cs.backgroundImage !== 'none') uncertain = true;
      cur = cur.parentElement;
    }
    return { color: { r: 255, g: 255, b: 255, a: 1 }, uncertain };
  };

  const visible = (el, cs, rect) => (
    cs.display !== 'none' &&
    cs.visibility !== 'hidden' &&
    parseFloat(cs.opacity || '1') > 0.05 &&
    rect.width > 0 && rect.height > 0
  );

  const SVG_NS = 'http://www.w3.org/2000/svg';

  // SVG の中身は viewBox で拡大縮小される。CSSの font-size をそのまま読むと、
  // 実際に画面に出ている大きさと一致しない (viewBox を 3倍に伸ばせば 12 は 36px)。
  // 図の中の文字が読めるかを測るには、実効倍率を掛けた値を見る必要がある。
  const userScale = (el) => {
    if (el.namespaceURI !== SVG_NS || typeof el.getScreenCTM !== 'function') return 1;
    const m = el.getScreenCTM();
    if (!m) return 1;
    const det = Math.abs(m.a * m.d - m.b * m.c);
    return det > 0 ? Math.sqrt(det) : 1;
  };

  const els = [];
  const colorUse = [];
  const families = new Set();
  const textRuns = [];   // 文字の実行矩形。占有率と重なり判定に使う
  const figures = [];
  let textArea = 0;
  let allText = '';

  document.querySelectorAll('body, body *').forEach((el) => {
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (!visible(el, cs, rect)) return;

    const ownText = [...el.childNodes]
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent)
      .join('')
      .replace(/\s+/g, ' ')
      .trim();

    const box = {
      x: +rect.x.toFixed(1), y: +rect.y.toFixed(1),
      w: +rect.width.toFixed(1), h: +rect.height.toFixed(1),
      right: +rect.right.toFixed(1), bottom: +rect.bottom.toFixed(1),
    };

    // クリップ検出: overflow が隠す設定で中身が箱を超えている
    const hidesX = /hidden|clip/.test(cs.overflowX);
    const hidesY = /hidden|clip/.test(cs.overflowY);
    const clipped =
      (hidesY && el.scrollHeight > el.clientHeight + 2 && el.clientHeight > 0) ||
      (hidesX && el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0);

    const rec = {
      sel: shortSel(el),
      tag: el.tagName.toLowerCase(),
      box,
      clipped,
      clipOver: clipped ? [el.scrollWidth - el.clientWidth, el.scrollHeight - el.clientHeight] : null,
    };

    if (ownText) {
      const scale = userScale(el);
      const fs = parseFloat(cs.fontSize) * scale;   // 画面上の実効サイズ
      const fw = parseInt(cs.fontWeight, 10) || 400;
      const fg = parseColor(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
      const bg = effectiveBg(el);
      const lh = parseFloat(cs.lineHeight) || fs * 1.4;
      const lines = Math.max(1, Math.round(rect.height / lh));
      // 出典・注記・キャプションは長くても「読ませる文」ではない。
      // 役割で宣言された細字はラベル段階として扱い、下限を分ける。
      // 本文をこれで包んで検査を逃げると、批評担当が絵を見て落とす。
      const finePrint = !!el.closest('.slide-footer, .source, .caption, .footnote, figcaption, [data-fineprint]');
      // figcaption は「図の中の文字」ではなく図に付ける注記なので、細字側で扱う。
      // ここを分けないと、正しく書かれたキャプションが図中文字の下限に引っかかる。
      const inFigure = !finePrint && (el.namespaceURI === SVG_NS || !!el.closest('figure, svg'));
      rec.text = { chars: ownText.length, snippet: ownText.slice(0, 60), lines, finePrint, inFigure };
      rec.font = {
        size: +fs.toFixed(1),
        declared: +parseFloat(cs.fontSize).toFixed(1),
        scale: +scale.toFixed(3),
        weight: fw,
        family: (cs.fontFamily || '').split(',')[0].replace(/["']/g, '').trim(),
        lineHeight: +lh.toFixed(1),
      };
      rec.color = { fg, bg: bg.color, uncertain: bg.uncertain };
      families.add(rec.font.family);
      colorUse.push({ sel: rec.sel, role: 'text', rgb: [Math.round(fg.r), Math.round(fg.g), Math.round(fg.b)], a: fg.a });
      // 占有率は要素の箱ではなく、実際の行の矩形で測る。箱で測ると
      // 全幅の見出しやパディングの大きい枠が丸ごと計上され、
      // 短い一行の見出しでも「詰まっている」と誤判定する。
      [...el.childNodes].forEach((n) => {
        if (n.nodeType !== 3 || !n.textContent.trim()) return;
        const range = document.createRange();
        range.selectNodeContents(n);
        for (const rc of range.getClientRects()) {
          if (rc.width < 1 || rc.height < 1) continue;
          textArea += rc.width * rc.height;
          textRuns.push({
            sel: rec.sel, inFigure,
            x: rc.x, y: rc.y, w: rc.width, h: rc.height,
            snippet: n.textContent.trim().slice(0, 24),
          });
        }
      });
      allText += ownText + ' ';
      // 1行あたりの文字数 (概算): 総文字数 / 行数
      rec.text.charsPerLine = Math.round(ownText.length / lines);
    }

    const bc = parseColor(cs.borderTopColor);
    if (bc && bc.a > 0.02 && parseFloat(cs.borderTopWidth) > 0) {
      colorUse.push({ sel: rec.sel, role: 'border', rgb: [Math.round(bc.r), Math.round(bc.g), Math.round(bc.b)], a: bc.a });
    }
    // background-color は rgba の重ねやグラデーションで合成値になりやすく、
    // トークン照合の偽陽性が多い。パレット検査は text と border に絞る。

    // SVG の塗りと線は fill/stroke に出る。ここを見ないと、図だけが
    // 共有トークンの外で好きな色を使えてしまい、デッキの声が割れる。
    if (el.namespaceURI === SVG_NS) {
      [['fill', cs.fill], ['stroke', cs.stroke]].forEach(([role, raw]) => {
        if (!raw || raw === 'none') return;
        const c = parseColor(raw);
        if (!c || c.a <= 0.02) return;
        colorUse.push({
          sel: rec.sel, role: 'svg-' + role,
          rgb: [Math.round(c.r), Math.round(c.g), Math.round(c.b)], a: c.a,
        });
      });
    }

    els.push(rec);
  });

  // ---- 文字同士の重なり
  // LLMがSVGを書くとき最も多い失敗がラベルの重なりと矢印のずれ。通常のHTML組版では
  // 実行矩形は重ならないので、重なりが出たら座標指定側 (SVG・絶対配置) の事故と見てよい。
  const overlaps = [];
  for (let i = 0; i < textRuns.length; i += 1) {
    for (let j = i + 1; j < textRuns.length; j += 1) {
      const a = textRuns[i], b = textRuns[j];
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox <= 2 || oy <= 2) continue;
      const share = (ox * oy) / Math.min(a.w * a.h, b.w * b.h);
      if (share < 0.28) continue;
      overlaps.push({
        a: a.snippet, b: b.snippet, sel: a.sel, sel2: b.sel,
        share: +share.toFixed(2), inFigure: a.inFigure || b.inFigure,
      });
      if (overlaps.length >= 12) break;
    }
    if (overlaps.length >= 12) break;
  }

  // ---- 図 (インラインSVG / ラスタ画像)
  document.querySelectorAll('svg').forEach((svg) => {
    if (svg.closest('svg') !== svg) return;              // 入れ子のSVGは親だけ見る
    const r = svg.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    let escaped = 0;
    let minStroke = Infinity;
    let minInset = Infinity;
    // 枠外・内側余白の判定は「実際に何かを描く要素」だけで行う。
    // <g> <switch> <foreignObject> は子を包む箱で、それ自体は何も塗らない。
    // draw.io は width="100%" の容器を出すので、これを数えると
    // viewBox をずらした分がそのまま「はみ出し」として誤検出される。
    const DRAWN = new Set(['rect', 'circle', 'ellipse', 'path', 'line', 'polygon',
                           'polyline', 'text', 'tspan', 'image', 'use', 'DIV', 'SPAN']);
    svg.querySelectorAll('*').forEach((c) => {
      const cr = c.getBoundingClientRect();
      if (cr.width > 0 && cr.height > 0 && DRAWN.has(c.tagName)) {
        if (cr.right > r.right + 1 || cr.bottom > r.bottom + 1 ||
            cr.left < r.left - 1 || cr.top < r.top - 1) escaped += 1;
        else {
          minInset = Math.min(minInset,
            cr.left - r.left, cr.top - r.top, r.right - cr.right, r.bottom - cr.bottom);
        }
      }
      const cs2 = getComputedStyle(c);
      if (cs2.stroke && cs2.stroke !== 'none') {
        const sw = parseFloat(cs2.strokeWidth || '1') * userScale(c);
        if (sw > 0 && sw < minStroke) minStroke = sw;
      }
    });
    figures.push({
      kind: 'svg',
      sel: shortSel(svg),
      w: +r.width.toFixed(1), h: +r.height.toFixed(1),
      named: !!(svg.querySelector(':scope > title') || svg.getAttribute('aria-label')),
      hidden: svg.getAttribute('aria-hidden') === 'true',
      viewBox: svg.getAttribute('viewBox') || '',
      escaped,
      minStroke: minStroke === Infinity ? null : +minStroke.toFixed(2),
      minInset: minInset === Infinity ? null : +minInset.toFixed(1),
    });
  });

  document.querySelectorAll('img').forEach((img) => {
    const r = img.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    figures.push({
      kind: 'img',
      sel: shortSel(img),
      w: +r.width.toFixed(1), h: +r.height.toFixed(1),
      naturalW: img.naturalWidth, naturalH: img.naturalHeight,
      alt: img.getAttribute('alt'),
      objectFit: getComputedStyle(img).objectFit,
      src: (img.getAttribute('src') || '').slice(0, 80),
    });
  });

  const bullets = document.querySelectorAll('li').length;

  return {
    title: document.title || '',
    lang: document.documentElement.lang || '',
    headings: [...document.querySelectorAll('h1,h2,h3')].map((h) => ({
      tag: h.tagName.toLowerCase(),
      text: (h.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
      size: +parseFloat(getComputedStyle(h).fontSize).toFixed(1),
    })),
    scroll: { w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight },
    elements: els,
    colorUse,
    families: [...families],
    overlaps,
    figures,
    bullets,
    textArea: Math.round(textArea),
    allText: allText.trim(),
    // <link rel=stylesheet> の実体は file:// だと cssRules が読めない (opaque)。
    // トークンは Python 側で CSS を読んで解決する。
    styleHrefs: [...document.querySelectorAll('link[rel~="stylesheet"]')].map((l) => l.getAttribute('href')),
  };
}
"""

# ---------------------------------------------------------------- 計算ヘルパ


def _srgb(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_srgb(rgb["r"]), _srgb(rgb["g"]), _srgb(rgb["b"]))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def composite(fg, bg):
    """半透明の前景を背景に合成する。"""
    a = fg.get("a", 1)
    if a >= 0.999:
        return fg
    return {
        "r": fg["r"] * a + bg["r"] * (1 - a),
        "g": fg["g"] * a + bg["g"] * (1 - a),
        "b": fg["b"] * a + bg["b"] * (1 - a),
        "a": 1,
    }


def contrast(fg, bg) -> float:
    l1, l2 = sorted([luminance(composite(fg, bg)), luminance(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


JA_RE = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})")


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) < 6:
        return None
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


TOKEN_DECL_RE = re.compile(r"--[\w-]+\s*:\s*([^;}]+)")


def token_palette(css_text: str) -> set:
    """theme.css の CSS変数宣言から、共有色として許可するRGB三つ組を集める。

    file:// では linked stylesheet の cssRules をブラウザから読めない (opaque) ため、
    CSSファイルを直接読んで解決する。ここを間違えると全色が逸脱扱いになる。
    """
    palette = {(0, 0, 0), (255, 255, 255)}
    for m in TOKEN_DECL_RE.finditer(css_text):
        value = m.group(1)
        for hm in HEX_RE.finditer(value):
            rgb = hex_to_rgb(hm.group(0))
            if rgb:
                palette.add(rgb)
        for cm in re.finditer(r"rgba?\(([^)]+)\)", value):
            parts = [p.strip() for p in cm.group(1).split(",")]
            try:
                palette.add(tuple(int(float(p)) for p in parts[:3]))
            except ValueError:
                pass
    return palette


def collect_theme_css(slide_path: Path, hrefs: list[str]) -> str:
    """スライドが読み込んでいる外部CSSを全部つないで返す。"""
    chunks = []
    for href in hrefs or []:
        if not href or href.startswith(("http://", "https://", "data:")):
            continue
        p = (slide_path.parent / href).resolve()
        if p.is_file():
            try:
                chunks.append(p.read_text(encoding="utf-8"))
            except OSError:
                pass
    return "\n".join(chunks)


def near_palette(rgb, palette, tol=10) -> bool:
    for p in palette:
        if abs(rgb[0] - p[0]) <= tol and abs(rgb[1] - p[1]) <= tol and abs(rgb[2] - p[2]) <= tol:
            return True
    return False


# ---------------------------------------------------------------- 判定


def evaluate(data: dict, gates: dict, source: str, slide_id: str, theme_css: str = "") -> dict:
    W = gates["canvas"]["width"]
    H = gates["canvas"]["height"]
    inset = gates["safe_inset_px"]
    findings = []

    def add(sev, code, msg, **extra):
        findings.append({"severity": sev, "code": code, "message": msg, **extra})

    # --- 文書レベル
    if not data["title"].strip():
        add("block", "missing_title", "<title> が空。スクリーンリーダーとビューアの一覧が壊れる。")
    if not any(h["tag"] in ("h1", "h2") for h in data["headings"]):
        add("review", "no_headline", "h1/h2 がない。主張を1行で言い切る見出しを置く。")
    if data["scroll"]["w"] > W + 1 or data["scroll"]["h"] > H + 1:
        add("block", "document_overflow",
            f"文書全体が {data['scroll']['w']}x{data['scroll']['h']} で {W}x{H} を超えている。")

    if re.search(r"""(?:src|href)\s*=\s*["']https?://""", source) or re.search(r"url\(\s*['\"]?https?://", source):
        add("block", "external_ref", "外部URLを参照している。オフライン配布とCSPで壊れる。相対パスかdata:に置き換える。")
    if re.search(r"<script[\s>]", source, re.I):
        add("block", "script_tag", "スライド内に <script> がある。静的配布プロファイルではCSPで実行されない。")
    if "Content-Security-Policy" not in source:
        add("review", "no_csp", "CSPメタタグがない。テンプレートのCSP行を戻す。")

    # --- 要素レベル
    max_size = 0.0
    sizes = []
    body_sizes = []
    for el in data["elements"]:
        b = el["box"]
        if b["right"] > W + 1 or b["bottom"] > H + 1 or b["x"] < -1 or b["y"] < -1:
            add("block", "canvas_overflow",
                f"{el['sel']} がキャンバス外にはみ出している "
                f"(x{b['x']} y{b['y']} → {b['right']}x{b['bottom']})", selector=el["sel"])
        elif (b["right"] > W - inset or b["bottom"] > H - inset
              or b["x"] < inset or b["y"] < inset) and el.get("text"):
            add("info", "safe_area",
                f"{el['sel']} が安全余白({inset}px)に食い込んでいる。", selector=el["sel"])

        if el["clipped"]:
            add("block", "clipped_text",
                f"{el['sel']} の中身が箱に収まらず切れている (超過 {el['clipOver']}px)。"
                "文字を減らすか箱を広げる。", selector=el["sel"])

        f = el.get("font")
        if not f:
            continue
        sizes.append(f["size"])
        max_size = max(max_size, f["size"])
        t = el["text"]
        # 見出しは階層の頂点であって本文ではない。長い見出しを本文に数えると
        # 本文中央値が見出しサイズまで持ち上がり、階層比が 1.0 に潰れる。
        is_body = (
            t["chars"] >= gates["body_text_chars"]
            and not t.get("finePrint")
            and not t.get("inFigure")   # 図中の文字は別段階。地の文と同じ下限を当てない
            and el["tag"] not in ("h1", "h2", "h3", "h4", "h5", "h6")
        )
        if is_body:
            body_sizes.append(f["size"])

        # 文字サイズは2段階で見る。読ませる文 (本文) と、目印としてのラベルでは
        # 必要な大きさが違う。同じ下限を当てると、装飾ラベルの修正で
        # ループの枠が埋まって肝心の本文に手が回らない。
        if f["size"] < gates["font_px_block"]:
            extra = ""
            if abs(f.get("scale", 1) - 1) > 0.01:
                extra = (f" (指定 {f['declared']}px × viewBox倍率 {f['scale']} の実効値。"
                         "SVG側の font-size ではなく、図の表示サイズか viewBox を見直す)")
            add("block", "font_unreadable",
                f"{el['sel']} が {f['size']}px。縮小表示で消えるので下限 {gates['font_px_block']}px を切らない "
                f"(「{t['snippet']}」){extra}", selector=el["sel"])
        elif t.get("inFigure") and f["size"] < gates["figure_font_px_min"]:
            add("review", "figure_font_small",
                f"{el['sel']} の図中の文字が {f['size']}px。図の中は本文より一段小さくてよいが "
                f"{gates['figure_font_px_min']}px は要る (「{t['snippet']}」)。"
                "文字を図の外に出すか、図を大きくする。", selector=el["sel"])
        elif is_body and f["size"] < gates["body_font_px_min"]:
            sev = "block" if f["size"] < gates["body_font_px_block"] else "review"
            add(sev, "body_font_small",
                f"{el['sel']} の本文({t['chars']}字)が {f['size']}px。"
                f"投影時に読める下限は {gates['body_font_px_min']}px (「{t['snippet']}」)",
                selector=el["sel"])
        elif not is_body and f["size"] < gates["label_font_px_min"]:
            add("review", "label_font_small",
                f"{el['sel']} のラベルが {f['size']}px。{gates['label_font_px_min']}px未満は"
                "縮小表示で読まれなくなる (「" + t["snippet"] + "」)", selector=el["sel"])

        c = el["color"]
        ratio = contrast(c["fg"], c["bg"])
        is_large = f["size"] >= gates["large_text_px"] or (
            f["size"] >= gates["large_text_bold_px"] and f["weight"] >= 700)
        need = gates["contrast_min_large"] if is_large else gates["contrast_min"]
        if ratio < need:
            # 背景が推定値のときは review に落とす。ただし大きく外している場合は
            # 背景をどう見積もっても足りないので block のままにする。
            sev = "review" if (c["uncertain"] and ratio > need * 0.7) else "block"
            add(sev, "low_contrast",
                f"{el['sel']} のコントラスト比 {ratio:.2f} < {need} "
                f"({f['size']}px/{f['weight']}{'、背景が画像/グラデーションで推定値' if c['uncertain'] else ''})",
                selector=el["sel"], ratio=round(ratio, 2))

        limit = gates["max_line_chars_ja"] if JA_RE.search(t["snippet"]) else gates["max_line_chars_en"]
        if t.get("charsPerLine", 0) > limit and t["lines"] > 1:
            add("info", "long_measure",
                f"{el['sel']} が1行 約{t['charsPerLine']}字。{limit}字を超えると視線が戻りにくい。",
                selector=el["sel"])

    # --- 密度と階層
    text = data["allText"]
    ja = len(JA_RE.findall(text))
    en_words = len(re.findall(r"[A-Za-z][A-Za-z'-]+", text))
    if ja > gates["max_ja_chars"]:
        add("review", "too_dense", f"日本語 {ja}文字。1枚 {gates['max_ja_chars']}字を超えると3秒で読めない。")
    if ja < 20 and en_words > gates["max_en_words"]:
        add("review", "too_dense", f"英単語 {en_words}語。{gates['max_en_words']}語を超えると1枚に詰めすぎ。")

    distinct = sorted({round(s) for s in sizes})
    if len(distinct) > gates["max_distinct_font_sizes"]:
        add("review", "type_scale_noise",
            f"文字サイズが {len(distinct)}種類 ({distinct})。段階が多いと階層が読めない。")

    # 短い箇条書きだけで構成された枚には「本文」に当たる要素がない。
    # そのまま 0 にすると階層の検査ごと素通りするので、最大サイズを除いた
    # 全テキストの中央値を基準に置き換える。
    # 中央値は偶数個のとき下側を取る。上側を取ると、要素が2つしかない枚で
    # 大きいほうが中央値になり、階層比が実態より小さく出る。
    if body_sizes:
        ordered = sorted(body_sizes)
        median_body = ordered[(len(ordered) - 1) // 2]
        min_body = ordered[0]
        body_basis = "body"
    elif len(sizes) > 1:
        rest = sorted(s for s in sizes if s < max_size) or sorted(sizes)
        median_body = rest[(len(rest) - 1) // 2]
        min_body = rest[0]
        body_basis = "fallback"
    else:
        median_body, min_body, body_basis = 0, 0, "none"
    ratio_h = (max_size / median_body) if median_body else 0
    if median_body and ratio_h < gates["min_hierarchy_ratio"]:
        add("review", "weak_hierarchy",
            f"最大 {max_size}px / 本文中央値 {median_body}px = {ratio_h:.2f}倍。"
            f"{gates['min_hierarchy_ratio']}倍未満だと最初に読む場所が決まらない。")

    area_ratio = data["textArea"] / (W * H)
    fig_share = sum(f["w"] * f["h"] for f in data.get("figures", [])) / (W * H)
    if area_ratio > gates["text_area_ratio_max"]:
        add("review", "overfilled", f"文字ブロックが画面の {area_ratio:.0%}。余白が足りない。")
    elif area_ratio < gates["text_area_ratio_min"] and ja + en_words > 0 and fig_share < 0.15:
        # 図が主役の枚は文字が少なくて当然。図の面積を見ずに薄いと言わない。
        add("info", "underfilled", f"文字ブロックが画面の {area_ratio:.0%}。1枚として情報が薄い可能性。")

    # --- 文字の重なり
    for ov in data.get("overlaps", []):
        where = "図の中で" if ov["inFigure"] else ""
        add("block", "text_overlap",
            f"{where}文字が重なっている: 「{ov['a']}」と「{ov['b']}」が {ov['share']:.0%} 重複 "
            f"({ov['sel']} / {ov['sel2']})。座標指定を直すか、ラベルを図の外へ出す。",
            selector=ov["sel"])

    # --- 図 (インラインSVG / ラスタ画像)
    W_area = W * H
    for fig in data.get("figures", []):
        area_share = (fig["w"] * fig["h"]) / W_area
        if fig["kind"] == "svg":
            if fig["escaped"]:
                add("block", "figure_clipped",
                    f"{fig['sel']} の中の {fig['escaped']}要素が図の枠から出ている。"
                    "SVGは枠外を描かないので、その分は消えている。viewBox を広げるか座標を直す。",
                    selector=fig["sel"])
            if not fig["viewBox"]:
                add("review", "figure_no_viewbox",
                    f"{fig['sel']} に viewBox がない。拡大縮小で比率が崩れる。", selector=fig["sel"])
            if not fig["named"] and not fig["hidden"]:
                add("review", "figure_unnamed",
                    f"{fig['sel']} に <title> も aria-label もない。図が主張を持つなら名前を付ける "
                    "(純粋な装飾なら aria-hidden=\"true\")。", selector=fig["sel"])
            if fig["minInset"] is not None and fig["minInset"] < gates["figure_inset_px"]:
                add("review", "figure_tight_margin",
                    f"{fig['sel']} の要素が枠から {fig['minInset']:.0f}px しか離れていない。"
                    f"{gates['figure_inset_px']}px は空けないと、縁に触れて切れて見える。",
                    selector=fig["sel"])
            if fig["minStroke"] is not None and fig["minStroke"] < gates["figure_min_stroke_px"]:
                add("review", "figure_hairline",
                    f"{fig['sel']} に実効 {fig['minStroke']}px の線がある。"
                    f"{gates['figure_min_stroke_px']}px 未満は投影とPDFで消える。", selector=fig["sel"])
        else:
            if not fig["naturalW"]:
                add("block", "image_not_loaded",
                    f"{fig['sel']} の画像が読み込めていない ({fig['src']})。", selector=fig["sel"])
                continue
            need = fig["w"] * gates["image_min_scale"]
            if fig["naturalW"] < need:
                sev = "block" if fig["naturalW"] < fig["w"] else "review"
                add(sev, "image_low_res",
                    f"{fig['sel']} は {fig['naturalW']}px の画像を {fig['w']:.0f}px で表示している。"
                    f"1600x900では表示幅の{gates['image_min_scale']}倍以上ないと粗く見える。",
                    selector=fig["sel"])
            if fig["objectFit"] in ("fill", "") and fig["naturalH"]:
                want = fig["naturalW"] / fig["naturalH"]
                got = fig["w"] / fig["h"] if fig["h"] else want
                if want and abs(got / want - 1) > 0.02:
                    add("review", "image_distorted",
                        f"{fig['sel']} の縦横比が元画像と {abs(got / want - 1):.0%} ずれている。"
                        "潰れて見えるので object-fit か寸法を直す。", selector=fig["sel"])
            if fig["alt"] is None:
                add("review", "image_no_alt",
                    f"{fig['sel']} に alt がない。装飾なら alt=\"\" を明示する。", selector=fig["sel"])
        if area_share > 0.02:
            findings.append({"severity": "info", "code": "figure_size",
                             "message": f"{fig['sel']} は画面の {area_share:.0%} "
                                        f"({fig['w']:.0f}x{fig['h']:.0f})"})

    # --- パレット逸脱 (共有CSSが見つかったときだけ判定する)
    if theme_css.strip():
        palette = token_palette(theme_css)
        drift = {}
        for use in data["colorUse"]:
            rgb = tuple(use["rgb"])
            if not near_palette(rgb, palette):
                key = "#%02x%02x%02x" % rgb
                drift.setdefault(key, []).append(f"{use['sel']}({use['role']})")
        for hexv, where in sorted(drift.items()):
            add("review", "palette_drift",
                f"{hexv} は theme.css のトークンにない色。{len(where)}箇所 (例 {where[0]})。"
                "デッキの声が分裂するのでトークンに寄せるか、theme側に追加して全枚で共有する。")
    else:
        add("info", "no_shared_css", "共有CSSを解決できなかったため、パレット検査を飛ばした。")

    counts = {"block": 0, "review": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] += 1

    return {
        "slide": slide_id,
        "title": data["title"],
        "headline": data["headings"][0]["text"] if data["headings"] else "",
        "metrics": {
            "ja_chars": ja,
            "en_words": en_words,
            "font_sizes": distinct,
            "max_font_px": max_size,
            "body_font_px": median_body,
            "min_body_font_px": min_body,
            "body_basis": body_basis,
            "hierarchy_ratio": round(ratio_h, 2),
            "text_area_ratio": round(area_ratio, 3),
            "bullets": data["bullets"],
            "families": data["families"],
        },
        "counts": counts,
        "findings": findings,
    }


# ---------------------------------------------------------------- ビューア同期

VIEWER_MARK_START = "// <slides>"
VIEWER_MARK_END = "// </slides>"


def sync_viewer(deck: Path, slides: list[tuple[Path, str]]) -> bool:
    index = deck / "index.html"
    if not index.exists():
        return False
    src = index.read_text(encoding="utf-8")
    if VIEWER_MARK_START not in src:
        return False
    body = ",\n".join(
        f'      ["slides/{p.name}", {json.dumps(title, ensure_ascii=False)}]' for p, title in slides
    )
    block = f"{VIEWER_MARK_START}\n    const slides = [\n{body}\n    ];\n    {VIEWER_MARK_END}"
    new = re.sub(
        re.escape(VIEWER_MARK_START) + r".*?" + re.escape(VIEWER_MARK_END),
        lambda _: block,
        src,
        flags=re.S,
    )
    if new != src:
        index.write_text(new, encoding="utf-8")
        return True
    return False


def check_viewer(page, deck: Path) -> list[dict]:
    """ビューア越しに開いたときも共有CSSが効いているかを確かめる。

    スライドを単体で開く検査だけでは、配布経路の欠陥を見逃す。実際に
    `sandbox`(値なし) が iframe を不透明オリジンにし、スライド側CSPの 'self' が
    一致しなくなって theme.css が丸ごと遮断される、という事故が起きた。
    素のHTMLが表示されるだけでコンソールにも出ないので、開いて確かめるしかない。
    """
    index = deck / "index.html"
    if not index.exists():
        return []
    page.goto(index.as_uri())
    page.wait_for_load_state("load")
    page.wait_for_timeout(500)

    frames = [f for f in page.frames if f is not page.main_frame]
    if not frames:
        return [{"severity": "review", "code": "viewer_no_frame",
                 "message": "index.html でスライドのiframeを確認できなかった。スライド一覧が空の可能性。"}]
    try:
        got = frames[0].evaluate(
            """() => {
              const cs = getComputedStyle(document.documentElement);
              const names = ['--ink','--paper','--bg','--body','--display','--accent'];
              return {
                tokenResolved: names.some((n) => cs.getPropertyValue(n).trim() !== ''),
                links: document.querySelectorAll('link[rel~="stylesheet"]').length,
                bodyWidth: document.body ? document.body.getBoundingClientRect().width : 0,
              };
            }"""
        )
    except Exception as exc:  # noqa: BLE001 - 握りつぶさず所見として返す
        return [{"severity": "review", "code": "viewer_unreadable",
                 "message": f"ビューア内のスライドを検査できなかった: {exc}"}]

    out = []
    if got["links"] and not got["tokenResolved"]:
        out.append({"severity": "block", "code": "viewer_style_blocked",
                    "message": "ビューア越しに開くと共有CSSが適用されていない。iframe の sandbox が"
                               "不透明オリジンを作り、スライド側CSPの 'self' が一致しなくなっている。"
                               'sandbox="allow-same-origin" を付ける (allow-scripts は付けない)。'})
    if got["bodyWidth"] and abs(got["bodyWidth"] - 1600) > 2:
        out.append({"severity": "review", "code": "viewer_canvas_mismatch",
                    "message": f"ビューア内のスライド幅が {got['bodyWidth']:.0f}px。"
                               "1600px でないと等倍縮小の前提が崩れる。"})
    return out


CONTACT_TPL = """<!doctype html><meta charset="utf-8">
<style>
 body{{margin:0;background:#0d1420;font:12px/1.4 -apple-system,sans-serif;color:#cfe0f5;padding:16px}}
 .grid{{display:grid;grid-template-columns:repeat({cols},1fr);gap:14px}}
 figure{{margin:0}} img{{width:100%;display:block;border:1px solid #2a3a52}}
 figcaption{{padding:5px 2px;font-weight:700;color:#9fb6d4}}
 .bad{{outline:3px solid #ff5f56}}
</style><div class="grid">{cells}</div>"""


def build_contact_sheet(page, shots: list[tuple[str, Path, bool]], out: Path, cols=3):
    cells = []
    for label, png, bad in shots:
        b64 = base64.b64encode(png.read_bytes()).decode()
        cls = ' class="bad"' if bad else ""
        cells.append(
            f'<figure><img{cls} src="data:image/png;base64,{b64}">'
            f"<figcaption>{label}</figcaption></figure>"
        )
    # full_page は内容に合わせて伸びるので、viewport は低くしておく。
    # 高くすると余った分がそのまま背景色の帯として画像に残る。
    page.set_viewport_size({"width": 1500, "height": 200})
    page.set_content(CONTACT_TPL.format(cols=cols, cells="".join(cells)))
    page.screenshot(path=str(out), full_page=True)


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path, help="デッキのディレクトリ (index.html と slides/ がある場所)")
    ap.add_argument("--round", type=int, default=None, help="ラウンド番号。省略時は自動採番")
    ap.add_argument("--slide", action="append", default=None, help="特定スライドだけ検査 (例 --slide 03)")
    ap.add_argument("--gates", type=Path, default=DEFAULT_GATES)
    ap.add_argument("--no-shots", action="store_true", help="スクリーンショットを撮らない (高速)")
    args = ap.parse_args()

    deck = args.deck.resolve()
    slide_dir = deck / "slides"
    if not slide_dir.is_dir():
        print(f"slides/ が見つからない: {slide_dir}", file=sys.stderr)
        return 2

    files = sorted(p for p in slide_dir.glob("*.html"))
    if args.slide:
        files = [p for p in files if any(s in p.name for s in args.slide)]
    if not files:
        print("検査対象のスライドがない", file=sys.stderr)
        return 2

    gates = json.loads(args.gates.read_text(encoding="utf-8"))
    W, H = gates["canvas"]["width"], gates["canvas"]["height"]

    loop_dir = deck / ".loop"
    if args.round is None:
        existing = [int(m.group(1)) for p in loop_dir.glob("round-*") if (m := re.match(r"round-(\d+)$", p.name))]
        rnd = max(existing) + 1 if existing else 1
    else:
        rnd = args.round
    out_dir = loop_dir / f"round-{rnd}"
    shot_dir = out_dir / "shots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    results = []
    titles = []
    shots = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            reduced_motion="reduce",  # 入場アニメの途中を撮らない
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        for f in files:
            page.goto(f.as_uri())
            page.wait_for_load_state("load")
            page.wait_for_timeout(120)
            data = page.evaluate(EXTRACT_JS)
            theme_css = collect_theme_css(f, data.get("styleHrefs", []))
            res = evaluate(data, gates, f.read_text(encoding="utf-8"), f.stem, theme_css)
            if not args.no_shots:
                png = shot_dir / f"{f.stem}.png"
                page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": W, "height": H})
                res["screenshot"] = str(png.relative_to(deck))
                shots.append((f.stem, png, res["counts"]["block"] > 0))
            results.append(res)
            titles.append((f, data["title"] or f.stem))

        # スライド一覧を先に同期してから、実際の配布経路 (ビューア) を開いて確かめる。
        synced = sync_viewer(deck, titles)
        deck_findings = check_viewer(page, deck)

        if shots:
            build_contact_sheet(page, shots, out_dir / "contact-sheet.png")
        browser.close()

    total = {"block": 0, "review": 0, "info": 0}
    for r in results:
        for k in total:
            total[k] += r["counts"][k]
    for f in deck_findings:
        total[f["severity"]] += 1

    report = {
        "round": rnd,
        "deck": str(deck),
        "gates": gates,
        "totals": total,
        "viewer_synced": synced,
        "deck_findings": deck_findings,
        "contact_sheet": "contact-sheet.png" if shots else None,
        "slides": results,
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- 標準出力サマリ
    print(f"\nround {rnd}  —  {len(results)}枚  block {total['block']} / review {total['review']} / info {total['info']}")
    print(f"report: {out_dir / 'report.json'}")
    if shots:
        print(f"shots : {shot_dir}  (contact-sheet.png)")
    print()

    if deck_findings:
        print("  デッキ全体 (配布経路の検査):")
        for f in deck_findings:
            print(f"        {f['severity']:<6} {f['code']:<22} {f['message']}")
        print()

    # 同じ code が枚をまたいで出ているときは、原因が共有CSSか共通の作りにある。
    # 1枚ずつ直すと同じ修正をN回することになるので、先に気づけるよう出しておく。
    spread: dict[str, set] = {}
    for r in results:
        for f in r["findings"]:
            if f["severity"] != "info":
                spread.setdefault(f["code"], set()).add(r["slide"])
    wide = {c: s for c, s in spread.items() if len(s) >= max(3, len(results) * 0.6)}
    if wide:
        print("  横断: 次は多くの枚で同時に出ている。原因は theme.css か共通の作りにある可能性が高い。")
        for code, hit in sorted(wide.items(), key=lambda kv: -len(kv[1])):
            print(f"        {code:<18} {len(hit)}/{len(results)}枚")
        print()

    # 所見は code ごとにまとめて出す。全件そのまま流すと、読む側の枠が
    # 同じ指摘の繰り返しで埋まり、優先度が判断できなくなる。
    for r in results:
        m = r["metrics"]
        flag = "BLOCK" if r["counts"]["block"] else ("review" if r["counts"]["review"] else "ok   ")
        print(f"  [{flag}] {r['slide']:<22} 本文最小{m['min_body_font_px']:>4.0f}px 階層{m['hierarchy_ratio']:>5.2f}x "
              f"和{m['ja_chars']:>4}字 占有{m['text_area_ratio']:.0%}  {r['headline'][:34]}")
        grouped: dict[tuple[str, str], list[dict]] = {}
        for fnd in r["findings"]:
            if fnd["severity"] == "info":
                continue
            grouped.setdefault((fnd["severity"], fnd["code"]), []).append(fnd)
        order = {"block": 0, "review": 1}
        for (sev, code), items in sorted(grouped.items(), key=lambda kv: (order[kv[0][0]], kv[0][1])):
            head = items[0]["message"]
            extra = f"  (+{len(items) - 1}件)" if len(items) > 1 else ""
            print(f"        {sev:<6} {code:<18} {head}{extra}")
    print("\n詳細と全件は report.json。修正は block → review の順で、"
          "1件ずつ直して再検査する。まとめて直すと何が効いたか分からなくなる。\n")
    return 1 if total["block"] else 0


if __name__ == "__main__":
    sys.exit(main())
