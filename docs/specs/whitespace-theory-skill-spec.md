# 余白理論のHTML Deck Skill導入仕様書

ステータス: 実験実装済み仕様（DOM構図ゲートを追加）  
作成日: 2026-09-06  
対象Skill: `skills/html-deck`  
前提: 現行の1600×900固定キャンバス、PlaywrightによるDOM実測、`gates.json`、`slide-critic`／`deck-critic`の差し戻しループを維持する。

## 1. 目的

余白を「センス」や「空いている面積」ではなく、次の4つを測る設計契約としてSkillへ追加する。

1. 主張を端から守る。
2. 同じ意味の要素を群化し、異なる意味の要素を分離する。
3. 視線の入口と読み順をつくる。
4. 詰まりすぎ・空きすぎ・死んだ空白を、人の判断へ効率よく送る。
5. 親フレームの配分破綻（兄弟の重なり、中央ずれ、子群の片寄り、過大な接続スロット、
   gapの二重所有）を、生成直後に決定的に止める。

導入後も、余白の質そのものは自動合否の絶対値ではない。ただし、構図フレームの幾何契約を
破るものは、余白の好みではなくDOM配分の破綻なので `block` とする。

## 2. Ponytail方針

この仕様は、`ponytail`のフル強度を前提にする。

- 新しいMLモデル、眼球運動カメラ、外部フォント、追加のレイアウトエンジンは導入しない。
- 既存のPlaywright実測値、DOM矩形、`gates.json`、批評エージェントを再利用する。
- `text_area_ratio`を捨てず、全体の占有率と役割を分離して追加する。
- 黄金比の自動配置やテンプレート大量追加はしない。
- 余白の目的が宣言されていない例外だけを、人にレビューさせる。
- しきい値を増やしすぎず、数値を返す純粋な小関数を1つの測定経路に集約する。
- 実デッキで偽陽性が確認されるまでは、既存のblock条件を広げない。
- block対象は、今回の5指摘に共通する親フレームの破綻に限定する。小さな内部カードは対象外とする。

要するに、**既存のDOM計測に「意味グループ間の距離」と「空白の配分」を足し、批評に余白の目的を読ませる**。これが最短の導入経路である。

現在の実装では、これに加えて大きなgrid/flex・表・比較領域の直接の兄弟を実矩形で比較し、
`metrics.layout` と5種類のblock findingを返す。

## 3. 非目的

- スライドを黄金比に自動変形すること。
- すべての空白を同じ割合にすること。
- 研究の数値だけで美的評価を自動化すること。
- PowerPointの編集可能な`.pptx`を生成すること。
- 画面サイズ・視距離・プロジェクタ環境を知らずに視角を推定すること。
- 「余白が多いほど良い」という単純なランキングを導入すること。

## 4. 用語・データ契約

### 4.1 任意のHTML属性

既存デッキを壊さないため、属性は段階導入とし、未指定時は現在のDOM構造から推定する。

```html
<main class="content"
      data-space-intent="separation"
      data-space-profile="oral">
  <section class="hero" data-space-group="hero" data-space-role="primary">
    <h2>主張を1文で置く</h2>
  </section>
  <figure data-space-group="evidence" data-space-role="figure">
    ...
  </figure>
</main>
```

#### `data-space-role`

| 値 | 対象 | 面積計測 | 入口候補 |
| --- | --- | --- | --- |
| `primary` | 主張・結論・主数字 | 含める | 強く加点 |
| `body` | 本文・説明 | 含める | 通常 |
| `figure` | SVG・図・画像 | 含める | 面積と位置で加点 |
| `source` | 出典・脚注・注記 | 含めるが低重み | 除外 |
| `decoration` | 装飾・背景以外の飾り | 除外 | 除外 |
| `background` | 全面背景・写真の下地 | 除外 | 除外 |

未指定時の推定順は、`figure`／`img` → `.slide-footer .source, .caption, .footnote` → 見出し → その他の可視要素とする。

