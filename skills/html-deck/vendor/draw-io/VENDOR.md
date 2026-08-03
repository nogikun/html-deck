# vendor/draw-io — 取り込み元と改変の有無

| 項目 | 内容 |
| --- | --- |
| 取り込み元 | https://github.com/little-hands/claude-drawio-skill |
| 対象パス | `plugins/draw-io/skills/draw-io/` |
| コミット | `23b6387` (2026-02-25) |
| ライセンス | MIT (`LICENSE` をそのまま同梱。Copyright (c) 2025 little-hands) |
| 改変 | **なし。** `SKILL.md` と `references/` は上流のまま |
| 取り込んでいないもの | `test/`、プラグイン定義 (`.claude-plugin/`)、README |

## なぜこれを選んだか

draw.io スキルは複数公開されている。比較して次の理由でこれにした。

- `SKILL.md` 141行 + references 419行と小さく、丸ごと読ませても文脈を食わない
- `.drawio` XML の書き方 (`xml-reference.md`) と座標計算・配置原則 (`layout-guide.md`) が
  分離されていて、スライド用途では後者だけを追加で読ませればよい
- MIT で、同梱と再配布の条件が明快
- `darkMode="0"` の指定漏れで書き出し時に色が反転する、という実務上の落とし穴が
  明記されている。これはスライドに貼ったときにそのまま事故になる

採用しなかったもの:

- `Agents365-ai/drawio-skill` — 36ツール・8.2MB。機能は最も広いが、
  スライド1枚に貼る図を作る用途には過剰で、読み込み負荷が見合わない
- `softaworks/agent-toolkit` の `draw-io` — 品質基準 (フレーム内余白30px以上、
  文字1.5倍、背景透過) は有用だが、`mise` 前提で AWS アイコン特化の色が濃い。
  品質基準の考え方だけ `references/figures.md` に取り込んだ

## このデッキ用途での差分

上流は「`.drawio` ファイルを成果物として残す」前提だが、スライドでは
**SVGへ書き出してHTMLにインライン展開する**ところまでが必要になる。
その手順とスライド固有の制約は上流には無いので、
`scripts/drawio_svg.py` と `references/figures.md` 側に置いた。上流には手を入れていない。
