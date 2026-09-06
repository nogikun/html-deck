# PptxGenJSによるhtml-deckのPPTX化調査

- 調査日: 2026-09-06
- 対象: `work/ctfp-for-new-engineers-deck`
- 判断: 既存HTMLをPptxGenJSへ直接渡す一行変換は不可。既存のPDFを画像として置くPPTXは生成可能。編集可能性を残すにはHTMLからPptxGenJSのテキスト・図形・画像・SVGオブジェクトへ写像する変換層が必要。

## 一次資料

- PptxGenJS公式 HTML-to-PowerPoint: https://gitbrent.github.io/PptxGenJS/docs/html-to-powerpoint/
- PptxGenJS公式 Quick Start: https://gitbrent.github.io/PptxGenJS/docs/quick-start/
- PptxGenJS公式 Text API: https://gitbrent.github.io/PptxGenJS/docs/api-text/
- PptxGenJS公式 Images API: https://gitbrent.github.io/PptxGenJS/docs/api-images/
- PptxGenJS公式 Shapes API: https://gitbrent.github.io/PptxGenJS/docs/api-shapes.html
- PptxGenJS公式実装（`tableToSlides`）: https://github.com/gitbrent/PptxGenJS/blob/master/src/pptxgen.ts

## 既存デッキの棚卸し

最新の `ctfp-for-new-engineers-deck` は、16枚の独立した `<article class="slide">` で構成され、キャンバスは1600×900pxに固定されている。スライドHTML全体には、インラインSVGが13個、`<table>` が0個、`<img>`・`<canvas>`・`<iframe>`・`<script>`・動画・音声が0個ある。レイアウトは共有CSSと各スライドのCSSで `grid` / `flex` を使い、テーマはCSS変数で管理される。アニメーション定義はあるが、印刷時には無効化される。

公式のHTML機能は任意のHTMLではなく、`tableToSlides(tableElementId)` によるHTML `<table>` の再現である。公式実装も `document.getElementById()` で対象を取得し、テーブルの行・列・セルスタイルをPowerPointの表へ変換する。したがって、現在の `<article>` ベースのデッキはこのAPIの入力形式に該当しない。

## 実験

1. `pptxgenjs@4.0.1` を一時領域へ取得した。
2. 既存PDFを1600×901pxのPNG 16枚へ変換し、PptxGenJSで各ページを1枚の画像として配置したPPTXを生成した。16スライド、1.6MB、OOXML ZIP検証は成功した。
3. 01枚目だけ、既存HTMLから文言とインラインSVGを取り出し、PptxGenJSのテキスト11個＋SVG画像1個へ手動写像したPPTXを生成した。OOXML上は `p:sp` 11個、`p:pic` 1個、テキストノード11個で、編集可能な部品が作れることを確認した。
4. `tableToSlides("slide")` を実行すると `Table ID "slide" does not exist!` となった。既存のスライドは表ではないためである。
5. LibreOfficeによる再レンダリングは、ユーザーがインストール後に追加確認する前提で保留した。

## 実装した変換層

`skills/html-deck/scripts/export_pptx.py` を追加した。既存のhtml-deckと同じChrome/Playwrightの固定1600×900px環境で各HTMLを開き、計算済みCSS、`getBoundingClientRect()`、文字ごとの `Range.getClientRects()` からDeckIRを生成する。DeckIRは `TextLine / Shape / Line / SVG / Image` の最小集合を持ち、`skills/html-deck/scripts/emit_pptx.mjs` がPptxGenJSの `addText` / `addShape` / `addImage` へ変換する。

CSSレイアウトをPptxGenJSで再実装せず、Chromeで解決済みの矩形を次の変換でインチへ落とす。

`x_in = x_px / 120`, `y_in = y_px / 120`, `w_in = w_px / 120`, `h_in = h_px / 120`

テキストはDOM要素の幅をそのままPPTXへ渡さず、ブラウザ上で同じ行に描画された文字の矩形を集約して `TextLine` にする。各行は `wrap=false`、`fit=none`、余白0で出力するため、PowerPointのフォントエンジンに再折返し・自動縮小を任せない。背景色は要素ごとの塗り、境界線は上・右・下・左の4本へ分解する。SVGは `viewBox=(V_w,V_h)` と元のCSS枠 `(W,H)` から `s=min(W/V_w,H/V_h)` を計算し、`(sV_w,sV_h)` を枠中央へ配置する。これにより、PowerPointの画像外枠にもSVG標準の `preserveAspectRatio="xMidYMid meet"` を反映する。インラインSVG内の `var(--token)` は、ブラウザで解決したテーマ値へ置換してからdata URI化する。