#### `data-space-group`

意味的に同じグループに属する要素の識別子。未指定時は、`.content`直下の可視子要素を仮グループとする。スライド固有の絶対配置が多い場合は、実装者が明示する。

#### `data-space-intent`

空白の主目的。複数指定はカンマ区切りとする。

```text
edge         外周保護
separation   グループ分離
hero         主張の孤立・強調
breath       画面の呼吸
figure       図の周囲の内側余白
full-bleed   全面写真・全面図
```

### 4.2 `deck.md`との対応

`storyboard`の`job`と`data-space-intent`を完全に二重管理しない。

- 通常は`job`から初期プロファイルを推定する。
- 例外（宣言、全面写真、表紙、ポスター）だけ`data-space-intent`を明示する。
- `deck.md`に「余白の意図」を残したいときは、`## constraints`に1行書く。
- 数値を外す判断は既存の`## accepted`へ積む。余白だけ別台帳を作らない。

### 4.3 プロファイル

既存の`situation`と矛盾しない範囲で、次の初期プロファイルを使う。

| `data-space-profile` | `whitespace_ratio`目標 | `text_ink_ratio`目標 | 備考 |
| --- | ---: | ---: | --- |
| `oral` | 0.30〜0.55 | 0.05〜0.20 | 話しながら見せる |
| `handout` | 0.25〜0.40 | 0.10〜0.30 | 置いて読ませる |
| `poster` | 0.30〜0.40 | 0.10〜0.25 | 図40〜50%を別途目標 |
| `declaration` | 0.40〜0.65 | 0.03〜0.15 | 1主張＋余白を優先 |
| `full-bleed` | 0.05〜0.35 | 0.03〜0.20 | 背景を空白と数えない |

これらはreview用の開始値であり、合否の真理ではない。`poster`の配分はポスターガイド、`group_separation_ratio`の1.5はGestalt研究、行長とコントラストは既存Skill／WCAGを根拠とする。詳細な出典は[調査報告](../research/report-source.md)を正本とする。

## 5. 測定仕様

### 5.1 入力矩形の作り方

`check_deck.py`の既存`EXTRACT_JS`を拡張し、可視要素ごとに次を返す。

```json
{
  "sel": "main.content > section.hero",
  "box": {"x": 80, "y": 160, "w": 820, "h": 180},
  "spaceRole": "primary",
  "spaceGroup": "hero",
  "spaceIntent": ["hero"],
  "semantic": true
}
```

実装規則:

- `background`と`decoration`は占有率から除外する。
- `source`は占有率には含めるが、入口候補・グループ密度からは除外する。
- 親子の矩形を二重加算しない。まず最小の意味ブロックを採用し、親が背景色面を持つ場合だけ親を採用する。
- `text_area_ratio`は既存どおり、文字の行矩形で測る。
- SVG・画像は既存の`figures`情報を使い、背景画像を新しいsemantic occupied areaへ含めない。

### 5.2 面積

```text
A_canvas = 1600 × 900
A_occupied = area(union(semantic rectangles))
occupied_ratio = A_occupied / A_canvas
whitespace_ratio = 1 - occupied_ratio
```

最初の実装は、既存依存だけで済む矩形unionを使う。厳密なピクセル画像処理はしない。

- 水平方向の走査線で矩形を分割し、各区間のunion長を足す。
- 透明部分や写真内部の空白はDOMでは分からないため、画像は要素矩形を占有とみなす。
- 面積誤差は小数第2位で丸める。
- 閾値境界の±0.03は、丸めとDOM箱の誤差としてreviewメッセージに明記する。

### 5.3 外周距離

```text
margin_i = min(x_i, y_i, W - (x_i + w_i), H - (y_i + h_i))
outer_margin_min_px = min(margin_i)
```

判定:

- キャンバス外: 既存どおり`block: canvas_overflow`。
- semantic要素の最小外周が48px未満: `review: space_edge_tight`。
- 目標値は左右80px、上56px、下48px。`safe_inset_px=48`は変更しない。

