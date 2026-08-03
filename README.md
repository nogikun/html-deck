# HTML Deck Skill

メモ、記事、調査資料、議事録、URL、口頭の依頼などをもとに、**HTML 形式のスライド資料を作り、検査と改善を繰り返して仕上げるための Codex スキル**です。

単にスライドを HTML で出力するだけではなく、固定キャンバス上で文字サイズ・はみ出し・コントラスト・情報量などを実測し、スクリーンショットと批評を使って読みやすさを改善します。納品用には、同じレイアウトを保った PDF も出力できます。

## できること

- 1600 × 900 の固定キャンバスで、各スライドを独立した HTML として作成
- `deck.md` にゴール、対象者、結論、制約、構成をまとめ、制作の判断基準を固定
- 共有の `theme.css` で色・書体・文字サイズを統一
- ブラウザで操作できる `index.html` ビューアを自動生成・同期
- ヘッドレス Chrome による実測検査
  - 要素のはみ出し、切れ、文字サイズ、コントラスト、色の逸脱
  - 文字量、文字の占有率、見出しと本文の階層、図中の文字・線の実効サイズ
  - ビューア経由でも共有 CSS が正しく読み込まれるか
- 検査結果、各スライドのスクリーンショット、コンタクトシートを `.loop/round-N/` に保存
- draw.io 図をスライド内へ貼り込める SVG に変換
- 全スライドを 1 本の固定レイアウト PDF に出力

## リポジトリ構成

| パス | 役割 |
| --- | --- |
| `skills/html-deck/SKILL.md` | Codex に渡す制作手順と品質基準 |
| `skills/html-deck/assets/` | スライド雛形、共有テーマ、ビューア、検査しきい値 |
| `skills/html-deck/scripts/init_deck.py` | 新しいデッキの骨格を作成 |
| `skills/html-deck/scripts/check_deck.py` | デッキを実測し、検査結果と画像を出力 |
| `skills/html-deck/scripts/export_pdf.py` | スライドを固定レイアウト PDF に結合 |
| `skills/html-deck/scripts/drawio_svg.py` | `.drawio` を貼り込み用 SVG に変換 |
| `skills/html-deck/references/` | レイアウト、図、反復改善のガイド |
| `skills/html-deck/agents/` | スライド単位・デッキ全体の批評用指示 |
| `docs/` | このスキルで作成したデッキの例 |

## 必要なもの

