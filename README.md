# Jev + Langfuse Trial

Jevで回答の意味的一致を一次判定し、その結果を参考情報としてLangfuseのマネージドEvaluator（GPT-4o）に渡し、最終判定するPythonプロジェクトです。
現在は固定の合成データ1件で動作確認しています。検証用データセットの作成・評価精度の校正は今後行います。

## 構成と評価基準

```mermaid
flowchart TD
    A[評価対象の回答と期待回答] --> B[Python: TypeSafe公式SDK]
    B --> C[Jev: 意味的一致の確率]
    C --> D[確率と仮の閾値0.5による一次判定]
    D --> E[Langfuse: finalize-answerに回答・期待回答・Jev結果を記録]
    E --> F[マネージドEvaluator: GPT-4o]
    F --> G[Check Correctness: 最終true/falseと理由]
```

評価する「正確性」は、期待回答の重要な意味・事実・制約・結論を、実際の回答が矛盾なく保持しているかです。
言い換えや形式の違いは許容し、重要な情報の欠落・矛盾・根拠のない主張などは不一致とします。

- **Jev**: TypeSafe公式Python SDK `typesafe-sdk`で直接接続します。Vercel AI Gatewayは使用しません。
- **一次判定**: Noulが返す意味的一致の確率を保存し、0.5以上をtrueに変換します。0.5は未校正の仮値です。確率は部分正答の点数ではありません。
- **最終判定**: GPT-4oが元の回答と期待回答を比較します。Jevの結果は参考情報であり、その判定を変更できます。Jevへの賛否も理由に含めます。
- **実行対象**: 今回はJevのtrue/falseにかかわらず全件を最終評価に渡します。不確実なケースだけを送る分岐は実装していません。

最終評価はLangfuse側で非同期に実行されます。Pythonのコマンド終了は、最終評価の完了を意味しません。
Jevが失敗した場合は最終評価用Observationを作成しません。

## 環境構築

Python 3.14以上、uv、起動済みのLangfuseが必要です。

```bash
uv sync --locked
```

初回のみ`.env.example`を`.env`にコピーし、以下を設定します。設定済みの`.env`は上書きしないでください。

| 環境変数 | 用途 |
| --- | --- |
| `LANGFUSE_BASE_URL` | Langfuse接続先（例: `http://localhost:3000`） |
| `LANGFUSE_PUBLIC_KEY` | Langfuseプロジェクトの公開キー |
| `LANGFUSE_SECRET_KEY` | Langfuseプロジェクトの秘密キー |
| `TYPESAFE_API_KEY` | TypeSafeのAPIキー |

OpenAIのAPIキーはLangfuseの **Settings → LLM Connections** に登録します。
PythonからGPT-4oを直接呼ぶ構成ではありません。キーをGitやREADMEに記載しないでください。

導入済みのツールは次のとおりです。

- Langfuse SDK、python-dotenv、TypeSafe SDK（接続確認時: `typesafe-sdk 0.7.0`）
- Langfuse CLI（接続確認時: `@langfuse/cli 1.2.4`、`~/.local/bin/langfuse`）
- Langfuseスキル: `.agents/skills/langfuse/`

CLIを別の環境にも導入する場合:

```bash
npm install --global @langfuse/cli
langfuse --version
```

## 実行

### 二段階評価

```bash
uv run python -m src.jev_experiment
```

現在の入力は以下の1件です。

| 項目 | 値 |
| --- | --- |
| 質問（記録用） | サンプルショップの開店時刻は？ |
| 評価対象の回答 | 午前10時に開店します。 |
| 期待回答 | サンプルショップの開店時刻は午前10時です。 |

Jevと最終Evaluatorは、評価対象の回答と期待回答を基準に比較します。質問文は判定用プロンプトには渡していません。
毎回Jevを1回呼び出し、新しいトレースを作成します。有効な評価ルールがある場合はGPT-4oも呼ばれるため、両プロバイダーのAPI利用料が発生します。
Jevのタイムアウトは30秒、自動再試行は無効です。

コマンドは一次判定、トレースID、確認URL、最終評価対象Observation IDを表示します。
最終結果は確認URLの`finalize-answer`に付いた`Check Correctness`スコアで確認します。

### 接続確認のみ

```bash
# Langfuseへ固定の入出力を1件送信
uv run python -m src.experiment

# Jevへ簡易プロンプトで1件送信（Langfuseへの記録なし）
uv run python -m src.jev_connection_check
```

`src.experiment`自体はモデルを呼びません。現在の最終評価ルールは`finalize-answer`のみを対象とするため、この接続確認は対象外です。

## Langfuseに保存する内容

```text
evaluate-with-jev (SPAN)
├── judge-semantic-equivalence (GENERATION)
│   └── Jevの入力・評価基準・応答・モデル名・使用トークン数
└── finalize-answer (SPAN、Jev完了後に作成)
    ├── output: 元の回答
    ├── metadata.expected_output: 期待回答
    ├── metadata.jev_result: Jevの確率・判定・閾値・モデル・基準の版
    └── Scores: Jevの2スコアとGPT-4oの最終スコア
```