背景・全面写真は外周違反の対象外とし、`full-bleed`プロファイルの例外にする。

### 5.4 グループ分離

グループ内距離を`g_in`、異なるグループ間の最近接距離を`g_out`とする。

```text
g_in  = 同じgroup内の主要要素の最近接距離の中央値
g_out = 異なるgroup間の最近接距離の中央値
group_separation_ratio = g_out / max(g_in, 1)
```

判定:

- `g_in`または`g_out`が計測不能な1グループ以下のスライド: `info`のみ。
- 2グループ以上で、`g_out / g_in < 1.5`: `review: weak_group_separation`。
- `data-space-intent`に`separation`がなくても、比較・因果・構造のjobでは計測する。
- グループ間距離の比率は、Gestaltの相対距離研究を移植した初期ヒューリスティックであり、blockにはしない。

### 5.5 空白の連結領域

DOM矩形を32×18セルへ量子化し、semantic要素が占めるセルを埋める。

```text
largest_void_ratio = 最大の空セル連結成分の面積 / A_canvas
```

判定:

- `largest_void_ratio > 0.30`かつ`hero`／`breath`／`full-bleed`がない: `info: possible_dead_space`。
- `largest_void_ratio > 0.30`かつ上記intentがある: 情報を出さない。
- セル境界による誤差があるため、詳細値は`0.01`単位で表示しない。`0.30`など2桁の比率のみ返す。

この指標は「大きな空白がある」ことしか言えない。死んだ空白かどうかは`slide-critic`がスクリーンショットで判断する。

### 5.6 視線の入口候補

眼球運動を直接測らず、次の代理スコアを作る。

```text
entry_score = normalized(area)
            + normalized(font_size)
            + normalized(contrast)
            + isolation_bonus
            + primary_role_bonus
```

候補は`source`・`decoration`を除外し、上位スコアの要素を同点統合する。

判定:

- 入口候補0: `review: no_entry_candidate`。
- 入口候補1〜2: 合格。
- 入口候補3以上: `review: split_entry`。

このスコアは実際の注視順ではない。批評エージェントが「3秒でどこを見たか」を上書きできるよう、数値は補助証拠としてのみ渡す。

### 5.7 間隔のリズム

主要要素の上下左右距離から、0より大きい間隔を抽出する。

```text
gap_rhythm_cv = stdev(gaps) / mean(gaps)
```

初期判定:

- 主要間隔が3個未満: 判定しない。
- `gap_rhythm_cv <= 0.75`: 情報なし。
- `gap_rhythm_cv > 0.75`: `info: spacing_rhythm_noise`。

これは数学的に等間隔であることを要求しない。主張、図、出典の役割が違うスライドに、機械的な等間隔を押し付けないため、reviewにもせずinfoから始める。

### 5.8 既存指標との関係

| 既存指標 | 扱い | 理由 |
| --- | --- | --- |
| `safe_inset_px` | 維持 | 外周保護の最低値 |
| `text_area_ratio` | 維持 | 文字インク量。新しい空白率とは別物 |
| `text_area_ratio_min/max` | 維持 | 文字の詰まり／薄さの補助 |
| `figure_min_area_ratio` | 維持 | アイコンで図の被覆を誤魔化さない |
| `figure_slide_ratio_min` | 維持 | デッキ全体の文字壁防止 |
| `min_hierarchy_ratio` | 維持 | 入口候補の強さを補う |
| `weak_hierarchy` | 維持 | 入口の数ではなくサイズ階層を測る |
| `underfilled` | 維持 | 文字が少ない情報の補助。ただし余白の意図を優先 |

### 5.9 構図フレームのDOM幾何

今回のレビューで明らかになった「親と子が同じ余白を取る」「固定幅の表が左へ寄る」「
右だけ空いて子群がずれる」「矢印列が内容を圧迫する」「評価ループ後に兄弟が重なる」を、
余白率とは別の決定的契約にする。

