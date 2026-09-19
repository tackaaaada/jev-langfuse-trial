"""合成データ1件でLangfuseへの接続・トレース送信を確認する。"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langfuse import Langfuse


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    required = (
        "LANGFUSE_BASE_URL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise SystemExit(f".envに設定してください: {', '.join(missing)}")

    langfuse = Langfuse()
    try:
        if not langfuse.auth_check():
            raise SystemExit(
                "認証できませんでした。Langfuseの起動状態・接続先・APIキーを確認してください。"
            )
        print("Langfuseの認証に成功しました。")

        with langfuse.start_as_current_observation(
            as_type="span",
            name="connectivity-check",
            input={
                "question": "架空の店舗サンプルショップの開店時刻は？",
                "reference": "サンプルショップは毎日午前10時に開店します。",
            },
            metadata={"purpose": "connectivity-check", "synthetic": True},
        ) as span:
            span.update(output={"answer": "午前10時です。", "mock": True})
            trace_id = span.trace_id

        langfuse.flush()
        print(f"トレースID: {trace_id}")
        trace_url = langfuse.get_trace_url(trace_id=trace_id)
        if trace_url:
            print(f"確認URL: {trace_url}")
        print("送信処理を終えました。Langfuse画面でトレースの到着を確認してください。")
        print("反映に時間がかかる場合があります。LLM・Jevは呼び出していません。")
    finally:
        langfuse.shutdown()


if __name__ == "__main__":
    main()