| スコア名 | 型 | 意味 |
| --- | --- | --- |
| `jev_semantic_match_probability` | NUMERIC | Jevによる意味的一致の確率（0〜1） |
| `jev_semantic_match` | BOOLEAN | 確率が仮の閾値0.5以上か |
| `Check Correctness` | BOOLEAN | GPT-4oによる最終判定。理由も保存 |

Jevの基準は`src/jev_judge.py`の`semantic-equivalence-v1`です。
`jev-latest`を指定して呼び出し、返却された具体的なモデル名を記録します。
初回は`jev-1.13.0`でした。料金設定がない場合、Langfuseのコストは未算出になります。

Jev結果を最終評価対象のmetadataへ直接コピーすることで、後から届くScoreや兄弟Observationの取得順序に依存せず、Evaluatorが必要な情報を読めるようにしています。

## マネージドEvaluatorの設定

- Evaluator: `Check Correctness`
- モデル: `openai`接続の`gpt-4o`
- スコア型: BOOLEAN
- ルール: `Final review after Jev`
- 対象: Observation名が`finalize-answer`
- サンプリング: 100%

| プロンプト変数 | ソース | JSONパス |
| --- | --- | --- |
| `assistant_output` | output | なし（全体） |
| `expected_output` | metadata | `$.expected_output` |
| `jev_result` | metadata | `$.jev_result` |

デフォルトの意味的一致プロンプトを維持し、Jevの判定を参考にして最終判定する説明を末尾に追加しています。
Evaluatorは対象Observationのデータを読みます。通常のObservation評価では、実験データ用の`expected_output`ソースではなく、今回保存したmetadataの期待回答を参照します。

適用済み設定を`config/langfuse/evaluator.json`と`config/langfuse/rule.json`に保存しています。
変更前の設定は同ディレクトリの`evaluator-before.json`と`rule-before.json`です。
このプロジェクトへの再適用は以下です。別プロジェクトではIDと接続名を変更してください。

```bash
langfuse --env .env api evaluators update YOUR_PRIVATE_ID --body-file config/langfuse/evaluator.json
langfuse --env .env api evaluation-rules update YOUR_PRIVATE_ID --body-file config/langfuse/rule.json
```

元に戻す場合は、それぞれの`--body-file`に`evaluator-before.json`と`rule-before.json`を指定します。
元の期待回答マッピングも復元されるため、元の設定が今回のObservation評価に適切とは限りません。

記録の読み戻し例（`TRACE_ID`は実行結果に置き換える）:

```bash
langfuse --env .env api observations list --trace-id TRACE_ID --fields core,basic,io,metadata,model,usage --json
langfuse --env .env api scores list --trace-id TRACE_ID --fields subject,details --json
```

## ここまでの確認結果

1. Langfuseへ`connectivity-check`トレースを送信。
2. OpenAI接続、GPT-4o、正確性Evaluatorを設定。
3. TypeSafe SDKとAPIキーを設定し、英語の同一回答ペアでJev接続を確認（確率0.99）。
4. 日本語の1件をJevで評価し、Langfuseへ保存・読み戻し（確率0.44、false）。同じ対象に既存Evaluatorのtrueも記録。
5. Jev結果を参考情報として渡す二段階評価に変更。最終評価用の変数マッピングと対象ルールを設定。
6. 二段階評価を実行し、Jevの確率0.47・false、GPT-4oの最終falseを読み戻して確認。GPT-4oは「店名との関係が欠けている」と説明し、Jevに同意しました。

ã­ã¼ã«ã«ã®Langfuse UIã§ç¢ºèª

手順4の既存Evaluatorは、期待回答の参照先が実験データ用の設定だったため、期待回答を正しく渡せた比較結果としては扱いません。二段階評価ではmetadataへの明示的なマッピングに修正しています。
これらは接続・処理の動作確認であり、精度や優劣の結論ではありません。今後、検証データを作成し、誤判定や閾値を確認します。

## 開発時の検証

```bash
uv run pytest -q tests/test_jev_experiment.py
uv run ruff check src/jev_experiment.py tests/test_jev_experiment.py
```

テストは外部APIを呼ばず、Jev完了後に最終評価対象を作成すること、判定と期待回答の受け渡し、Jev失敗時に最終評価を作成しないことを確認します。
実APIの確認では、3つのObservation、Jevの実モデル名・トークン数、最終評価用metadata、同一Observation上の3スコアを読み戻しました。

## 参考資料

- [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python)
- [Noul: Yesとなる確率](https://docs.typesafe.ai/primitives/noul)
- [Langfuse LLM-as-a-Judge](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
- [Langfuse CLI](https://langfuse.com/docs/api-and-data-platform/features/cli)