修正版を最新16枚デッキで実行した結果:

- TextLine: 220
- Shape: 17
- Line: 63
- SVG: 13
- 出力: `work/ctfp-for-new-engineers-deck/ctfp-for-new-engineers-deck.pptx`
- 16スライド生成成功、OOXML ZIP検証成功
- 生成XMLにPowerPointの `<a:normAutofit>` / `<a:spAutoFit>` なし
- 既存 `check_deck.py --no-shots`: `block 0`

未確認なのはPowerPoint/Keynoteで開いた際の最終的な見た目だけである。LibreOfficeは未導入のため再レンダリング検査はできない。PptxGenJS側の構造生成、行単位のテキストrun、背景・境界線、SVGのCSS変数解決、既存HTMLの品質検査は確認済み。

実験生成物（暫定）:

- `/private/tmp/pptxgenjs-lab/ctfp-raster.pptx`
- `/private/tmp/pptxgenjs-lab/ctfp-editable-bridge-slide01.pptx`

## 変換の形式化

HTMLスライドを、DOM木 `D=(V,E)`、ブラウザの計算済みスタイル `C(v)`、実測矩形 `B(v)=(x_v,y_v,w_v,h_v)`、塗り順 `z_v` の組とする。PptxGenJSが扱う基本オブジェクトを

`P = Text × Shape × Image/SVG × Table × Chart/Media`

とする。編集可能な変換とは、次を満たす写像 `F: D → P*` が存在することと定義する。

`RenderHTML(D) ≈ RenderPPTX(F(D))`

ここで `≈` は、少なくともすべての可視要素 `v` について、対応オブジェクト `p=F(v)` が

`|x_p-x_v/120| ≤ ε_x`, `|y_p-y_v/120| ≤ ε_y`, `|w_p-w_v/120| ≤ ε_w`, `|h_p-h_v/120| ≤ ε_h`

を満たし、文字列・色・線・塗り・前後関係が同値であることを意味する。1600×900pxの16:9スライドでは `1 inch = 120px` とし、PptxGenJS座標は `(x/120,y/120,w/120,h/120)`、CSS pxの文字サイズ・線幅は `72/120 = 0.6pt/px` に変換する。`0.75pt/px` はCSSの96dpiとPowerPointの物理単位だけを結び、今回の120px/inのスライド座標変換とは整合しない。

### 崩れを説明するより厳密なモデル

HTML要素の矩形は「その要素が占めるレイアウト領域」であって、「文字が実際に描かれた領域」ではない。テキスト要素 `e` の文字・空白・改行を、ブラウザが返す文字片

`g_k = (s_k, r_k, q_k)`, `r_k = (left_k, top_k, right_k, bottom_k)`, `q_k = (font, size, weight, color, ...)`

の列として観測する。`|top_i - top_j| <= τ`（実装では `τ=1px`）かつ同じ強制改行区間に属する文字片を同じ行とする。この同値類 `L_j` から、行の矩形を

`B(L_j) = (min left_k, min top_k, max right_k - min left_k, max(max bottom_k - min top_k, lineHeight_j))`

で作る。今回の `TextLine` はこの `B(L_j)` と、隣接する同一スタイル文字片をまとめたrunだけを持つ。

したがって出力は、要素単位の

`addText(text_e, x_e, y_e, w_e, h_e, wrap=true)`

ではなく、行単位の

`addText(runs(L_j), x_j/120, y_j/120, w_j/120, h_j/120, margin=0, wrap=false, fit=none)`

である。前者ではPowerPointのフォントメトリクス `M_p` が改行関数 `W_p(text, w_e, M_p)` に入り、ブラウザの `W_b` と異なると、後続行の `y` と要素の占有高さまで連鎖的に変わる。後者では改行関数を変換前に固定するため、フォント差は原則としてその行の横幅・字形差に局所化され、他要素の配置を押し下げない。

