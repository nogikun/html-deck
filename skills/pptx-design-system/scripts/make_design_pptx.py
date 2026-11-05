"""design.pptx — プレゼン標準スタイル (デザインシステム) を組み立てる。

既存資料 4 本から抽出した配色・書体・グリッドを、PowerPoint が機能として
読める形 (テーマ配色 / テーマフォント / スライドマスター) に落とし、
同じ規約を人が読める形 (スライド 16 枚) で併記する。

    uv run --with python-pptx python scripts/make_design_pptx.py

配色やプロジェクト名を変えるときは下の TOKENS だけ書き換える。
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

from slides import build
from tokens import BAND_H, EMU_IN, FOOT_H, FOOT_Y, RULE_H, RULE_Y, SLIDE_W, TOKENS

# ---------------------------------------------------------------- テーマ差し替え

THEME_CLR = """<a:clrScheme name="{name}"><a:dk1><a:srgbClr val="{dk1}"/></a:dk1>\
<a:lt1><a:srgbClr val="{lt1}"/></a:lt1><a:dk2><a:srgbClr val="{dk2}"/></a:dk2>\
<a:lt2><a:srgbClr val="{lt2}"/></a:lt2><a:accent1><a:srgbClr val="{accent1}"/></a:accent1>\
<a:accent2><a:srgbClr val="{accent2}"/></a:accent2><a:accent3><a:srgbClr val="{accent3}"/></a:accent3>\
<a:accent4><a:srgbClr val="{accent4}"/></a:accent4><a:accent5><a:srgbClr val="{accent5}"/></a:accent5>\
<a:accent6><a:srgbClr val="{accent6}"/></a:accent6><a:hlink><a:srgbClr val="{hlink}"/></a:hlink>\
<a:folHlink><a:srgbClr val="{folHlink}"/></a:folHlink></a:clrScheme>"""

THEME_FONT = """<a:fontScheme name="{name}"><a:majorFont><a:latin typeface="{major}"/>\
<a:ea typeface="{major}"/><a:cs typeface=""/><a:font script="Jpan" typeface="{major}"/>\
</a:majorFont><a:minorFont><a:latin typeface="{minor_latin}"/><a:ea typeface="{minor_ea}"/>\
<a:cs typeface=""/><a:font script="Jpan" typeface="{minor_ea}"/></a:minorFont></a:fontScheme>"""

# 既定テーマは 3 段すべての効果スタイルに outerShdw を持つ。図形側で打ち消しても、
# コネクタのように effectRef だけ持つ要素には影が出る。「影を使わない」は規約なので、
# テーマの段階で空にする。以後ユーザーが挿す図形にも影は付かない。
THEME_EFFECT = ("<a:effectStyleLst>"
                + "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
                + "</a:effectStyleLst>")


def patch_theme(path: Path) -> None:
    """theme1.xml の配色・書体・効果スキームを TOKENS で置き換える。

    PowerPoint の［配色］［フォント］に出るのはここ。スライド上の見た目だけ
    変えても、後からユーザーが挿す図形には効かないので必ず差し替える。
    効果スキームも空にする (理由は THEME_EFFECT のコメント)。
    """
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    clr = THEME_CLR.format(**{**TOKENS, "name": TOKENS["name"] + " 配色"})
    fnt = THEME_FONT.format(name=TOKENS["name"], major=TOKENS["font_major"],
                            minor_latin=TOKENS["font_minor_latin"],
                            minor_ea=TOKENS["font_minor_ea"])
    out = []
    for info, data in items:
        if re.match(r"ppt/theme/theme\d+\.xml$", info.filename):
            x = data.decode("utf8")
            x = re.sub(r"<a:clrScheme.*?</a:clrScheme>", clr, x, flags=re.S)
            x = re.sub(r"<a:fontScheme.*?</a:fontScheme>", fnt, x, flags=re.S)
            x = re.sub(r"<a:effectStyleLst>.*?</a:effectStyleLst>", THEME_EFFECT, x, flags=re.S)
            data = x.encode("utf8")
        out.append((info, data))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in out:
            z.writestr(info, data)


def trim_layouts(prs, keep=("Title Slide", "Title and Content", "Two Content",
                            "Title Only", "Blank")) -> None:
    """使わない既定レイアウトを落として、マスターを読める大きさに保つ。"""
    master = prs.slide_masters[0]
    layouts = list(master.slide_layouts)
    names = {"Title Slide": "表紙", "Title and Content": "標準 (帯＋本文)",
             "Two Content": "2 分割", "Title Only": "タイトルのみ", "Blank": "白紙"}
    for lay in layouts:
        if lay.name in keep:
            lay.name = names.get(lay.name, lay.name)
        else:
            master.slide_layouts.remove(lay)


MASTER_RECT = """<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<p:nvSpPr><p:cNvPr id="{id}" name="{name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
<a:solidFill><a:schemeClr val="{slot}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>
<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"""


def dress_master(prs) -> None:
    """マスターに共通の枠を置き、新規スライドが最初から標準の見た目になるようにする。

    枠はテーマスロット参照 (schemeClr) で塗る。accent1 を差し替えれば罫も追従する。
    """
    from pptx.oxml import parse_xml

    master = prs.slide_masters[0]
    for ph in list(master.placeholders):
        ph._element.getparent().remove(ph._element)
    sp_tree = master.shapes._spTree
    chrome_parts = [
        ("タイトル帯", "tx2", 0, 0, SLIDE_W, BAND_H),
        ("アクセント罫", "accent1", 0, RULE_Y, SLIDE_W, RULE_H),
        ("フッター帯", "bg2", 0, FOOT_Y, SLIDE_W, FOOT_H),
    ]
    for i, (name, slot, x, y, w, h) in enumerate(chrome_parts, start=90):
        sp_tree.append(parse_xml(MASTER_RECT.format(
            id=i, name=name, slot=slot,
            x=int(x * EMU_IN), y=int(y * EMU_IN),
            cx=int(w * EMU_IN), cy=int(h * EMU_IN))))


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    out = (Path(argv[0]).resolve() if argv
           else Path(__file__).resolve().parent.parent / "assets" / "design.pptx")
    prs = Presentation()
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)
    trim_layouts(prs)
    dress_master(prs)
    build(prs)
    core = prs.core_properties
    core.title = TOKENS["name"]
    core.author = TOKENS["owner"]
    core.comments = "プレゼン資料の標準スタイル。配色・書体はテーマとして登録済み。"
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    patch_theme(out)
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB, {len(prs.slides._sldIdLst)} slides)")


if __name__ == "__main__":
    main()