対象は次のいずれかを満たす、可視子が2つ以上の領域である。

- `data-space-frame` を持つ。
- `TABLE`、または `compare` / `table` / `composition` クラスを持つ。
- 幅720px以上または高さ420px以上の `grid` / `flex`。

子の直接兄弟だけを比較し、親子の包含は正常として除外する。

| 指標 | 式 / 閾値 | finding | severity |
| --- | --- | --- | --- |
| 兄弟重なり | 交差面積64px²以上、かつ小さい側の2%以上 | `layout_overlap` | block |
| 構図の中央ずれ | キャンバス中央から16px超 | `composition_off_center` | block |
| 子群の片寄り | 子union中心が親内側中心から16px超 | `layout_child_shift` | block |
| コネクタ列の過大化 | 軸方向96px超、または親内側の12%超 | `connector_track_wide` | block |
| 間隔の二重所有 | 親gapと隣接子marginが各12px以上 | `redundant_gap_owner` | block |

`data-space-intent="overlay"` は意図したレイヤー表現の重なりだけに使う。左寄せ・端寄せ・
全面表示は `left` / `start` / `edge` / `full-bleed` を宣言する。例外のために閾値を緩めない。

修復は、親フレームの幅 → 兄弟トラック → gapの所有者 → 子padding → 文字・図形の順で行う。
`left`・`transform` の微調整は検査を隠すだけなので、blockの修復手段にしない。

## 6. `gates.json`追加案

既存キーを変更せず、次のnamespaceを追加する。面積率の閾値は通常スライドの検知用で、プロファイルがある場合はプロファイルを優先する。初期リリースでは、外周以外の所見を`info`または`review`に限定する。

```json
"space": {
  "margin_target_px": 80,
  "margin_min_px": 48,
  "whitespace_review_min": 0.20,
  "whitespace_review_max": 0.60,
  "largest_void_info_ratio": 0.30,
  "group_gap_ratio_min": 1.5,
  "entry_candidate_max": 2,
  "gap_rhythm_cv_info_max": 0.75,
  "void_grid_cols": 32,
  "void_grid_rows": 18,
  "layout_overlap_area_min_px": 64,
  "layout_overlap_share_block": 0.02,
  "layout_center_tolerance_px": 16,
  "layout_child_shift_tolerance_px": 16,
  "connector_track_max_px": 96,
  "connector_track_max_ratio": 0.12,
  "redundant_gap_min_px": 12
}
```

余白率・群化比・最大空白は引き続き review/info。上のDOM幾何5項目だけはblockにする。

## 7. `check_deck.py`変更仕様

### 7.1 変更箇所

| 箇所 | 変更 |
| --- | --- |
| `EXTRACT_JS` | space属性、semantic要素、グループ、intentを返す |
| `EXTRACT_JS` | 大きなgrid/flex・表・比較の直接兄弟と実矩形を `layoutRegions` として返す |
| `evaluate()` | space metricsを計算し、既存findingsへ追加 |
| `evaluate()` | `metrics.layout` と5種類のDOM幾何blockを追加 |
| `deck_level()` | スライド間の空白率の波と空白なし連続を出す |
| `report.json` | `metrics.space`を追加。既存キーは壊さない |
| 標準出力 | 既存の1行サマリへ`空白率`と`群化比`を追加 |

### 7.2 `report.json`の出力形

```json
{
  "metrics": {
    "ja_chars": 210,
    "text_area_ratio": 0.14,
    "space": {
      "occupied_ratio": 0.63,
      "whitespace_ratio": 0.37,
      "outer_margin_min_px": 80,
      "largest_void_ratio": 0.18,
      "group_count": 2,
      "group_separation_ratio": 1.67,
      "entry_candidate_count": 1,
      "gap_rhythm_cv": 0.42,
      "profile": "oral",
      "intent": ["separation"]
    }
  }
}
```

### 7.3 findingコード