背景も同じく要素を一つの「見た目」として扱わず、ペイント命令へ分解する。要素 `e` のペイントを

`Paint(e) = Fill(B_e, color_e) ∪ {Border_s(B_e, color_s, width_s) | s ∈ {top,right,bottom,left}}`

とし、`Fill` は `Shape`、各 `Border_s` は `Line` へ写像する。これにより `border-left`、`pre` の背景、直接テキストを持つ `.callout` など、HTML要素の種類に依存せず計算済みCSSの塗りを拾える。`background-image`、疑似要素、shadow、filter、mask、clip-path、canvasは別のペイント記録が必要であり、現実装では完全再現の対象外として警告する。

旧実装の主な誤差源は、(1) 要素矩形一つへ全文を押し込んだこと、(2) `fit=shrink` によりPowerPointへ自動縮小を依頼したこと、(3) `border-top` など一部の背景・線しか抽出しなかったこと、(4) 透過している `article.slide` だけを背景色として読み、`body` の `--bg` を継承しなかったこと、の四つである。今回の修正はフォントを推測して数式で合わせるのではなく、ブラウザの観測結果を中間表現へ固定することで、再レイアウトの自由度を減らしている。

### 編集可能変換に必要なHTML条件

各スライドを次の制約付き文法へ縮退させる。

```text
Slide ::= <article class="slide" data-pptx-slide> Paint*
Paint  ::= Text | Shape | Image | Svg | Table
Text   ::= <p|h1|h2|h3|span data-pptx-kind="text"> Run*
Run    ::= plain-text | <span data-pptx-run="...">plain-text</span>
Shape  ::= <div data-pptx-kind="shape" data-pptx-shape="rect|ellipse|line|...">
Image  ::= <img data-pptx-kind="image" src="...">
Svg    ::= <svg data-pptx-kind="svg">...</svg>
Table  ::= <table data-pptx-kind="table">...</table>
```

さらに、以下を満たす必要がある。

1. スライドの描画領域は一つだけで、`W=1600px`, `H=900px`。外部参照・ランタイムスクリプト・ユーザー操作で変化する状態を持たない。
2. すべての塗り要素は `Paint` のいずれか一つに対応し、未対応のCSS描画（`::before/::after` の内容、filter、blend、複雑なshadow、clip-path、mask、canvas描画など）を持たない。
3. 各 `Paint` の矩形 `B(v)`、塗り、線、透明度、z順、テキストの改行位置が確定している。`grid` / `flex` は入力段階で使ってよいが、変換時にはブラウザで計算済み矩形を取得するか、`data-pptx-x/y/w/h` として明示する。
4. テキストは文字列または有限個のスタイル付きrunだけで構成し、`text-wrap: balance`、自動折返し、禁則、可変フォント、疑似要素の文字をPowerPoint側に再計算させない。改行位置を `<br>` または `\n` で固定する。
5. 画像・SVGは自己完結したローカルパスまたはdata URIであり、PowerPointで利用可能な形式である。既存デッキのインラインSVGは、この条件に最も近い。
6. `tableToSlides` を使う場合に限り、該当部分は実HTML `<table>` とし、セル単位のCSSへ制限する。公式仕様ではセル内の単語単位の装飾やネスト表を一般HTMLのようには再現できない。

### 画像一枚化なら条件が緩い

編集可能性を捨てて見た目だけを保存する場合は、各HTMLスライドをブラウザで描画して画像 `I_i` にし、

`slide_i = addImage(I_i, x=0, y=0, w=13.333333, h=7.5)`

とすればよい。この場合の条件は「ブラウザで安定して描画できること」と「画像が自己完結していること」だけで、現在のデッキはすでにほぼ満たしている。ただし、PowerPoint上では文字・SVG・CSSの個別編集はできず、1枚の画像になる。

## 判断

最小の実装は画像一枚化である。編集可能PPTXが必要なら、HTMLをそのまま読む汎用変換器を作るのではなく、html-deck側にPptxGenJS用の意味付け（`data-pptx-kind`、明示矩形、固定改行、色・フォント・z順）を追加し、Text/Shape/Image/SVG/Tableの5種類だけを変換する。既存16枚を完全編集可能にするには、各スライドのHTMLを一度だけこの中間表現へ落とす必要があり、PptxGenJSの追加オプションだけでは解決しない。
