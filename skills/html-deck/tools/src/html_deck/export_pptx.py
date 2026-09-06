#!/usr/bin/env python3
"""既存のHTMLスライドを実測し、PptxGenJSの編集可能な部品へ変換する。

使い方 (事前のインストールは要らない。初回だけ自分でランタイムを作る):
    uvx --from <このスキルのディレクトリ>/tools html-deck-pptx <deck-dir>
    uvx --from <このスキルのディレクトリ>/tools html-deck-pptx <deck-dir> -o output.pptx

変換対象は TextLine / Shape / Line / Table / SVG / Image の最小集合。CSSレイアウトはChromeに解決させ、
PptxGenJSには計算済みの矩形だけを渡す。SVGは1つのSVG画像として保持する。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


from .setup_export_runtime import ensure_node

SCRIPT_DIR = Path(__file__).resolve().parent
EMITTER = SCRIPT_DIR / "emit_pptx.mjs"
CANVAS = {"width": 1600, "height": 900}


EXTRACT_IR_JS = r"""
() => {
  const root = document.querySelector("article.slide") || document.body;
  const parseColor = (value) => {
    const m = String(value || "").match(/rgba?\(([^)]+)\)/);
    if (!m) return { hex: "FFFFFF", alpha: 0 };
    const parts = m[1].split(",").map((part) => parseFloat(part.trim()));
    const alpha = parts.length > 3 ? parts[3] : 1;
    const hex = parts.slice(0, 3).map((part) => Math.max(0, Math.min(255, Math.round(part)))
      .toString(16).padStart(2, "0")).join("").toUpperCase();
    return { hex, alpha };
  };
  const visible = (el, rect) => {
    const cs = getComputedStyle(el);
    return cs.display !== "none" && cs.visibility !== "hidden" && parseFloat(cs.opacity || "1") > 0.01
      && rect.width > 0 && rect.height > 0;
  };
  const firstFont = (font) => String(font || "system-ui").split(",")[0].trim().replace(/^['"]|['"]$/g, "");
  const rectOf = (el) => {
    const r = el.getBoundingClientRect();
    return { x: +r.x.toFixed(2), y: +r.y.toFixed(2), w: +r.width.toFixed(2), h: +r.height.toFixed(2) };
  };
  const borderOf = (cs, side) => ({
    ...parseColor(cs[`border${side}Color`]),
    width: parseFloat(cs[`border${side}Width`] || "0"),
    style: cs[`border${side}Style`] || "none",
  });
  const textStyleOf = (el) => {
    const cs = getComputedStyle(el);
    const color = parseColor(cs.color);
    return {
      fontFace: firstFont(cs.fontFamily),
      fontSize: parseFloat(cs.fontSize || "16"),
      fontWeight: parseInt(cs.fontWeight || "400", 10) || 400,
      italic: cs.fontStyle === "italic",
      color: color.hex,
      align: cs.textAlign === "start" ? "left" : cs.textAlign,
      valign: "top",
      lineHeight: cs.lineHeight === "normal" ? parseFloat(cs.fontSize || "16") * 1.2 : parseFloat(cs.lineHeight),
      charSpacing: cs.letterSpacing === "normal" ? 0 : parseFloat(cs.letterSpacing || "0") * (72 / 120),
      whiteSpace: cs.whiteSpace,
    };
  };
  const paintStyleOf = (el) => {
    const cs = getComputedStyle(el);
    return {
      fill: parseColor(cs.backgroundColor),
      backgroundImage: cs.backgroundImage,
      radius: parseFloat(cs.borderTopLeftRadius || "0"),
      borders: {
        top: borderOf(cs, "Top"),
        right: borderOf(cs, "Right"),
        bottom: borderOf(cs, "Bottom"),
        left: borderOf(cs, "Left"),
      },
    };
  };
  const shapeType = (rect, style) => {
    if (Math.abs(rect.w - rect.h) <= 2 && style.radius >= Math.min(rect.w, rect.h) / 2) return "ellipse";
    if (style.radius > 0) return "roundRect";
    return "rect";
  };
  const hasPaint = (style) => {
    const hasFill = style.fill.alpha > 0.01;
    const hasBorder = Object.values(style.borders).some((border) => border.alpha > 0.01 && border.width > 0 && border.style !== "none");
    return hasFill || hasBorder;
  };
  const hasDirectText = (el) => [...el.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.nodeValue.trim());
  const isTextRoot = (el) => el.dataset.pptxKind === "text" || hasDirectText(el);
  const graphemes = (text) => {
    if (globalThis.Intl?.Segmenter) return [...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)].map((part) => ({ text: part.segment, index: part.index }));
    let index = 0;
    return [...text].map((part) => {
      const item = { text: part, index };
      index += part.length;
      return item;
    });
  };
  const styleKey = (style) => [style.fontFace, style.fontSize, style.fontWeight, style.italic, style.color, style.charSpacing].join("|");
  const collectTextLines = (el) => {
    const lines = [];
    let current = [];
    const pushLine = () => {
      if (current.some((char) => char.text.trim() || char.text === "　")) lines.push(current);
      current = [];
    };
    const visit = (node, inherited) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const raw = node.nodeValue || "";
        const preserve = /^pre/.test(inherited.whiteSpace || "");
        let previousWasSpace = false;
        for (const part of graphemes(raw)) {
          const isSpace = !preserve && /\s/.test(part.text);
          if (isSpace && previousWasSpace) continue;
          previousWasSpace = isSpace;
          const text = isSpace ? " " : part.text;
          const range = document.createRange();
          range.setStart(node, part.index);
          range.setEnd(node, part.index + part.text.length);
          const rect = [...range.getClientRects()].find((candidate) => candidate.width > 0 && candidate.height > 0);
          if (!rect) continue;
          const last = current[current.length - 1];
          if (last && Math.abs(rect.top - last.rect.top) > 1) pushLine();
          current.push({ text, rect, style: inherited });
        }
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      if (node.tagName.toLowerCase() === "br") {
        pushLine();
        return;
      }
      const style = textStyleOf(node);
      for (const child of node.childNodes) visit(child, style);
    };
    const rootStyle = textStyleOf(el);
    for (const child of el.childNodes) visit(child, rootStyle);
    pushLine();
    return lines.map((chars) => {
      while (chars.length && !chars[0].text.trim() && chars[0].text !== "　") chars.shift();
      while (chars.length && !chars.at(-1).text.trim() && chars.at(-1).text !== "　") chars.pop();
      if (!chars.length) return null;
      const runs = [];
      for (const char of chars) {
        const previous = runs.at(-1);
        if (previous && styleKey(previous) === styleKey(char.style)) previous.text += char.text;
        else runs.push({ text: char.text, ...char.style });
      }
      const x = Math.min(...chars.map((char) => char.rect.left));
      const y = Math.min(...chars.map((char) => char.rect.top));
      const right = Math.max(...chars.map((char) => char.rect.right));
      const bottom = Math.max(...chars.map((char) => char.rect.bottom));
      const lineHeight = Math.max(...chars.map((char) => char.style.lineHeight || char.rect.height));
      return { kind: "text", id: el.dataset.pptxId || "", x, y, w: Math.max(1, right - x), h: Math.max(lineHeight, bottom - y), runs };
    }).filter((line) => line && line.runs.length);
  };
  const tableBorderOf = (cs, side) => {
    const border = borderOf(cs, side);
    return {
      hex: border.hex,
      alpha: border.alpha,
      width: border.width,
      style: border.style,
      type: border.style === "dashed" || border.style === "dotted" ? "dash" : border.style === "none" ? "none" : "solid",
    };
  };
  const tableCellOf = (cell, meta) => {
    const cs = getComputedStyle(cell);
    const style = textStyleOf(cell);
    const lines = collectTextLines(cell);
    const runs = lines.flatMap((line, lineIndex) => line.runs.map((run, runIndex) => ({
      ...run,
      breakLine: lineIndex < lines.length - 1 && runIndex === line.runs.length - 1,
    })));
    const text = lines.map((line) => line.runs.map((run) => run.text).join("")).join("\n");
    return {
      text,
      runs,
      fill: parseColor(cs.backgroundColor),
      border: [
        tableBorderOf(cs, "Top"),
        tableBorderOf(cs, "Right"),
        tableBorderOf(cs, "Bottom"),
        tableBorderOf(cs, "Left"),
      ],
      fontFace: style.fontFace,
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      italic: style.italic,
      color: style.color,
      align: ["left", "center", "right"].includes(style.align) ? style.align : "left",
      valign: { top: "top", middle: "middle", bottom: "bottom" }[cs.verticalAlign] || "top",
      lineHeight: style.lineHeight,
      charSpacing: style.charSpacing,
      margin: ["Top", "Right", "Bottom", "Left"].map((side) => parseFloat(cs[`padding${side}`] || "0")),
      colspan: meta.colspan > 1 ? meta.colspan : undefined,
      rowspan: meta.rowspan > 1 ? meta.rowspan : undefined,
    };
  };
  const tableItemOf = (table, rect) => {
    const rows = [...table.rows];
    const occupied = [];
    const placements = new Map();
    let columnCount = 0;
    for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
      occupied[rowIndex] ||= [];
      let column = 0;
      for (const cell of rows[rowIndex].cells) {
        while (occupied[rowIndex][column]) column += 1;
        const colspan = Math.max(1, cell.colSpan || 1);
        const rowspan = cell.rowSpan === 0 ? rows.length - rowIndex : Math.max(1, cell.rowSpan || 1);
        placements.set(cell, { row: rowIndex, col: column, colspan, rowspan });
        for (let r = rowIndex; r < rowIndex + rowspan; r += 1) {
          occupied[r] ||= [];
          for (let c = column; c < column + colspan; c += 1) occupied[r][c] = true;
        }
        column += colspan;
        columnCount = Math.max(columnCount, column);
      }
    }
    const edges = Array(columnCount + 1).fill(null);
    edges[0] = 0;
    edges[columnCount] = rect.w;
    const setEdge = (index, value) => {
      if (edges[index] == null) edges[index] = value;
      else edges[index] = (edges[index] + value) / 2;
    };
    for (const [cell, meta] of placements) {
      const cellRect = cell.getBoundingClientRect();
      setEdge(meta.col, cellRect.left - rect.x);
      setEdge(meta.col + meta.colspan, cellRect.right - rect.x);
    }
    for (let start = 0; start < edges.length;) {
      if (edges[start] != null) {
        start += 1;
        continue;
      }
      const left = start - 1;
      let end = start;
      while (end < edges.length && edges[end] == null) end += 1;
      const right = edges[end] ?? rect.w;
      const step = (right - edges[left]) / (end - left);
      for (let i = start; i < end; i += 1) edges[i] = edges[left] + step * (i - left);
      start = end;
    }
    const rowH = rows.map((row) => row.getBoundingClientRect().height);
    const tableRows = rows.map((row) => [...row.cells].map((cell) => tableCellOf(cell, placements.get(cell))));
    const cs = getComputedStyle(table);
    return {
      kind: "table",
      id: table.dataset.pptxId || "",
      ...rect,
      colW: edges.slice(1).map((edge, index) => Math.max(1, edge - edges[index])),
      rowH,
      rows: tableRows,
      fill: parseColor(cs.backgroundColor),
      border: [
        tableBorderOf(cs, "Top"),
        tableBorderOf(cs, "Right"),
        tableBorderOf(cs, "Bottom"),
        tableBorderOf(cs, "Left"),
      ],
    };
  };
  const paintItems = (el, rect, style) => {
    const items = [];
    if (style.backgroundImage && style.backgroundImage !== "none") {
      warnings.push({ type: "background-image", selector: el.className || el.tagName.toLowerCase(), value: style.backgroundImage });
    }
    if (style.fill.alpha > 0.01) {
      items.push({ kind: "shape", id: el.dataset.pptxId || "", ...rect, shapeType: shapeType(rect, style), fill: style.fill, line: { hex: "FFFFFF", alpha: 0, width: 0 } });
    }
    const sides = [
      ["top", rect.x, rect.y, rect.w, 0],
      ["right", rect.x + rect.w, rect.y, 0, rect.h],
      ["bottom", rect.x, rect.y + rect.h, rect.w, 0],
      ["left", rect.x, rect.y, 0, rect.h],
    ];
    for (const [side, x, y, w, h] of sides) {
      const border = style.borders[side];
      if (!border || border.width <= 0 || border.style === "none" || border.alpha <= 0.01) continue;
      items.push({ kind: "line", id: `${el.dataset.pptxId || ""}-${side}`, x, y, w, h, shapeType: "line", line: border, fill: { hex: "FFFFFF", alpha: 0 } });
    }
    return items;
  };
  const svgData = (svg) => {
    const clone = svg.cloneNode(true);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    // PowerPoint does not load the source page's <style> into an SVG image.
    // Copy the computed SVG properties inline so class/variable-based artwork
    // keeps its colors instead of falling back to SVG's default black.
    const svgProperties = [
      "fill", "fill-opacity", "stroke", "stroke-opacity", "stroke-width",
      "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset",
      "opacity", "font-family", "font-size", "font-weight", "font-style",
      "letter-spacing", "text-anchor", "dominant-baseline",
    ];
    const sourceNodes = [svg, ...svg.querySelectorAll("*")];
    const targetNodes = [clone, ...clone.querySelectorAll("*")];
    sourceNodes.forEach((source, index) => {
      const target = targetNodes[index];
      const style = getComputedStyle(source);
      for (const property of svgProperties) {
        const value = style.getPropertyValue(property);
        if (value) target.setAttribute(property, value);
      }
    });
    const viewBox = svg.viewBox?.baseVal;
    if (viewBox?.width > 0 && viewBox?.height > 0) {
      clone.setAttribute("preserveAspectRatio", clone.getAttribute("preserveAspectRatio") || "xMidYMid meet");
      clone.setAttribute("width", clone.getAttribute("width") || String(viewBox.width));
      clone.setAttribute("height", clone.getAttribute("height") || String(viewBox.height));
    }
    const tokenValues = {};
    for (const name of ["--bg", "--surface", "--ink", "--muted", "--line", "--accent", "--accent-2", "--display", "--body", "--mono"]) {
      tokenValues[name] = getComputedStyle(root).getPropertyValue(name).trim().replaceAll('"', "");
    }
    let markup = clone.outerHTML;
    markup = markup.replace(/var\(\s*(--[\w-]+)(?:\s*,[^)]*)?\)/g, (_, name) => tokenValues[name] || "currentColor");
    return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(markup)))}`;
  };
  const items = [];
  const warnings = [];
  const visit = (el) => {
    if (!(el instanceof Element) || el === root) {
      for (const child of el.children || []) visit(child);
      return;
    }
    const tag = el.tagName.toLowerCase();
    const rect = rectOf(el);
    if (!visible(el, el.getBoundingClientRect())) return;
    if (tag === "svg") {
      const viewBox = el.viewBox?.baseVal;
      const svgRect = { ...rect };
      if (viewBox?.width > 0 && viewBox?.height > 0) {
        const scale = Math.min(svgRect.w / viewBox.width, svgRect.h / viewBox.height);
        const width = +(viewBox.width * scale).toFixed(2);
        const height = +(viewBox.height * scale).toFixed(2);
        svgRect.x = +(svgRect.x + (svgRect.w - width) / 2).toFixed(2);
        svgRect.y = +(svgRect.y + (svgRect.h - height) / 2).toFixed(2);
        svgRect.w = width;
        svgRect.h = height;
      }
      items.push({ kind: "svg", id: el.dataset.pptxId || "", ...svgRect, data: svgData(el) });
      return;
    }
    if (tag === "img") {
      items.push({ kind: "image", id: el.dataset.pptxId || "", ...rect, src: el.currentSrc || el.src });
      return;
    }
    if (tag === "table") {
      items.push(tableItemOf(el, rect));
      return;
    }
    const paintStyle = paintStyleOf(el);
    if (hasPaint(paintStyle)) items.push(...paintItems(el, rect, paintStyle));
    if (isTextRoot(el)) {
      items.push(...collectTextLines(el));
      return;
    }
    for (const child of el.children) visit(child);
  };
  for (const child of root.children) visit(child);
  const backgroundOf = (el) => {
    for (let node = el; node; node = node.parentElement) {
      const color = parseColor(getComputedStyle(node).backgroundColor);
      if (color.alpha > 0.01) return color;
    }
    return { hex: "FFFFFF", alpha: 1 };
  };
  const background = backgroundOf(root);
  return {
    title: document.title,
    width: root.getBoundingClientRect().width,
    height: root.getBoundingClientRect().height,
    background,
    warnings,
    items,
  };
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--node", default="node", help="Node.js executable")
    parser.add_argument(
        "--browser",
        default=os.environ.get("HTML_DECK_BROWSER"),
        help="Chrome/Chromium executable path (or set HTML_DECK_BROWSER)",
    )
    parser.add_argument("--write-ir", type=Path, help="also keep the generated DeckIR JSON")
    return parser.parse_args()


def resolve_node(command: str) -> str:
    """Resolve a command without relying on the shell or its working directory."""
    candidate = Path(command).expanduser()
    if not candidate.is_absolute() and candidate.name.lower() in {
        "node", "node.exe", "nodejs", "nodejs.exe",
    }:
        resolved = shutil.which(command)
        if resolved:
            return resolved
        raise RuntimeError("Node.js が見つかりません。Node.js をインストールするか --node で指定してください")
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise RuntimeError(f"Node.js 実行ファイルがありません: {resolved}")
    return str(resolved)


def launch_browser(playwright, executable: str | None):
    """Prefer the installed Chrome, then a locally installed Playwright browser."""
    if executable:
        path = Path(executable).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"Chrome/Chromium 実行ファイルがありません: {path}")
        return playwright.chromium.launch(executable_path=str(path), headless=True)

    try:
        return playwright.chromium.launch(channel="chrome", headless=True)
    except Exception as chrome_error:  # noqa: BLE001 - fallback is the compatibility path
        bundled = Path(playwright.chromium.executable_path)
        if not bundled.is_file():
            raise RuntimeError(
                "Chrome を起動できませんでした。Google Chrome をインストールするか、"
                "--browser で Chrome/Chromium の実行ファイルを指定してください"
            ) from chrome_error
        try:
            return playwright.chromium.launch(executable_path=str(bundled), headless=True)
        except Exception as bundled_error:  # noqa: BLE001 - retain a short actionable error
            raise RuntimeError(
                "Chrome/Chromium を起動できませんでした。"
                "--browser で別の実行ファイルを指定してください"
            ) from bundled_error


def main() -> int:
    args = parse_args()
    deck = args.deck.resolve()
    slides_dir = deck / "slides"
    files = sorted(slides_dir.glob("*.html"))
    if not files:
        print(f"slides/*.html がありません: {slides_dir}", file=sys.stderr)
        return 2
    output = (args.output or deck / f"{deck.name}.pptx").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    pages = []
    with sync_playwright() as playwright:
        browser = launch_browser(playwright, args.browser)
        try:
            page = browser.new_page(
                viewport={"width": CANVAS["width"], "height": CANVAS["height"]},
                device_scale_factor=1,
                reduced_motion="reduce",
            )
            for slide in files:
                page.goto(slide.as_uri())
                page.wait_for_load_state("load")
                page.wait_for_timeout(120)
                page.evaluate("document.fonts.ready.then(() => true)")
                data = page.evaluate(EXTRACT_IR_JS)
                if round(data["width"]) != CANVAS["width"] or round(data["height"]) != CANVAS["height"]:
                    raise RuntimeError(f"{slide.name}: canvas is {data['width']}x{data['height']}, expected 1600x900")
                pages.append({"source": str(slide), **data})
        finally:
            browser.close()

    ir = {"title": deck.name, "canvas": CANVAS, "slides": pages}
    if args.write_ir:
        args.write_ir.parent.mkdir(parents=True, exist_ok=True)
        args.write_ir.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")

    node = resolve_node(args.node)
    package_root = ensure_node(deck)

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as fh:
        json.dump(ir, fh, ensure_ascii=False)
        ir_path = Path(fh.name)
    try:
        subprocess.run(
            [node, str(EMITTER), "--input", str(ir_path), "--output", str(output),
             "--package-root", str(package_root)],
            cwd=str(package_root),
            check=True,
        )
    finally:
        ir_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