| コード | severity | 条件 | 文言の方向 |
| --- | --- | --- | --- |
| `space_edge_tight` | review | semantic要素が48px未満 | 外周を戻すか、例外を宣言 |
| `weak_group_separation` | review | 比率が1.5未満 | 内部よりグループ間を広げる |
| `split_entry` | review | 入口候補が3以上 | 入口を1〜2箇所へ絞る |
| `possible_dead_space` | info | 大きな空白連結領域＋intentなし | 図の再配置／意図宣言を検討 |
| `spacing_rhythm_noise` | info | CVが0.75超 | 間隔トークンを整理するか、役割差を説明 |
| `space_profile_mismatch` | review | プロファイルの範囲外 | まず分量／配置を見直す |
| `layout_overlap` | block | 兄弟の実矩形が閾値以上に重なる | 親のgrid/flexへ戻す |
| `composition_off_center` | block | 中央構図が16px超ずれる | `margin-inline:auto` 等で親を中央化 |
| `layout_child_shift` | block | 子群のunionが親内側中心から16px超ずれる | 固定列・空き列を再配分 |
| `connector_track_wide` | block | 接続スロットが96px/12%超 | コネクタ列を縮め内容へ返す |
| `redundant_gap_owner` | block | 親gapと子marginが同じ間隔を二重所有 | gapかmarginの一方を0にする |

`space_profile_mismatch`は初回リリースで必須にしない。実デッキの分布を収集してから有効化する。最初から範囲外を大量に出すと、レビューが数値合わせになるためである。

## 8. ドキュメント変更仕様

### 8.1 `references/quality-contract.md`

既存の「余白」節を拡張し、次を追加する。

- 余白の5層（キャンバス、ブロック、グループ、文字組版、図形）。
- `whitespace_ratio`と`text_area_ratio`の違い。
- `outer_margin_min_px`の48／80px。
- `group_separation_ratio >= 1.5`を初期目標として紹介。
- `oral`、`handout`、`poster`、`declaration`のプロファイル表。
- 30／40／20配分はポスターのguidelineであり、普遍法則ではないという注記。
- 黄金比は参考比率で、ゲートにしないという禁止事項。

### 8.2 `references/layout-playbook.md`

既存の「形はjobから決める」の前に、次の手順を追加する。

```text
claim/jobを決める
→ 入口を1つ予約する
→ 外周を確保する
→ グループ内を詰める
→ グループ間を1.5倍以上空ける
→ 残った空白に目的を付ける
→ 面積・距離・行長を測る
```

さらに、宣言スライド、比較、因果、構造、数量、全面写真の各jobについて「空白をどこに割り当てるか」を1行ずつ追加する。

### 8.3 `SKILL.md`

変更は最小限にする。

- 手順3または手順4に「レイアウト実装前に余白プロファイルを決める」と1段落追加。
- 手順5の検査一覧に`whitespace_ratio`、`group_separation_ratio`、`split_entry`を追加。
- 手順5に`metrics.layout`と5種類のDOM幾何blockを追加し、「余白率の違反はreview/info、
  親フレームの配分破綻はblock」と明記。
- `data-space-intent`の例外宣言を、`deck.md`の`accepted`と紐づける。

既存の説明を別の章へ重複コピーしない。詳しい根拠は`quality-contract.md`と調査報告へ寄せる。

### 8.4 `agents/slide-critic.md`

既存の`density`、`entry`、`craft`へ以下を追加する。

- 空白率の数値が範囲内でも、空白が意味グループを分けているかを見る。
- `possible_dead_space`は自動的に悪とせず、主張の孤立・呼吸・図の視線誘導として機能しているか確認する。
- `split_entry`は「入口が多い」という指摘だけでなく、残す入口と下げる要素を指定する。
- `weak_group_separation`は、内部24px／外部40pxのように具体的な修正値を書く。
- `data-space-intent`をユーザーの意図として扱い、好みで蒸し返さない。

`metrics`のJSON例:

