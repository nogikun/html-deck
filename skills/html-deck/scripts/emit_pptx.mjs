#!/usr/bin/env node

import fs from "node:fs";
import { fileURLToPath } from "node:url";
import PptxGenJS from "pptxgenjs";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 1) {
  if (process.argv[i].startsWith("--")) args.set(process.argv[i], process.argv[++i]);
}

const input = args.get("--input");
const output = args.get("--output");
if (!input || !output) {
  console.error("usage: emit_pptx.mjs --input deck-ir.json --output deck.pptx");
  process.exit(2);
}

const ir = JSON.parse(fs.readFileSync(input, "utf8"));
const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "html-deck";
pptx.subject = "HTML deck export";
pptx.title = ir.title || "HTML deck";

const INCH = 120;
const POINTS_PER_CSS_PX = 72 / INCH;
const box = (item) => ({
  x: item.x / INCH,
  y: item.y / INCH,
  w: item.w / INCH,
  h: item.h / INCH,
});

const toTransparency = (alpha) => Math.max(0, Math.min(100, Math.round((1 - alpha) * 100)));

function fillOptions(fill) {
  if (!fill || fill.alpha <= 0.01) return { color: "FFFFFF", transparency: 100 };
  return { color: fill.hex, transparency: toTransparency(fill.alpha) };
}

function lineOptions(line) {
  if (!line || line.alpha <= 0.01 || line.width <= 0) {
    return { color: "FFFFFF", transparency: 100, width: 0 };
  }
  return {
    color: line.hex,
    transparency: toTransparency(line.alpha),
    width: Math.max(0.25, line.width * POINTS_PER_CSS_PX),
  };
}

function textRuns(item) {
  const runs = [];
  for (const run of item.runs || [{ text: item.text || "", ...item.style }]) {
    const parts = String(run.text ?? "").split("\n");
    parts.forEach((text, index) => {
      if (text || parts.length === 1) {
        runs.push({
          text,
          options: {
            fontFace: run.fontFace,
            fontSize: run.fontSize * POINTS_PER_CSS_PX,
            color: run.color,
            bold: run.fontWeight >= 600,
            italic: run.italic,
            charSpacing: run.charSpacing || undefined,
            breakLine: index < parts.length - 1,
          },
        });
      } else if (index < parts.length - 1) {
        runs.push({ text: "", options: { breakLine: true } });
      }
    });
  }
  return runs.length ? runs : [{ text: "", options: {} }];
}

function textOptions(item) {
  const opts = {
    ...box(item),
    margin: 0,
    align: "left",
    valign: "top",
    wrap: false,
    fit: "none",
  };
  if (item.shapeType) {
    opts.shape = pptx.ShapeType[item.shapeType] || item.shapeType;
    opts.fill = fillOptions(item.fill);
    opts.line = lineOptions(item.line);
  }
  return opts;
}

function addText(slide, item) {
  slide.addText(textRuns(item), textOptions(item));
}

function addShape(slide, item) {
  slide.addShape(pptx.ShapeType[item.shapeType] || item.shapeType, {
    ...box(item),
    fill: fillOptions(item.fill),
    line: lineOptions(item.line),
  });
}

for (const page of ir.slides) {
  const slide = pptx.addSlide();
  slide.background = { color: page.background.hex };

  for (const item of page.items) {
    if (item.kind === "text") {
      addText(slide, item);
    } else if (item.kind === "shape" || item.kind === "line") {
      addShape(slide, item);
    } else if (item.kind === "svg") {
      slide.addImage({ data: item.data, ...box(item) });
    } else if (item.kind === "image") {
      const src = item.src.startsWith("file:") ? fileURLToPath(item.src) : item.src;
      slide.addImage({ path: src, ...box(item) });
    } else {
      throw new Error(`Unsupported DeckIR item: ${item.kind}`);
    }
  }
}

await pptx.writeFile({ fileName: output });
console.log(`${ir.slides.length}枚 → ${output}`);
