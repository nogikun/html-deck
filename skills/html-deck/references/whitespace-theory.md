# 余白理論 — 余白は要素ではなく構図の予算

この文書は、`html-deck` がスライドを一度で組むためのレイアウト契約である。
余白の多寡を美的な点数に変換するものではない。**どの親が、どの空間を、何のために一度だけ所有するか**を決め、DOMの実矩形で破綻を止める。

## 1. 対象と前提

- キャンバスは 1600×900px。
- 通常の外周は左右80px、上56px、下48px。最低値は48px。
- `text_area_ratio` は文字のインク量、`metrics.space` は意味要素の占有面積、`metrics.layout` は構図フレームの幾何契約を測る。3つを同じ指標として扱わない。
- 透明な写真内部の空や、SVG内部の空白はDOM矩形だけでは判定しない。画像は表示矩形を占有とみなす。
- 黄金比、三分割、均等カード数はゲートにしない。jobに対する理由があるときだけ使う。

## 2. 余白の三層

余白を次の三層に分ける。下の層が上の層の空きを「もう一度」取ってはいけない。

1. **キャンバス余白 `M`** — 端から内容を守る。通常80px、最低48px。
2. **構図フレームの間隔 `G`** — 比較・因果・構造など、兄弟グループの間を分ける。親の `gap` が一度だけ所有する。
3. **内容内余白 `P`** — カードや図の枠内で、文字・線を縁から離す。子の `padding` が所有する。

横方向の構図は次で割る。

```text
A = W - M_left - M_right
A = C_1 + C_2 + ... + C_n + G_1 + G_2 + ... + G_(n-1)
```

`C` は内容領域、`G` は内容領域ではなく分離スロットである。矢印やコネクタを `C` と同じ大きな列に置くと、矢印の左右に空白を抱えたまま内容が縮む。

### 一所有者原則

同じ二要素の間隔を、親の `gap` と隣接する子の `margin-right` / `margin-left` の両方で作らない。

```text
実際の間隔 = 親gap + 前の子の外側margin + 次の子の外側margin
```

親gapが20px、子marginが左右12pxなら、見た目の間隔は44pxになる。`gap` を残すなら子の該当marginを0にする。子marginを残すなら親gapを0にする。`redundant_gap_owner` は、どちらも12px以上のときblockにする。

## 3. 中央配置の契約

比較表・比較構図・中央宣言・大きな構図フレームは、指定がない限りキャンバス中央に置く。

```text
offset_x = |(x + width / 2) - 1600 / 2|
offset_y = |(y + height / 2) - 900 / 2|
offset = max(offset_x, offset_y)
```

`offset <= 16px` を許容し、それを超えたら `composition_off_center` をblockにする。中央に置く実装は、固定座標を微調整するのではなく次のいずれかにする。

```css
.composition {
  width: 1260px;
  margin-inline: auto;
}
```

または、親が作業領域全幅を持つなら、内容を `grid` / `flex` のトラックで中央に割る。左寄せ、端までの配置、全面図は、`data-space-intent="left"`、`start`、`edge`、`full-bleed` のいずれかを明示する。

## 4. 兄弟の重なり

親子の包含は正常なDOM構造なので、重なりとして数えない。比較するのは同じ構図フレームに属する兄弟だけである。

```text
I = area(intersection(child_a, child_b))
share = I / min(area(child_a), area(child_b))
```

次の両方を満たす兄弟重なりは `layout_overlap` としてblockにする。

- `I >= 64px²`
- `share >= 2%`

意図したレイヤー表現だけは、該当子に `data-space-intent="overlay"` を付ける。`overflow: hidden`、`z-index`、`transform` で隠した重なりは修正済みとはみなさない。

## 5. 子群の片寄りと空き列

構図フレームの内側矩形を `F`、直接の子のunion矩形を `U` とする。

```text
child_offset = max(|center_x(U) - center_x(F)|,
                   |center_y(U) - center_y(F)|)
```

`child_offset > 16px` なら `layout_child_shift` をblockにする。特に、左空きと右空きが大きく異なるときは、子要素の見た目ではなく親の固定トラック・空き列・固定幅が原因である。

修復は次の順序に固定する。

1. 構図フレームの内側幅を決める。
2. 兄弟の内容幅と `G` の合計を計算する。
3. `grid-template-columns` を `minmax(0, 1fr)` か、内容に合う固定幅へ戻す。
4. `margin-inline: auto` でフレームを中央に置く。
5. `left`、`right`、`transform: translate` の座標調整を削る。
6. 合計が収まらなければ、余白を無理に消さず、縦積みかスライド分割に戻る。

## 6. コネクタの予算

矢印、線、`middle`、`connector`、矢印だけの文字は、内容領域ではなく接続スロットである。次のどちらかを超えたら `connector_track_wide` をblockにする。

- 軸方向の幅または高さが96px超
- 親の内側軸幅の12%超

明示する場合は次の属性を使う。

```html
<div class="arrow" data-space-role="connector">→</div>
```

初期値は56〜80px程度。コネクタが本当に説明文を含む場合は、コネクタと本文を別の兄弟に分け、`data-space-role="body"` を付けた内容領域として扱う。

## 7. 生成時のレイアウト文法

HTMLを書く前に、各スライドの構図を次の1行にする。

```text
M=80 / frame=composition / axis=row / children=[A, connector, B]
G=40 / connector=64 / align=center / intent=separation
```

実装は必ず、親フレーム → 兄弟トラック → 子のpadding → 文字と図形の順で行う。子を先に置いてから親の空きを埋める方法は、親と子が別々に余白を所有し、今回のレビューに出た「余白が2倍」「右だけ空く」「中央がずれる」を生む。

## 8. 決定的ゲートと人の判断

`html-deck-check` は次を機械的に止める。

| コード | 数値 | 直す対象 |
| --- | ---: | --- |
| `layout_overlap` | 64px² かつ2%以上 | 兄弟の実矩形、親の分割 |
| `composition_off_center` | 中央から16px超 | フレームの中央配置 |
| `layout_child_shift` | 子群中心が16px超 | 固定トラック・空き列 |
| `connector_track_wide` | 96px超または12%超 | 矢印用トラック |
| `redundant_gap_owner` | gapと隣接marginが各12px以上 | 間隔の所有者 |

これらが1件でも残る間は、批評エージェントを起動しない。`metrics.space` の占有率、群化比、最大空白は、目的のある呼吸まで機械的に悪としないため、引き続きreview/infoとして人に渡す。

## 9. レビュー5指摘との対応

| レビューで見えた現象 | 一般化した原因 | ゲート |
| --- | --- | --- |
| 大きな親と中央領域がそれぞれ余白を持つ | 親の分割と子のpaddingが同じ空間を所有 | `redundant_gap_owner` / `connector_track_wide` |
| 表が左に寄る | 固定幅フレームに `margin-inline:auto` がない | `composition_off_center` |
| 右だけ空き、子が左にずれる | 親の固定列の合計が内側幅を使い切らない | `layout_child_shift` |
| 左右タイルが小さく、中央矢印が大きい | コネクタを内容列として予約している | `connector_track_wide` |
| 評価ループで要素が重なる | DOMの兄弟領域を座標で個別調整している | `layout_overlap` |

この表は個別スライドの修正手順ではない。同じDOM原因を次のデッキでも一度で検出するための契約である。