```text
space: whitespace 37%, margin 80px, group ratio 1.67, entry 1, largest void 18%
```

### 8.5 `agents/deck-critic.md`

既存の`rhythm`と`visual_balance`へ以下を追加する。

- スライドごとの空白率を時系列で見て、全枚が同じ密度になっていないか確認する。
- 空白率の波がある場合、ストーリー上の導入・展開・結論と一致しているか確認する。
- `text_only_streak`と空白率を別物として扱う。図があっても全体が詰まっていれば文字壁になり得る。
- 空白率が高いスライドを一律に削らず、宣言・章扉・結論の役割を確認する。

## 9. テスト仕様

### 9.1 純粋関数テスト

新しい測定ロジックはPlaywrightを起動しない純粋関数として分離し、既存の
`scripts/test_space_metrics.py`へ自己チェックを追加する。フレームワークは使わず、
既存方針どおり`assert`でよい。

必須ケース:

1. 重なった2矩形のunion面積が二重加算されない。
2. 外周80pxの矩形が`margin_target`を満たす。
3. 40pxの矩形が`margin_min`未満として検出される。
4. `g_in=24, g_out=40`で比率1.67になる。
5. `g_in=32, g_out=32`で比率1.0となりreview条件になる。
6. 全面背景が占有率へ入らない。
7. `hero` intentの大きな空白が`possible_dead_space`を出さない。
8. 入口候補2は合格、3は`split_entry`になる。
9. 小数境界（0.20、0.60、1.5）で比較が逆転しない。
10. 構図フレームの兄弟重なり、中央ずれ、子群片寄り、過大なコネクタ、gap二重所有を検出する。

### 9.2 HTML fixtureテスト

一時ディレクトリに最小の3枚デッキを生成し、既存の`check_deck.py`を通す。

| fixture | 期待 |
| --- | --- |
| `space-good` | block 0。space reviewなし |
| `space-tight` | block 0。`space_edge_tight`あり |
| `space-dead-void` | block 0。intentなしは`possible_dead_space`、intentありはなし |
| `space-split-entry` | block 0。`split_entry`あり |

新しい余白所見は、初期リリースでは終了コードを1にしない。既存の壊れたデッキの納品を止めるのは、overflow・clipping・画像未読込など物理的破損に限定する。

### 9.3 Skill eval

`evals/evals.json`へ1ケース追加する。

期待する挙動:

- 口頭発表と判断した場合、`deck.md`のconstraintsに余白プロファイルと1枚300字を残す。
- 比較・因果・構造・数量のいずれかを、箇条書きではなく図／空白分離へ変換する。
- `quality-contract.md`を参照し、30〜40%を普遍則と断定しない。
- 黄金比を必須ルールにしない。
- `accepted`に例外の理由を残す。

## 10. 実装順序

Ponytailに従い、最小の差分で段階導入する。

### Phase 1: 根拠と宣言場所

1. `quality-contract.md`に余白の定義・プロファイル・注意書きを追加。
2. `layout-playbook.md`に空白先行の手順を追加。
3. `slide-critic.md`／`deck-critic.md`に余白の読み方を追加。
4. `SKILL.md`に導入点を1段落追加。

この段階だけでも、LLMが「空白を埋める」方向へ暴走するのを抑えられる。

### Phase 2: 最小計測

1. `EXTRACT_JS`に属性とsemantic矩形を追加。
2. 矩形union、外周、グループ距離比、空白連結領域を実装。
3. `metrics.space`とreview/infoのfindingを追加。
4. `test_space_contract.py`とHTML fixtureを追加。

### Phase 3: デッキ全体への接続

1. `deck_level()`に空白率の時系列と大きな空白の連続を追加。
2. `report.json`の標準出力とコンタクトシートのラベルへ反映。
3. `evals.json`へケース追加。

### Phase 4: 再校正

最低10デッキ、最低100スライドの実測結果を集め、次を確認してから閾値を動かす。

