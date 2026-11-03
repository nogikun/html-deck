"""描画プリミティブ — 図形・テキスト・共通部品。

python-pptx の API を、このテンプレートの語彙 (面・ピル・カード・帯) に
一段かぶせたもの。スライドの中身は slides.py 側にある。
"""

from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt

from tokens import (
    BAND_H, BODY_T, BODY_W, FOOT_Y, GREY_RULE, GREY_SUB,
    MARGIN, RULE_H, RULE_Y, SLIDE_W, SZ, TOKENS, E, rgb,
)

# ---------------------------------------------------------------- 低レベル描画


def box(slide, x, y, w, h, fill=None, line=None, line_w=1.0, shape=MSO_SHAPE.RECTANGLE,
        radius=None):
    sp = slide.shapes.add_shape(shape, E(x), E(y), E(w), E(h))
    if fill:
        sp.fill.solid()
        sp.fill.fore_color.rgb = rgb(fill)
    else:
        sp.fill.background()
    if line:
        sp.line.color.rgb = rgb(line)
        sp.line.width = Pt(line_w)
    else:
        sp.line.fill.background()
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sp.adjustments[0] = radius
    sp.text_frame.word_wrap = True
    return sp


def text(slide, x, y, w, h, runs, size="body", color=None, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, font=None, line_spacing=1.35, space_after=0):
    """runs: str か [(text, {size/color/bold/font}), ...]"""
    tb = slide.shapes.add_textbox(E(x), E(y), E(w), E(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    base_size = SZ[size] if isinstance(size, str) else size
    base_color = color or TOKENS["dk1"]
    base_font = font or TOKENS["font_minor_ea"]

    paragraphs = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        if space_after:
            p.space_after = Pt(space_after)
        chunks = para if isinstance(para, list) else [(para, {})]
        for s, opt in chunks:
            r = p.add_run()
            r.text = s
            f = r.font
            sz = opt.get("size", base_size)
            f.size = Pt(SZ[sz] if isinstance(sz, str) else sz)
            f.bold = opt.get("bold", bold)
            f.color.rgb = rgb(opt.get("color", base_color))
            f.name = opt.get("font", base_font)
            _set_ea(r, opt.get("font", base_font), opt.get("latin"))
    return tb


def _set_ea(run, name, latin=None):
    """python-pptx は latin しか書かないので ea / cs を足す。"""
    rPr = run._r.get_or_add_rPr()
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    if latin:
        for el in rPr.findall(f"{ns}latin"):
            el.set("typeface", latin)
    for tag in ("ea", "cs"):
        for el in rPr.findall(f"{ns}{tag}"):
            rPr.remove(el)
        el = rPr.makeelement(f"{ns}{tag}", {"typeface": name})
        rPr.append(el)


def line_h(slide, x, y, w, color, width=1.0, dash=None):
    ln = slide.shapes.add_connector(1, E(x), E(y), E(x + w), E(y))  # 1 = straight
    ln.line.color.rgb = rgb(color)
    ln.line.width = Pt(width)
    if dash:
        ln.line._get_or_add_ln().append(
            ln.line._get_or_add_ln().makeelement(
                "{http://schemas.openxmlformats.org/drawingml/2006/main}prstDash",
                {"val": dash},
            )
        )
    return ln


# ---------------------------------------------------------------- 部品


def chrome(slide, title, page=None, band=None):
    """共通の枠の上に、そのスライドの文字だけを置く。

    帯・アクセント罫・フッター帯はスライドマスターが描くので、ここでは描かない。
    両方で描くと罫が 2 本に見える (マスターの矩形とスライドの線が数ミリずれる)。
    band にセクション色を渡したときだけ、その 1 枚でマスターの帯を塗り替える。
    """
    if band:
        box(slide, 0, 0, SLIDE_W, BAND_H, fill=band)
        box(slide, 0, RULE_Y, SLIDE_W, RULE_H, fill=TOKENS["accent1"])
    text(slide, MARGIN, 0, BODY_W, BAND_H, title, size="title", color=TOKENS["lt1"],
         bold=True, anchor=MSO_ANCHOR.MIDDLE, font=TOKENS["font_major"], line_spacing=1.0)
    text(slide, 0.25, FOOT_Y + 0.09, 3.0, 0.40, TOKENS["name"], size="note", color=GREY_SUB)
    text(slide, 4.42, FOOT_Y + 0.09, 4.5, 0.40, TOKENS["owner"], size="note", color=GREY_SUB,
         align=PP_ALIGN.CENTER)
    if page is not None:
        text(slide, 10.08, FOOT_Y + 0.09, 3.0, 0.40, str(page), size="note", color=GREY_SUB,
             align=PP_ALIGN.RIGHT)


def lead(slide, msg, y=BODY_T):
    """主張文 (ガバニングメッセージ)。本文の最上段に 1〜2 行で置く。"""
    return text(slide, MARGIN, y, BODY_W, 0.9, msg, size="lead", bold=True,
                align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.3)


def card(slide, x, y, w, h, heading, body, accent=None, icon_text=None, fill=None):
    """カードは面で置く。輪郭線は引かない (明度差だけで地と分ける)。"""
    accent = accent or TOKENS["accent1"]
    box(slide, x, y, w, h, fill=fill or TOKENS["lt2"],
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    cy = y + 0.26
    if icon_text:
        box(slide, x + 0.26, cy, 0.42, 0.42, fill=accent, shape=MSO_SHAPE.OVAL)
        text(slide, x + 0.26, cy + 0.07, 0.42, 0.3, icon_text, size=14, color="FFFFFF",
             bold=True, align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.0)
        hx = x + 0.80
    else:
        hx = x + 0.26
    text(slide, hx, cy + 0.02, w - (hx - x) - 0.26, 0.4, heading, size="small", bold=True,
         color=accent, font=TOKENS["font_major"], line_spacing=1.1)
    text(slide, x + 0.26, cy + 0.62, w - 0.52, h - 0.95, body, size=14, line_spacing=1.45)


def pill(slide, x, y, w, h, label, fill, color="FFFFFF", size=14):
    box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    text(slide, x, y + h / 2 - 0.13, w, 0.3, label, size=size, color=color, bold=True,
         align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.0)


def swatch(slide, x, y, w, h, hexv, slot, role):
    # 紙に近い色は枠がないと見えないので、明度が高いときだけ罫を足す
    light = sum(int(hexv[i:i + 2], 16) for i in (0, 2, 4)) / 3 > 228
    box(slide, x, y, w, h * 0.60, fill=hexv, line=GREY_RULE if light else None, line_w=0.75)
    text(slide, x, y + h * 0.60 + 0.06, w, 0.26, slot, size=13, bold=True,
         color=TOKENS["dk1"], font=TOKENS["font_major"], line_spacing=1.0)
    text(slide, x, y + h * 0.60 + 0.32, w, 0.26, "#" + hexv, size=12, color=GREY_SUB,
         font="Arial", line_spacing=1.0)
    text(slide, x, y + h * 0.60 + 0.56, w, 0.5, role, size=12, color=GREY_SUB, line_spacing=1.25)
