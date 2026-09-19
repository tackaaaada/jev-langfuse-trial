"""合成データ1件でJevの接続を確認する。評価精度の検証は行わない。"""

import os
from pathlib import Path

from dotenv import load_dotenv
from typesafe_sdk import Noul, RetryPolicy, TypeSafeClient


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if not os.getenv("TYPESAFE_API_KEY", "").strip():
        raise SystemExit(".envにTYPESAFE_API_KEYを設定してください。")

    with TypeSafeClient(timeout=30.0, retry=RetryPolicy(max_retries=0)) as client:
        response = client.system_one(
            model="jev-latest",
            state={
                "assistant_output": "The shop opens at 10 AM.",
                "expected_output": "The shop opens at 10 AM.",
            },
            questions={
                "semantic_match": Noul(
                    instructions=(
                        "Does assistant_output preserve every material fact and meaning "
                        "in expected_output without contradiction? "
                        "Ignore formatting and wording differences."
                    ),
                ),
            },
        )

    probability = response.nouls["semantic_match"].noul
    if not 0 <= probability <= 1:
        raise SystemExit("Jevの応答が確率の範囲外です。")
    print("Jevへの接続に成功しました。")
    print(f"意味的一致の確率: {probability}")
    print("接続確認のみです。評価精度の検証・Langfuseへの記録は行っていません。")


if __name__ == "__main__":
    main()