- `whitespace_ratio`とslide-criticの`density`スコアの関係。
- `group_separation_ratio`と`fit`／`craft`の関係。
- `possible_dead_space`の偽陽性率。
- `split_entry`が本当に「入口の割れ」と一致している割合。

校正前は新しい所見をinfo/reviewに留める。ラウンド途中で値を緩めないという既存ルールを維持する。

## 11. 受け入れ条件

### 必須

- [ ] 既存の全テストが通る。
- [ ] 既存の`metrics`キーと終了コードの意味を壊さない。
- [ ] `report.json`に`metrics.space`が出る。
- [ ] `report.json`に`metrics.layout`が出る。
- [ ] 1600×900で外周、占有率、空白率、グループ距離比、入口候補を再現可能に測れる。
- [ ] 背景・装飾・出典の扱いが二重計上されない。
- [ ] 余白率・群化比・最大空白などの美的ヒューリスティックはblockにしない。
- [ ] DOM構図の5契約（重なり・中央ずれ・子群片寄り・コネクタ幅・gap二重所有）はblockにする。
- [ ] `data-space-intent="hero"`、`"full-bleed"`、`"separation"`が例外として機能する。
- [ ] 黄金比をゲートにしない。
- [ ] 3秒の最終判断をslide-criticに残す。

### 品質確認

- [ ] 3枚以上の実デッキで空白率と図被覆の両方が意図どおり出る。
- [ ] 文字の多い比較スライドが、空白率だけを満たして合格しない。
- [ ] 宣言スライドの大きな空白が、intent宣言により誤検知されない。
- [ ] 背景写真の空や透明部分が、空白率を不当に増減させないという限界がレポートに明記されている。
- [ ] `review`が増えすぎた場合に、まず条件を削り、閾値を緩めない。

## 12. 実装しないもの（保留）

次は、測定データなしで追加しない。

- 眼球運動カメラやWebカメラによる実ユーザ視線計測。
- CLIP・Saliencyモデル・画像セグメンテーションによる空白判定。
- 画像内部の「空」をピクセル単位で分類する処理。
- スライドの内容から自動的に最適な余白率を学習するモデル。
- 黄金比・三分割の自動テンプレート。
- 文化・年齢・視力・視距離に応じた個別最適化。

追加条件は、少なくとも「実デッキで偽陽性が繰り返される」「ユーザーが具体的な改善を求める」「その追加が既存の最短経路より小さい」ときのいずれかを満たすこと。

## 14. 今回の実験実装

今回のレビュー5件を受け、次の範囲を実装した。

- `references/whitespace-theory.md` — 一所有者原則、構図フレーム、式、閾値、修復文法。
- `scripts/check_deck.py` — `layoutRegions` のDOM抽出、`metrics.layout`、5種類のblock finding。
- `assets/gates.json` — 64px² / 2%、16px、96px / 12%、12pxの固定値。
- `scripts/test_space_metrics.py` — 兄弟重なり、中央ずれ、子群片寄り、コネクタ幅、gap二重所有の純粋関数テスト。
- `SKILL.md`、`quality-contract.md`、`layout-playbook.md`、`slide-critic.md`、`deck-critic.md` —
  生成前の構図契約と、blockを批評前にゼロにする順序。

未実施のものは、実デッキを自動修復するレイアウトエンジン、黄金比への自動変形、画像内部の
空白判定である。blockが出たときは、親のgrid/flexを直す人間または修正担当へ返す。

## 13. 実装担当への短い指示

最初のPRでは、`SKILL.md`、`quality-contract.md`、`layout-playbook.md`、`slide-critic.md`、`deck-critic.md`、`gates.json`、`check_deck.py`、`test_space_contract.py`の範囲に閉じる。テンプレートやレビューサーバーは触らない。

最小の完成形は次である。

```text
空白率を測る
→ 群化の距離比を測る
→ 入口の割れを報告する
→ 余白の目的を批評に渡す
→ 実データが集まるまで閾値を増やさない
```
