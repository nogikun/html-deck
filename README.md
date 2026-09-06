# HTML Deck Skill

メモ、記事、調査資料、議事録、URL、口頭の依頼などをもとに、**HTML 形式のスライド資料を作り、検査と改善を繰り返して仕上げるための Skills** です。

単にスライドを HTML で出力するだけではなく、固定キャンバス上で文字サイズ・はみ出し・コントラスト・情報量などを実測し、スクリーンショットと批評を使って読みやすさを改善します。納品用には、同じレイアウトを保った PDF も出力できます。

## セットアップ

以下のコマンドを実行し、ターミナル上で適用先を指定

```bash
npx skills add nogikun/gen-slide-skills
```

## できること

- 1600 × 900 の固定キャンバスで、各スライドを独立した HTML として作成
- `deck.md` にゴール、対象者、結論、制約、構成をまとめ、制作の判断基準を固定
- 共有の `theme.css` で色・書体・文字サイズを統一
- ブラウザで操作できる `index.html` ビューアを自動生成・同期（レビュー画面と同じ1ファイル）
- ヘッドレス Chrome による実測検査
  - 要素のはみ出し、切れ、文字サイズ、コントラスト、色の逸脱
  - 文字量、文字の占有率、見出しと本文の階層、図中の文字・線の実効サイズ
  - ビューア経由でも共有 CSS が正しく読み込まれるか
- 検査結果、各スライドのスクリーンショット、コンタクトシートを `.loop/round-N/` に保存
- draw.io 図をスライド内へ貼り込める SVG に変換
- 全スライドを 1 本の固定レイアウト PDF に出力（指定書体が実際に使われたかを検査）
- デッキ一式を**外部参照ゼロの 1 枚 HTML** に畳んで、そのまま送れる形にする
- **レビューモード**: ブラウザ上でスライドの要素をクリックすると、入力欄に `#1` `#2` … という**ブロック**が入る。それを主語に自然言語で直しを依頼できる。指摘はソースの行番号まで解決された JSON になり、AI エージェントがそのまま読める。画面は白モード / ナイトモードの2系統
- **情報量の統制**: 枚ごとの字数だけでなく、**図のある枚の割合 (4割以上) と文字だけの枚の連続 (2枚まで)** を並びとして検査する。どの1枚も合格のままデッキ全体が文字の壁になるのを止める
- **最初にインタビューする**: 「見終わった人がどういう状態になっていてほしいか」「話しながら見せるのか、置いて読ませるのか」から始める。場面がそのまま1枚の情報量の予算になる

## リポジトリ構成

| パス                                           | 役割                                                  |
| ---------------------------------------------- | ----------------------------------------------------- |
| `skills/html-deck/SKILL.md`                  | Codex に渡す制作手順と品質基準                        |
| `skills/html-deck/assets/`                   | スライド雛形、共有テーマ、ビューア、検査しきい値      |
| `skills/html-deck/scripts/init_deck.py`      | 新しいデッキの骨格を作成                              |
| `skills/html-deck/scripts/check_deck.py`     | デッキを実測し、検査結果と画像を出力                  |
| `skills/html-deck/scripts/export_pdf.py`     | スライドを固定レイアウト PDF に結合                   |
| `skills/html-deck/scripts/drawio_svg.py`     | `.drawio` を貼り込み用 SVG に変換                   |
| `skills/html-deck/scripts/review_server.py`  | レビューモードのサーバ。DOM 指定を JSON に落とす      |
| `skills/html-deck/scripts/review_wait.py`    | 指摘が届くまで待機（送信を検知する経路）              |
| `skills/html-deck/scripts/review_thread.py`  | 指摘スレッドの読み書き。確定判断を `deck.md` に積む   |
| `skills/html-deck/scripts/bundle_deck.py`    | デッキ一式を1枚の HTML に畳む                         |
| `skills/html-deck/references/`               | レイアウト、図、反復改善のガイド                      |
| `skills/html-deck/agents/`                   | スライド単位・デッキ全体の批評用指示                  |
| `skills/html-deck/assets/review.html`        | 唯一のビューア。`index.html` としても配置される       |
| `docs/design/`                               | 設計ドキュメント                                      |
| `docs/`                                      | このスキルで作成したデッキの例                        |

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

### 5. レビューモードで直しを依頼する

生成したデッキをブラウザで開き、スライド上の要素を直接指して直しを出せます。

```bash
python3 skills/html-deck/scripts/review_server.py ./output/product-proposal-deck --open
```

表示された URL を開き、`E` キーでレビューモードに入ります。要素にカーソルを合わせると
ハイライトされ、クリックするとその要素が右のペインの入力欄に `#1` というブロックとして
挿し込まれます。空白部分をドラッグすると、まだ要素がない場所を領域として指定できます。

