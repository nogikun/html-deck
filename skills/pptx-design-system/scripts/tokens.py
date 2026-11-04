"""design.pptx のデザイントークン — 色・グリッド・文字サイズ。

ここだけが「デザインで決めること」。別案件向けに作り直すときは、
このファイルの TOKENS を書き換えるだけで済むようにしてある。
"""

from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Emu

# ---------------------------------------------------------------- トークン

TOKENS = {
    "name": "Presentation Design System",
    "owner": "nogikun",
    # テーマ配色 12 スロット。PowerPoint の「色のカスタマイズ」に並ぶ順。
    "dk1": "212121",  # 本文
    "lt1": "FFFFFF",  # 紙
    "dk2": "3F3D56",  # 帯・濃い面
    "lt2": "EEF0F4",  # 面。白地の上で境界が見える明度に置く (罫線の代わり)
    "accent1": "6C63FF",  # 主役 / ブランド  ← 案件ごとに差し替える唯一の色
    "accent2": "FF9800",  # 強調・数値
    "accent3": "098544",  # 肯定・達成
    "accent4": "C00000",  # 否定・リスク
    "accent5": "0070C0",  # 参照・情報
    "accent6": "747474",  # 中立・抑制
    "hlink": "0070C0",
    "folHlink": "747474",
    # 書体
    "font_major": "Noto Sans JP Medium",  # 見出し。太さはウェイトで持ち、ボールドは掛けない
    "font_minor_ea": "Noto Sans JP",  # 本文 (和文)。見出しと同じ家族で、Mac・Windows・Linux すべてで使える
    "font_minor_latin": "Arial",  # 本文 (欧文)
}

# テーマスロットに入らない運用色
GREY_RULE = "D9D9D9"  # 罫線。軸と色見本の輪郭だけに使う (面の区切りには使わない)
GREY_SUB = "747474"  # 補足テキスト
TINT_40 = "C4C1FF"  # accent1 40%
TINT_20 = "E2E0FF"  # accent1 20%
SHADE_80 = "564FCC"  # accent1 80%

# ---------------------------------------------------------------- グリッド
# 13.333 x 7.5 in (16:9)。既存資料の 16:10 版 (10 x 6.25) を横 x1.333 / 縦 x1.2 した値。

SLIDE_W, SLIDE_H = 13.3333, 7.5
MARGIN = 0.92  # 左右の外周マージン
BAND_H = 1.00  # タイトル帯の高さ
RULE_Y = 1.04  # 帯直下のアクセント罫
RULE_H = 0.042  # 同 3pt 相当。マスター側と同じ値を使う
BODY_T = 1.35  # 本文領域の上端
BODY_B = 6.70  # 本文領域の下端
FOOT_Y = 6.94  # フッター帯の上端
FOOT_H = SLIDE_H - FOOT_Y
BODY_W = SLIDE_W - MARGIN * 2

# タイプスケール (pt)
SZ = {
    "hero": 54,
    "cover": 44,
    "section": 40,
    "title": 36,
    "lead": 24,
    "body": 20,
    "small": 16,
    "note": 12,
}

EMU_IN = 914400


def E(inches: float) -> Emu:
    return Emu(int(round(inches * EMU_IN)))


def rgb(hexstr: str) -> RGBColor:
    return RGBColor.from_string(hexstr)
