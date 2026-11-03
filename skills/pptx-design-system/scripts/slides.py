"""規約スライド 16 枚の中身。

1 枚ずつ上から読める形に並べてある。座標は共有せず各枚に直接書く
(抽象化すると「どの枚の何を直すか」が追えなくなるため)。
"""

from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

from kit import box, card, chrome, lead, line_h, pill, swatch, text
from tokens import (
    BAND_H, BODY_B, BODY_T, BODY_W, FOOT_H, FOOT_Y, GREY_RULE, GREY_SUB,
    MARGIN, RULE_Y, SHADE_80, SLIDE_H, SLIDE_W, TINT_20, TINT_40, TOKENS,
)

# ---------------------------------------------------------------- スライド


def build(prs):
    blank = next(lay for lay in prs.slide_layouts if lay.name == "白紙")
    s = lambda: prs.slides.add_slide(blank)  # noqa: E731
    n = iter(range(1, 99))

    # --- 1 表紙 -----------------------------------------------------------
    sl = s()
    box(sl, 0, 0, SLIDE_W, SLIDE_H, fill=TOKENS["dk2"])
    box(sl, 0, 0, 5.4, SLIDE_H, fill=TOKENS["accent1"])
    box(sl, 0, SLIDE_H - 1.6, 5.4, 1.6, fill=SHADE_80)
    text(sl, 6.3, 2.35, 6.2, 1.6, TOKENS["name"], size="cover", color="FFFFFF", bold=True,
         font=TOKENS["font_major"], line_spacing=1.15)
    line_h(sl, 6.3, 4.22, 2.2, TOKENS["accent1"], width=4)
    text(sl, 6.3, 4.52, 6.2, 1.4,
         ["プレゼン資料の標準スタイル", "色・書体・余白・図解の約束ごとを 1 ファイルにまとめたもの"],
         size="small", color="D9D9D9", line_spacing=1.6)
    text(sl, 6.3, 6.3, 6.2, 0.4, f"{TOKENS['owner']}  /  v1.0", size="note", color="A9A7BD",
         font="Arial")

    # --- 2 この資料の役割 ---------------------------------------------------
    sl = s()
    chrome(sl, "この資料の役割", next(n) + 1)
    lead(sl, "毎回ゼロから決めないために、決め終わったことだけを置く。")
    cw, gap = 3.75, 0.36
    items = [
        ("機能として効くもの", "テーマ配色とテーマフォントは、このファイルの中で PowerPoint の機能として登録してある。"
                       "新しい図形や表は最初からこの色・この書体で出る。", TOKENS["accent1"], "1"),
        ("判断として効くもの", "赤をいつ使うか、文字を何 pt まで小さくしてよいか。"
                       "測れない判断を言葉にして、迷いを前倒しで消す。", TOKENS["accent2"], "2"),
        ("引き継げるもの", "案件ごとに変えるのは accent1 の 1 色だけ。"
                     "残りは固定なので、他人が触っても崩れない。", TOKENS["accent3"], "3"),
    ]
    for i, (h, b, a, ic) in enumerate(items):
        card(sl, MARGIN + i * (cw + gap), 2.55, cw, 2.70, h, b, accent=a, icon_text=ic)

    # --- 3 設計の 5 原則 ----------------------------------------------------
    sl = s()
    chrome(sl, "設計の 5 原則", next(n) + 1)
    rules = [
        ("主役は 1 色", "画面の色の 7 割は accent1 と無彩色。他の色は意味があるときだけ出す。"),
        ("色に意味を結ぶ", "赤は否定、緑は肯定、橙は注目。装飾で色を選ばない。"),
        ("1 枚 1 主張", "本文の最上段に主張を 1 文。その下は全部その証拠。"),
        ("枠は動かさない", "帯・罫・フッターの位置は全ページ同じ。変えるのは中身だけ。"),
        ("足すより消す", "本文は 1 枚 100 字が中央値。250 字を超えたら 2 枚に割る。"),
    ]
    y = 1.75
    for i, (h, b) in enumerate(rules):
        box(sl, MARGIN, y, 0.62, 0.62, fill=TOKENS["accent1"], shape=MSO_SHAPE.OVAL)
        text(sl, MARGIN, y + 0.13, 0.62, 0.4, f"0{i + 1}", size="small", color="FFFFFF",
             bold=True, align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.0)
        text(sl, MARGIN + 0.9, y + 0.02, 3.3, 0.5, h, size="lead", bold=True,
             color=TOKENS["dk2"], font=TOKENS["font_major"], line_spacing=1.1)
        text(sl, MARGIN + 4.4, y + 0.08, BODY_W - 4.4, 0.6, b, size="small", line_spacing=1.4)
        y += 0.98

    # --- 4 カラーパレット ---------------------------------------------------
    sl = s()
    chrome(sl, "カラーパレット", next(n) + 1)
    text(sl, MARGIN, BODY_T, BODY_W, 0.6,
         "PowerPoint の［デザイン］▸［バリエーション］▸［配色］に、この 12 色が登録済み。"
         "図形も表もグラフも、この行から選べば外れない。", size="small", color=GREY_SUB)
    slots = [
        ("dk1", TOKENS["dk1"], "本文テキスト"),
        ("lt1", TOKENS["lt1"], "紙 / 反転文字"),
        ("dk2", TOKENS["dk2"], "タイトル帯・濃い面"),
        ("lt2", TOKENS["lt2"], "フッター・薄い面"),
        ("accent1", TOKENS["accent1"], "主役。案件ごとに差し替える"),
        ("accent2", TOKENS["accent2"], "強調・注目させる数値"),
        ("accent3", TOKENS["accent3"], "肯定・達成・できること"),
        ("accent4", TOKENS["accent4"], "否定・リスク・できないこと"),
        ("accent5", TOKENS["accent5"], "参照・情報・外部"),
        ("accent6", TOKENS["accent6"], "中立・抑制・その他"),
        ("hlink", TOKENS["hlink"], "ハイパーリンク"),
        ("folHlink", TOKENS["folHlink"], "表示済みリンク"),
    ]
    sw, sgap = 1.72, 0.22
    for i, (slot, hexv, role) in enumerate(slots):
        cx = MARGIN + (i % 6) * (sw + sgap)
        cy = 2.15 + (i // 6) * 2.15
        swatch(sl, cx, cy, sw, 1.30, hexv, slot, role)
    for i, (hexv, lab) in enumerate(
        [(TINT_20, "20%"), (TINT_40, "40%"), (TOKENS["accent1"], "100%"), (SHADE_80, "80% 暗")]
    ):
        bx = MARGIN + i * 1.05
        box(sl, bx, 6.22, 0.95, 0.30, fill=hexv)
        text(sl, bx, 6.55, 0.95, 0.25, lab, size=11, color=GREY_SUB, align=PP_ALIGN.CENTER,
             font="Arial", line_spacing=1.0)
    text(sl, MARGIN + 4.5, 6.22, BODY_W - 4.5, 0.6,
         "濃淡は色を増やして作らない。accent1 の明度違い (PowerPoint の［テーマの色］上段/下段) だけで足りる。",
         size=13, color=GREY_SUB, line_spacing=1.4)

    # --- 5 色の配分と意味 ---------------------------------------------------
    sl = s()
    chrome(sl, "色の配分と意味", next(n) + 1)
    lead(sl, "色数ではなく、配分と対応づけで決める。")
    bar_y, bar_h = 2.65, 0.52
    segs = [("無彩色 (紙・文字・面) 70%", 0.70, TOKENS["lt2"], TOKENS["dk1"]),
            ("accent1 25%", 0.25, TOKENS["accent1"], "FFFFFF"),
            ("他 5%", 0.05, TOKENS["accent2"], "FFFFFF")]
    bx = MARGIN
    for label, frac, fill, fg in segs:
        w = BODY_W * frac
        box(sl, bx, bar_y, w, bar_h, fill=fill)
        text(sl, bx, bar_y + 0.13, w, 0.3, label, size=13, color=fg, bold=True,
             align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.0)
        bx += w
    text(sl, MARGIN, bar_y + 0.70, BODY_W, 0.4,
         "1 枚の中で accent1 が主役でいられるのは、周りが無彩色だから。"
         "accent2〜6 は「意味が立つ瞬間」にだけ出す。", size="small", color=GREY_SUB)

    y = 4.15
    pairs = [
        ("否定・リスク・課題", TOKENS["accent4"], "×印、課題、できないこと"),
        ("肯定・達成・解決", TOKENS["accent3"], "○印、効果、できること"),
        ("注目させる数値", TOKENS["accent2"], "グラフの当該系列、主要な数字"),
        ("参照・外部・情報", TOKENS["accent5"], "引用、他社、補足リンク"),
        ("中立・抑制・その他", TOKENS["accent6"], "比較対象、グレーアウト"),
    ]
    pw = (BODY_W - 0.3 * 4) / 5
    for i, (label, c, use) in enumerate(pairs):
        px = MARGIN + i * (pw + 0.3)
        pill(sl, px, y, pw, 0.46, label, c, size=13)
        text(sl, px, y + 0.62, pw, 0.9, use, size=13, color=GREY_SUB, align=PP_ALIGN.CENTER,
             line_spacing=1.4)
    text(sl, MARGIN, 5.85, BODY_W, 0.7,
         [[("登場人物にも色を割り当てる。", {"bold": True, "color": TOKENS["dk2"]}),
           ("　「自社=accent1 / 競合=accent6 / 顧客=accent5」と決めたら、"
            "資料の最後まで図も表も本文もその対応を崩さない。読み手は 2 枚目から凡例を見なくなる。", {})]],
         size="small", line_spacing=1.5)

    # --- 6 書体 ------------------------------------------------------------
    sl = s()
    chrome(sl, "書体", next(n) + 1)
    lead(sl, "見出しは記名性、本文は可読性。役割を分けて 2 書体に留める。")
    for i, (role, fam, note_, sample) in enumerate([
        ("見出し (major)", TOKENS["font_major"],
         "丸ゴシック。4 本すべての資料に共通して出てくる書体で、この資料の記名性そのもの。",
         "読ませる前に、伝える"),
        ("本文 (minor)", TOKENS["font_minor_ea"],
         "Microsoft 同梱の UD 書体。投影時につぶれず、Windows なら相手の環境にも必ずある。",
         "本文はここに書く。1 枚 100 字が中央値、250 字で 2 枚に割る。"),
    ]):
        y = 2.5 + i * 1.95
        box(sl, MARGIN, y, 0.08, 1.55, fill=TOKENS["accent1"] if i == 0 else TOKENS["accent6"])
        text(sl, MARGIN + 0.32, y, 3.4, 0.4, role, size="small", bold=True,
             color=TOKENS["accent1"] if i == 0 else GREY_SUB,
             font=TOKENS["font_major"], line_spacing=1.1)
        text(sl, MARGIN + 0.32, y + 0.38, 4.2, 0.5, fam, size=22, bold=True,
             color=TOKENS["dk2"], font=fam, line_spacing=1.1)
        text(sl, MARGIN + 0.32, y + 0.95, 4.6, 0.6, note_, size=13, color=GREY_SUB,
             line_spacing=1.4)
        text(sl, MARGIN + 5.4, y + 0.22, BODY_W - 5.4, 1.1, sample,
             size=26 if i == 0 else 18, bold=(i == 0), color=TOKENS["dk1"], font=fam,
             line_spacing=1.4)
    text(sl, MARGIN, 6.35, BODY_W, 0.5,
         [[("配布先に書体がないとき", {"bold": True, "color": TOKENS["dk2"]}),
           ("　［ファイル］▸［オプション］▸［保存］▸［ファイルにフォントを埋め込む］で "
            "見出し書体ごと配れる。埋め込めないときは見出しも BIZ UDPGothic に落とす。", {})]],
         size=13, color=TOKENS["dk1"], line_spacing=1.5)

    # --- 7 文字サイズ -------------------------------------------------------
    sl = s()
    chrome(sl, "文字サイズ", next(n) + 1)
    text(sl, MARGIN, BODY_T, BODY_W, 0.4,
         "13.333 × 7.5 in (16:9) での基準値。16:10 (10 × 6.25 in) で使うときは全段 ×0.83。",
         size="small", color=GREY_SUB)
    scale = [
        ("hero", 54, "数字 1 つで殴る枚。1 デッキに 1 回だけ", "95%"),
        ("cover", 44, "表紙タイトル", "表紙タイトル"),
        ("section", 40, "セクション扉", "1. 背景"),
        ("title", 36, "スライドタイトル (帯の中)", "スライドタイトル"),
        ("lead", 24, "主張文。本文最上段に 1〜2 行", "主張はここに 1 文で置く"),
        ("body", 20, "本文", "本文はこの大きさ"),
        ("small", 16, "補足・キャプション・図中ラベル", "補足とキャプション"),
        ("note", 12, "出典・注記。これより下は使わない", "出典: ○○調査 (2025)"),
    ]
    y = 1.95
    for name, pt, use, sample in scale:
        text(sl, MARGIN, y + 0.04, 1.3, 0.4, name, size=13, bold=True, color=TOKENS["accent1"],
             font="Arial", line_spacing=1.0)
        text(sl, MARGIN + 1.3, y + 0.04, 0.8, 0.4, f"{pt}pt", size=13, color=GREY_SUB,
             font="Arial", align=PP_ALIGN.RIGHT, line_spacing=1.0)
        text(sl, MARGIN + 2.35, y - (pt - 20) * 0.006, 4.9, 0.6, sample,
             size=min(pt, 30), bold=pt >= 36, color=TOKENS["dk1"],
             font=TOKENS["font_major"] if pt >= 24 else TOKENS["font_minor_ea"],
             line_spacing=1.0)
        text(sl, MARGIN + 7.5, y + 0.06, BODY_W - 7.5, 0.5, use, size=13, color=GREY_SUB,
             line_spacing=1.3)
        y += 0.60
    text(sl, MARGIN, 6.78, BODY_W, 0.4,
         "※ 見本は紙面の都合で 30pt 以上を縮めて表示している。実寸は左の数値を正とする。",
         size=11, color=GREY_SUB)

    # --- 8 グリッド --------------------------------------------------------
    sl = s()
    chrome(sl, "画面の骨格", next(n) + 1)
    gx, gy, gw = MARGIN, 1.75, 7.3
    gh = gw * SLIDE_H / SLIDE_W
    box(sl, gx - 0.12, gy - 0.12, gw + 0.24, gh + 0.24, fill=TOKENS["lt2"])
    box(sl, gx, gy, gw, gh, fill="FFFFFF")
    sc = gw / SLIDE_W
    box(sl, gx, gy, gw, BAND_H * sc, fill=TOKENS["dk2"])
    line_h(sl, gx, gy + RULE_Y * sc, gw, TOKENS["accent1"], width=2.5)
    box(sl, gx, gy + FOOT_Y * sc, gw, FOOT_H * sc, fill=TOKENS["lt2"])
    box(sl, gx + MARGIN * sc, gy + BODY_T * sc, (BODY_W) * sc, (BODY_B - BODY_T) * sc,
        fill=TINT_20)
    text(sl, gx + MARGIN * sc, gy + (BODY_T + 1.6) * sc, BODY_W * sc, 0.4, "本文領域",
         size=13, bold=True, color=SHADE_80, align=PP_ALIGN.CENTER, line_spacing=1.0)
    specs = [
        ("外周マージン", "左右 0.92 in (6.9%)", "端に寄せた要素も、ここより外へは出さない"),
        ("タイトル帯", "高さ 1.00 in / 全幅", "セクション名を入れる。1 枚ごとの要約を入れない"),
        ("アクセント罫", "y = 1.04 in / 3pt", "accent1 を全ページに 1 本だけ通す"),
        ("本文領域", "y 1.35 → 6.70 in", "高さ 5.35 in。ここに収まらない量は 2 枚に割る"),
        ("フッター帯", "y 6.94 in / 高さ 0.56", "左: 資料名 / 中央: 所属 / 右: ページ"),
    ]
    sx, sw2 = 8.70, SLIDE_W - MARGIN - 8.70
    y = 1.78
    for label, val, note_ in specs:
        text(sl, sx, y, sw2, 0.3, label, size=13, bold=True, color=TOKENS["dk2"],
             font=TOKENS["font_major"], line_spacing=1.0)
        text(sl, sx, y + 0.28, sw2, 0.3, val, size=12, color=TOKENS["accent1"], font="Arial",
             line_spacing=1.0)
        text(sl, sx, y + 0.54, sw2, 0.55, note_, size=11, color=GREY_SUB, line_spacing=1.3)
        y += 1.06

    # --- 9 レイアウトの型 ---------------------------------------------------
    sl = s()
    chrome(sl, "レイアウトの型", next(n) + 1)
    lead(sl, "型は 6 つ。迷ったら「主張＋根拠」から始める。")
    tw, th, lw, pitch = 1.60, 1.05, 1.75, 3.88
    kinds = [
        ("主張＋根拠", [(0.10, 0.10, 0.80, 0.18), (0.10, 0.36, 0.80, 0.52)]),
        ("2 分割", [(0.08, 0.10, 0.40, 0.78), (0.52, 0.10, 0.40, 0.78)]),
        ("3 連", [(0.06, 0.18, 0.26, 0.62), (0.37, 0.18, 0.26, 0.62), (0.68, 0.18, 0.26, 0.62)]),
        ("図版 1 点", [(0.18, 0.10, 0.64, 0.78)]),
        ("比較表", [(0.08, 0.10, 0.84, 0.20), (0.08, 0.34, 0.84, 0.54)]),
        ("数字 1 つ", [(0.25, 0.22, 0.50, 0.42), (0.20, 0.70, 0.60, 0.14)]),
    ]
    use_note = [
        "本文の頭に主張を 1 文、下にその根拠。既存資料で最も多い型",
        "対比・前後・左文右図。左右の上端と下端を必ず揃える",
        "並列な 3 つ。4 つ以上になったら分類を見直す合図",
        "構成図・スクリーンショット。説明は図の外に置かない",
        "行に対象、列に観点。自社の行だけ accent1 で塗る",
        "結論の数字を 54pt。1 デッキに 1 回だけ使う",
    ]
    for i, (name, blocks) in enumerate(kinds):
        bx = MARGIN + (i % 3) * pitch
        by = 2.60 + (i // 3) * 1.95
        box(sl, bx, by, tw, th, fill=TOKENS["lt2"])
        box(sl, bx, by, tw, th * 0.16, fill=TOKENS["dk2"])
        for fx, fy, fw_, fh_ in blocks:
            box(sl, bx + tw * fx, by + th * (0.20 + fy * 0.78), tw * fw_, th * fh_ * 0.78,
                fill=TINT_40)
        text(sl, bx + tw + 0.18, by + 0.02, lw, 0.35, name, size="small", bold=True,
             color=TOKENS["dk2"], font=TOKENS["font_major"], line_spacing=1.1)
        text(sl, bx + tw + 0.18, by + 0.40, lw, 1.0, use_note[i], size=12, color=GREY_SUB,
             line_spacing=1.35)

    # --- 10 図解の部品 ------------------------------------------------------
    sl = s()
    chrome(sl, "図解の部品", next(n) + 1)
    lead(sl, "新しい形を増やさない。同じ意味は同じ形で描く。")
    # 部品は y〜y+0.60 の帯に揃え、説明は y+0.80 から始める
    y, cap = 2.70, 3.50
    pill(sl, MARGIN, y, 2.0, 0.50, "登場人物", TOKENS["accent1"])
    text(sl, MARGIN, cap, 2.0, 0.9, "塗りピル\n人・組織・システムなど、図の主語",
         size=12, color=GREY_SUB, align=PP_ALIGN.CENTER, line_spacing=1.4)
    box(sl, MARGIN + 2.5, y, 2.0, 0.50, fill="FFFFFF", line=TOKENS["accent1"], line_w=1.25,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    text(sl, MARGIN + 2.5, y + 0.12, 2.0, 0.3, "属性・状態", size=14, color=TOKENS["accent1"],
         bold=True, align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.0)
    text(sl, MARGIN + 2.5, cap, 2.0, 0.9, "線ピル\n主語にぶら下がる性質・条件",
         size=12, color=GREY_SUB, align=PP_ALIGN.CENTER, line_spacing=1.4)
    box(sl, MARGIN + 5.0, y - 0.12, 2.4, 0.74, fill=TOKENS["lt2"],
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    text(sl, MARGIN + 5.15, y + 0.00, 2.1, 0.3, "まとまり", size=13, bold=True,
         color=TOKENS["dk2"], font=TOKENS["font_major"], line_spacing=1.0)
    text(sl, MARGIN + 5.15, y + 0.28, 2.1, 0.3, "説明文が付く単位", size=11, color=GREY_SUB,
         line_spacing=1.2)
    text(sl, MARGIN + 5.0, cap, 2.4, 0.9, "カード\n見出しと本文の単位。面で置き、囲まない",
         size=12, color=GREY_SUB, align=PP_ALIGN.CENTER, line_spacing=1.4)
    tri = box(sl, MARGIN + 8.05, y + 0.05, 0.42, 0.40, fill=TOKENS["accent1"],
              shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
    tri.rotation = 90
    text(sl, MARGIN + 7.65, cap, 1.3, 0.9, "送り\n流れ・変換・因果",
         size=12, color=GREY_SUB, align=PP_ALIGN.CENTER, line_spacing=1.4)
    box(sl, MARGIN + 9.1, y - 0.12, 2.4, 0.56, fill=TOKENS["lt2"],
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3)
    text(sl, MARGIN + 9.2, y + 0.01, 2.2, 0.3, "心の声を書く吹き出し", size=12,
         color=TOKENS["dk1"], align=PP_ALIGN.CENTER, line_spacing=1.2)
    box(sl, MARGIN + 9.5, y + 0.46, 0.15, 0.15, fill=TOKENS["lt2"], shape=MSO_SHAPE.OVAL)
    box(sl, MARGIN + 9.35, y + 0.64, 0.10, 0.10, fill=TOKENS["lt2"], shape=MSO_SHAPE.OVAL)
    text(sl, MARGIN + 9.1, cap, 2.4, 0.9, "吹き出し\n読み手の心の声を代弁する",
         size=12, color=GREY_SUB, align=PP_ALIGN.CENTER, line_spacing=1.4)
    text(sl, MARGIN, 4.98, BODY_W, 1.4,
         [[("線で分けず、面で分ける。", {"bold": True, "color": TOKENS["dk2"]}),
           ("　箱を細い罫で囲むと、読む前に「要素がいくつあるか」が先に目に入る。"
            "地より一段沈めた面を置けば罫は要らない。罫は軸と区切りだけに残す。", {})],
          [("影・グラデーション・斜体を使わない。角丸は 2 種類まで。", {"bold": True, "color": TOKENS["dk2"]}),
           ("　面の差は明度だけでつける。ピルは半径最大、カードは浅い角丸、それ以外は作らない。", {})]],
         size="small", line_spacing=1.5, space_after=10)

    # --- 11 強調の作法 ------------------------------------------------------
    sl = s()
    chrome(sl, "強調の作法", next(n) + 1)
    lead(sl, "強調は、強調していない部分があって初めて効く。")
    cw2 = (BODY_W - 0.4 * 2) / 3
    box(sl, MARGIN, 2.65, cw2, 3.3, fill=TOKENS["lt2"],
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    text(sl, MARGIN + 0.28, 2.90, cw2 - 0.56, 0.4, "色で差す", size="small", bold=True,
         color=TOKENS["accent1"], font=TOKENS["font_major"], line_spacing=1.1)
    text(sl, MARGIN + 0.28, 3.45, cw2 - 0.56, 1.1,
         [[("新入社員の", {}), ("適切な配属先", {"color": TOKENS["accent4"], "bold": True}),
           ("を見極められる", {})]], size=18, line_spacing=1.45)
    text(sl, MARGIN + 0.28, 4.75, cw2 - 0.56, 1.0,
         "文の中で一番効く語だけを 1 色。太字は使わず色で差すと、文が崩れない。",
         size=13, color=GREY_SUB, line_spacing=1.45)
    bx = MARGIN + cw2 + 0.4
    box(sl, bx, 2.65, cw2, 3.3, fill=TOKENS["lt2"],
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    text(sl, bx + 0.28, 2.90, cw2 - 0.56, 0.4, "他を落とす", size="small", bold=True,
         color=TOKENS["accent1"], font=TOKENS["font_major"], line_spacing=1.1)
    for i, (lab, on) in enumerate([("選択肢 A", True), ("選択肢 B", False), ("選択肢 C", False)]):
        yy = 3.45 + i * 0.52
        pill(sl, bx + 0.28, yy, cw2 - 0.56, 0.42,
             lab, TOKENS["accent1"] if on else "DEDEDE",
             color="FFFFFF" if on else "9A9A9A", size=13)
    text(sl, bx + 0.28, 5.15, cw2 - 0.56, 0.9,
         "採らなかった案は消さずに灰色で残す。検討の幅がそのまま説得力になる。",
         size=13, color=GREY_SUB, line_spacing=1.45)
    bx2 = MARGIN + (cw2 + 0.4) * 2
    box(sl, bx2, 2.65, cw2, 3.3, fill=TOKENS["lt2"],
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    text(sl, bx2 + 0.28, 2.90, cw2 - 0.56, 0.4, "積み上げる", size="small", bold=True,
         color=TOKENS["accent1"], font=TOKENS["font_major"], line_spacing=1.1)
    for i in range(3):
        box(sl, bx2 + 0.28 + i * 0.1, 3.5 + i * 0.5, cw2 - 0.56 - i * 0.2, 0.40,
            fill=[TINT_20, TINT_40, TOKENS["accent1"]][i])
    text(sl, bx2 + 0.28, 5.15, cw2 - 0.56, 0.9,
         "同じ構図のまま要素を足して 2〜3 枚続ける。読み手は毎回見方を覚え直さずに済む。",
         size=13, color=GREY_SUB, line_spacing=1.45)
    text(sl, MARGIN, 6.15, BODY_W, 0.5,
         "赤 (accent4) は否定・リスクにだけ使う。目立たせたいだけの赤は accent2 に置き換える。",
         size="small", color=TOKENS["accent4"], bold=True, align=PP_ALIGN.CENTER,
         font=TOKENS["font_major"])

    # --- 12 表とグラフ ------------------------------------------------------
    sl = s()
    chrome(sl, "表とグラフ", next(n) + 1)
    cols = ["", "観点 A", "観点 B", "観点 C", "観点 D"]
    rows = [("自社", ["○", "○", "○", "△"], True),
            ("競合 X", ["○", "△", "", "○"], False),
            ("競合 Y", ["△", "", "○", ""], False)]
    tx0, ty0 = MARGIN, 1.85
    cw3, ch3 = 1.18, 0.46
    label_w = 1.5
    for j, c in enumerate(cols):
        x = tx0 + (0 if j == 0 else label_w + (j - 1) * cw3)
        w = label_w if j == 0 else cw3
        box(sl, x, ty0, w, ch3, fill=TOKENS["dk2"] if j else TOKENS["lt2"])
        if c:
            text(sl, x, ty0 + 0.11, w, 0.3, c, size=13, color="FFFFFF", bold=True,
                 align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.0)
    for i, (label, vals, mine) in enumerate(rows):
        yy = ty0 + ch3 + i * ch3
        row_fill = TINT_40 if mine else (TOKENS["lt2"] if i % 2 else "FFFFFF")
        box(sl, tx0, yy, label_w, ch3, fill=row_fill)
        text(sl, tx0, yy + 0.11, label_w, 0.3, label, size=13,
             color=SHADE_80 if mine else TOKENS["dk1"], bold=mine, align=PP_ALIGN.CENTER,
             line_spacing=1.0)
        for j, v in enumerate(vals):
            x = tx0 + label_w + j * cw3
            box(sl, x, yy, cw3, ch3, fill=row_fill)
            if v:
                text(sl, x, yy + 0.08, cw3, 0.33, v, size=16,
                     color=SHADE_80 if mine else GREY_SUB, bold=mine,
                     align=PP_ALIGN.CENTER, line_spacing=1.0)
    text(sl, MARGIN, 3.95, label_w + cw3 * 4, 1.5,
         [[("表", {"bold": True, "color": TOKENS["dk2"], "size": "small"})],
          [("見出し行は dk2 に白抜き。自分の行だけ accent1 の面で塗り、"
            "残りは紙と面の交互で分ける。罫線は 1 本も引かない。", {})]],
         size=13, color=GREY_SUB, line_spacing=1.45, space_after=6)

    gx2 = MARGIN + 6.9
    base = 5.95
    vals = [(0.9, "2022"), (1.25, "2023"), (1.6, "2024"), (2.35, "2025")]
    for i, (h, lab) in enumerate(vals):
        bxx = gx2 + i * 0.95
        is_last = i == len(vals) - 1
        box(sl, bxx, base - h, 0.62, h, fill=TOKENS["accent2"] if is_last else "DEDEDE")
        text(sl, bxx - 0.1, base - h - 0.32, 0.82, 0.28, ["3.3", "3.8", "4.5", "5.1"][i],
             size=13, bold=is_last, color=TOKENS["accent2"] if is_last else GREY_SUB,
             align=PP_ALIGN.CENTER, font="Arial", line_spacing=1.0)
        text(sl, bxx - 0.1, base + 0.06, 0.82, 0.28, lab, size=12, color=GREY_SUB,
             align=PP_ALIGN.CENTER, font="Arial", line_spacing=1.0)
    line_h(sl, gx2 - 0.1, base, 4.0, GREY_RULE, width=1)
    text(sl, gx2, 1.85, 4.3, 0.9,
         [[("グラフ", {"bold": True, "color": TOKENS["dk2"], "size": "small"})],
          [("言いたい系列だけ accent2、残りは灰色。凡例より直接ラベル。"
            "目盛線は引かず、値を数字で置く。", {})]],
         size=13, color=GREY_SUB, line_spacing=1.45, space_after=6)

    # --- 13 イラストと画像 --------------------------------------------------
    sl = s()
    chrome(sl, "イラストと画像", next(n) + 1)
    lead(sl, "画像は装飾ではなく、文が言い切れない形を引き受ける。")
    items2 = [
        ("出典を 1 つに絞る", "1 本の資料の中で画風を混ぜない。線画なら線画、"
                      "フラットイラストならフラットで最後まで通す。", TOKENS["accent1"]),
        ("accent1 を絵から取る", "unDraw のような色を指定できる素材なら、"
                        "素材側の色を accent1 に合わせる。資料と絵が同じ色で喋る。", TOKENS["accent2"]),
        ("面積は 1〜2 割", "既存資料の中央値で、画像が画面に占める面積は 8〜19%。"
                     "それ以上は図が主語になる枚として別に設計する。", TOKENS["accent3"]),
        ("キャプションを必ず置く", "画像の下に 16pt で 1 行。"
                         "何を見てほしいかを書かない画像は、見られない。", TOKENS["accent5"]),
    ]
    cw4 = (BODY_W - 0.36 * 3) / 4
    for i, (h, b, a) in enumerate(items2):
        card(sl, MARGIN + i * (cw4 + 0.36), 2.60, cw4, 3.05, h, b, accent=a,
             icon_text=str(i + 1))
    text(sl, MARGIN, 5.90, BODY_W, 0.8,
         "素材の利用条件は資料ごとに確認する。配布・公開する資料では、"
         "出典表記が必要な素材をフッター左ではなく当該ページの右下 12pt に置く。",
         size=13, color=GREY_SUB, line_spacing=1.45)

    # --- 14 やらないこと ----------------------------------------------------
    sl = s()
    chrome(sl, "やらないこと", next(n) + 1)
    bad = [
        ("タイトルに要約を書く", "帯はセクション名の場所。要約は本文最上段の主張文に書く"),
        ("目立たせたいから赤", "赤は否定の色として予約済み。注目させたいだけなら accent2"),
        ("色で分類を増やす", "4 つ以上を色分けしたくなったら、分類そのものを疑う"),
        ("本文を中央揃え", "中央揃えはタイトルと主張文だけ。段落と箇条書きは必ず左揃え"),
        ("12pt より小さい文字", "投影で読めない。入らないなら削るか 2 枚に割る"),
        ("1 枚に主張を 2 つ", "読み手が持ち帰れるのは 1 枚 1 つ。足したら割る"),
        ("細い罫で箱を囲む", "罫が増えるほど要素の数が先に目に入る。囲まずに面で沈める"),
        ("枠を 1 枚だけ変える", "帯・罫・フッターの位置は全ページ共通。例外を作らない"),
    ]
    cw5 = (BODY_W - 0.5) / 2
    for i, (h, b) in enumerate(bad):
        xx = MARGIN + (i % 2) * (cw5 + 0.5)
        yy = 1.70 + (i // 2) * 1.26
        box(sl, xx, yy + 0.06, 0.34, 0.34, fill=TOKENS["accent4"], shape=MSO_SHAPE.OVAL)
        text(sl, xx, yy + 0.11, 0.34, 0.3, "×", size=15, color="FFFFFF", bold=True,
             align=PP_ALIGN.CENTER, font=TOKENS["font_major"], line_spacing=1.0)
        text(sl, xx + 0.52, yy + 0.04, cw5 - 0.52, 0.4, h, size="small", bold=True,
             color=TOKENS["dk2"], font=TOKENS["font_major"], line_spacing=1.1)
        text(sl, xx + 0.52, yy + 0.46, cw5 - 0.52, 0.7, b, size=13, color=GREY_SUB,
             line_spacing=1.4)

    # --- 15 運用 ------------------------------------------------------------
    sl = s()
    chrome(sl, "運用", next(n) + 1)
    lead(sl, "使うときは 1 色変えるだけ。配るときはテンプレートとして配る。")
    steps = [
        ("新しい資料を作る",
         "このファイルを複製して中身を消す。または［デザイン］▸［配色］から この配色を選ぶ。"),
        ("案件の色に合わせる",
         "［配色］▸［色のカスタマイズ］で accent1 だけ差し替える。帯・罫・表・グラフが追従する。"),
        ("テンプレートとして配る",
         "［名前を付けて保存］で .potx。配色と書体だけなら［現在の配色を保存］で .thmx。"),
        ("書体ごと配る",
         "［オプション］▸［保存］▸［フォントを埋め込む］。見出し書体がない相手にも崩れない。"),
    ]
    cw6 = (BODY_W - 0.36 * 3) / 4
    for i, (h, b) in enumerate(steps):
        xx = MARGIN + i * (cw6 + 0.36)
        box(sl, xx, 2.45, cw6, 2.70, fill=TOKENS["lt2"],
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
        text(sl, xx + 0.26, 2.68, cw6 - 0.52, 0.3, f"STEP {i + 1}", size=12, bold=True,
             color=TOKENS["accent1"], font="Arial", line_spacing=1.0)
        text(sl, xx + 0.26, 2.98, cw6 - 0.52, 0.6, h, size="small", bold=True,
             color=TOKENS["dk2"], font=TOKENS["font_major"], line_spacing=1.2)
        text(sl, xx + 0.26, 3.62, cw6 - 0.52, 1.3, b, size=13, line_spacing=1.45)
        if i < 3:
            t = box(sl, xx + cw6 + 0.06, 3.65, 0.26, 0.24, fill=TINT_40,
                    shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
            t.rotation = 90
    text(sl, MARGIN, 5.50, BODY_W, 1.2,
         [[("変えてよいのは accent1 と、表紙・フッターの文字だけ。", {"bold": True, "color": TOKENS["dk2"]})],
          [("帯の高さ、罫の位置、文字サイズ階層を資料ごとに変えると、"
            "そのファイルはもうこの標準の外にいる。変えたくなったらこのファイルを直して、"
            "次からの全部に効かせる。", {})]],
         size="small", line_spacing=1.5, space_after=8)

    # --- 16 裏表紙 ----------------------------------------------------------
    sl = s()
    box(sl, 0, 0, SLIDE_W, SLIDE_H, fill=TOKENS["dk2"])
    box(sl, 0, 0, SLIDE_W, 0.22, fill=TOKENS["accent1"])
    text(sl, MARGIN, 3.05, BODY_W, 1.0, "決め終わったことは、もう決めない。",
         size="section", color="FFFFFF", bold=True, align=PP_ALIGN.CENTER,
         font=TOKENS["font_major"], line_spacing=1.2)
    text(sl, MARGIN, 4.25, BODY_W, 0.6,
         f"{TOKENS['name']}  —  {TOKENS['owner']}", size="small", color="A9A7BD",
         align=PP_ALIGN.CENTER, font="Arial")