そのまま文を続けて書き、`Cmd`/`Ctrl` + `Enter` で送信します。

```text
#1 の回収期間を6ヶ月に直して出典を足して。#2 の見出しも数字を合わせて。
#3 に現行と提案の比較図を入れて。
```

`#N` はテキストではなく1つのブロックとして振る舞います。`⌫` で丸ごと消え、コピーして
貼り直してもブロックのまま、手で `#2` と打てばブロックに変わります。番号は本文に
現れた順で振り直されるので、途中で消しても対応が崩れません。`T` で白モードと
ナイトモードを切り替えられます。

送信内容は `<deck>/.loop/feedback/threads/fb-NNN.jsonl` に、1指摘 = 1スレッドとして
保存されます。各指定は**ファイル名と行番号**まで解決されているため、Claude Code などの
AI エージェントがそのまま読んで修正できます。会話も状態もこのファイルが正本で、
ピンの色にもそのまま反映されます。**確定するのはユーザーがマージしたときだけ**で、
エージェントは「直した」までしか進められません。

上のコマンドは手動で実行する場合のものです。**スキル経由で使う場合、起動から指摘の取り込み、
修正、記録までは AI エージェント側が行います。** ユーザーは渡された URL で指摘を出すだけです。
エージェントは `review_wait.py` を併走させ、送信された時点で気づきます。

> レビューモードには**ローカルサーバーが必要**です。`file://` で開いた場合、ブラウザの制約に
> よりページ内の要素を選択できません。`index.html` を直接開くとレビュー機能は自動的に
> 畳まれ、ただのビューアとして動きます。

### 6. PDF を出力する

すべての検査と目視確認が済んだら、固定レイアウトの PDF を出力します。

```bash
uv run skills/html-deck/scripts/export_pdf.py ./output/product-proposal-deck \
  -o ./output/product-proposal.pdf
```

PDF は閲覧環境のフォント差異による崩れを避けるための納品形式です。出力後は必ず開き、文字化け・欠落・切れがないかを確認してください。

`theme.css` で指定した書体がこの環境に無いと、代替書体で描かれた結果がそのまま固定されます。
それでは見た目を固定して渡したことにならないため、**実際に描画に使われた書体を検査して、
落ちていれば書き出しません**。承知のうえで出すなら `--allow-font-fallback` を付けます。

### 7. 編集可能な PPTX を実験的に出力する

PptxGenJS を使い、Chrome が計算した座標をテキスト行・背景図形・境界線・SVG・画像へ写像します。CSSを
PowerPoint側で再現するのではなく、既存の1600×900pxレイアウトとブラウザ上の改行位置を先に確定してから出力します。

```bash
npm install
uv run skills/html-deck/scripts/export_pptx.py ./work/ctfp-for-new-engineers-deck \
  -o ./work/ctfp-for-new-engineers-deck/ctfp-for-new-engineers-deck.pptx
```

テキスト、背景図形、境界線は編集できます。テキストはブラウザの実測行ごとに分割し、PowerPoint側の
自動縮小・再折返しを無効化しています。インラインSVGは1つのSVG画像として配置されるため、SVG内部の
線や文字を個別編集するものではありません。HTMLの複雑なCSS効果やPowerPointと異なるフォント
メトリクスは、完全一致ではなく検査対象です。

人に送るだけなら、1枚の HTML に畳むほうが手軽です。外部参照が無いのでそのまま添付できます。

```bash
python skills/html-deck/scripts/bundle_deck.py ./output/product-proposal-deck
```

どちらもレビュー画面のツールバーのボタンから実行できます（サーバー稼働中のみ）。

## 制作の考え方

品質の中心は、最初の生成結果ではなく改善の反復です。基本の流れは次のとおりです。

```text
目的・読者の合意
  → 構成とデザインの固定
  → スライド実装
  → 実測検査（block を解消）
  → スライド単位・デッキ全体の批評
  → 局所修正と再検査
  → 目視確認 → 1枚 HTML / PDF の書き出し
```

`theme.css` と検査しきい値は、反復の途中で安易に変えません。複数のスライドに同じ指摘が出た場合だけ、共通設定を見直します。詳細な品質契約と終了条件は [`skills/html-deck/SKILL.md`](skills/html-deck/SKILL.md) および `references/` を参照してください。

## 作例

`docs/` には、このスキルで作成したデッキが含まれています。

- `docs/honolulu-packing-deck/`: 旅行者向け手荷物準備ガイド
- `docs/卒業研究-発表-deck/`: 卒業研究の発表資料
- `docs/検証レポート-deck/`: 検証結果を意思決定へつなげるレポート

各デッキの `deck.md` は、目的・想定読者・ストーリーボードをどう記録するかの参考になります。