- Python 3.10 以降
- [uv](https://docs.astral.sh/uv/)（検査・PDF 出力時。必要な Python パッケージを自動解決します）
- Google Chrome または Chromium（`check_deck.py` と `export_pdf.py` が使用）

このリポジトリには Nix 開発環境も含まれています。Nix と direnv を利用する場合は、リポジトリ直下で次を実行すると `mise` と `task` を利用できます。

```bash
direnv allow
```

> `uv`、Python、Chrome は必要に応じて別途用意してください。Nix の設定では固定していません。

## 使い方

### 1. Codex にスライド作成を依頼する

`skills/html-deck/SKILL.md` を利用できる環境では、たとえば次のように依頼します。

```text
この調査メモをもとに、意思決定者向けの提案スライドを 10 枚程度で作って
```

スキルは、まず資料の目的と想定読者を定め、ゴールに沿って構成・デザイン・HTML を作成します。その後、機械検査と批評を行い、必要な修正を反復します。編集可能な PowerPoint が必須の場合は対象外です。HTML または固定 PDF を納品形式にしてください。

このリポジトリはスキル本体を含みます。Codex から使うには、利用中の Codex 環境で `skills/html-deck/` をスキルとして参照できるようにしてください。Codex を使わず、以下のスクリプトだけを直接実行することもできます。

### 2. デッキの骨格を作る

スクリプトを直接使う場合は、出力先とタイトルを指定します。

```bash
python skills/html-deck/scripts/init_deck.py ./output/product-proposal-deck \
  --title "プロダクト提案"
```

次のファイルが作られます。

```text
output/product-proposal-deck/
├── deck.md       # ゴール・対象者・結論・構成の正本
├── theme.css     # 全スライド共通のデザイン設定
├── index.html    # 操作・全画面表示に対応したビューア
├── slides/       # 01-title.html などのスライド本体
└── .loop/        # 検査結果・画像（検査時に出力）
```

`deck.md` の `goal`、`audience`、`takeaway`、`constraints`、`storyboard` を埋めてから制作を始めます。各スライドは `skills/html-deck/assets/slide-template.html` を元に `slides/NN-slug.html` として作成し、共通の色・書体・文字サイズは `theme.css` から参照します。

同じ出力先に再実行しても、既存の `deck.md`、`theme.css`、`index.html` は上書きされません。これらも雛形に戻す必要がある場合だけ `--force` を付けてください。

### 3. 検査する

```bash
uv run skills/html-deck/scripts/check_deck.py ./output/product-proposal-deck
```

検査ごとに `.loop/round-N/` へ次が保存されます。

- `report.json`: `block` / `review` / `info` の所見と数値指標
- `shots/`: 各スライドのスクリーンショット
- `contact-sheet.png`: 一覧で確認するためのコンタクトシート

`block` が残っている間は、先にレイアウトや可読性の問題を修正してください。特定のスライドだけ確認したい場合や画像を省略したい場合は、次のように指定できます。

```bash
uv run skills/html-deck/scripts/check_deck.py ./output/product-proposal-deck --slide 03
uv run skills/html-deck/scripts/check_deck.py ./output/product-proposal-deck --no-shots
```

検査は `index.html` のスライド一覧もファイル名順に更新します。ビューアは `index.html` を Chrome などのブラウザで直接開いて確認できます。ローカルサーバーは不要です。

### 4. 図を使う（任意）

構造が複雑な図は draw.io で作成できます。変換後の SVG は `<img>` ではなく、内容をスライド HTML の `<figure>` 内に直接貼り込みます。これにより、図内の文字や線も検査対象になります。

```bash
python skills/html-deck/scripts/drawio_svg.py \
  ./output/product-proposal-deck/figures/architecture.drawio \
  --title "処理の全体像"
```

draw.io アプリが見つからない場合は、スクリプトの案内に従ってインストールするか、単純な図であればインライン SVG を直接書いてください。

### 5. PDF を出力する

すべての検査と目視確認が済んだら、固定レイアウトの PDF を出力します。

```bash
uv run skills/html-deck/scripts/export_pdf.py ./output/product-proposal-deck \
  -o ./output/product-proposal.pdf
```

PDF は閲覧環境のフォント差異による崩れを避けるための納品形式です。出力後は必ず開き、文字化け・欠落・切れがないかを確認してください。

## 制作の考え方

品質の中心は、最初の生成結果ではなく改善の反復です。基本の流れは次のとおりです。

```text
目的・読者の合意
  → 構成とデザインの固定
  → スライド実装
  → 実測検査（block を解消）
  → スライド単位・デッキ全体の批評
  → 局所修正と再検査
  → 目視確認・PDF 出力
```

`theme.css` と検査しきい値は、反復の途中で安易に変えません。複数のスライドに同じ指摘が出た場合だけ、共通設定を見直します。詳細な品質契約と終了条件は [`skills/html-deck/SKILL.md`](skills/html-deck/SKILL.md) および `references/` を参照してください。

## 作例

`docs/` には、このスキルで作成したデッキが含まれています。

- `docs/honolulu-packing-deck/`: 旅行者向け手荷物準備ガイド
- `docs/卒業研究-発表-deck/`: 卒業研究の発表資料
- `docs/検証レポート-deck/`: 検証結果を意思決定へつなげるレポート

各デッキの `deck.md` は、目的・想定読者・ストーリーボードをどう記録するかの参考になります。
