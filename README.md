# Jev + Langfuse Trial

LLM-as-a-judgeとJevによる評価結果をLangfuseに記録するPythonプロジェクト。

## 環境構築

1. `uv sync --locked`を実行する。
2. `.env.example`を`.env`にコピーし、接続情報を設定する。
3. 別ディレクトリでLangfuseを起動する。

## 実行

```bash
uv run python -m src.experiment

評価処理は未実装。
