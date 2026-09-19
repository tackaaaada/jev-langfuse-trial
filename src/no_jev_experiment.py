"""同じ長文ペアをJevなしでLangfuseのマネージドEvaluatorへ渡す。"""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


def main(*, repeat: int = 1) -> list[dict]:
    if repeat not in (1, 2, 3):
        raise ValueError("repeatは1〜3を指定してください。")
    project_dir = Path(__file__).resolve().parents[1]
    load_dotenv(project_dir / ".env")
    required = ("LANGFUSE_BASE_URL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    missing = [key for key in required if not os.getenv(key, "").strip()]
    if missing:
        raise SystemExit(f".envに設定してください: {', '.join(missing)}")

    from langfuse import Langfuse

    case = json.loads((project_dir / "data/long_semantic_match.json").read_text())
    state = {key: case[key] for key in ("assistant_output", "expected_output")}
    batch_id = str(uuid4())
    results = []
    output_dir = project_dir / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"without-jev-{batch_id}.json"
    client = Langfuse()
    try:
        if not client.auth_check():
            raise SystemExit("Langfuseの認証に失敗しました。")
        # クライアントは全件の送信完了まで維持する。
        for index in range(1, repeat + 1):
            with client.start_as_current_observation(
                name="finalize-answer-without-jev",
                as_type="span",
                input=state,
                output=state["assistant_output"],
                metadata={
                    "synthetic": True,
                    "condition": "without-jev",
                    "case_id": case["case_id"],
                    "batch_id": batch_id,
                    "run_index": index,
                    "expected_output": state["expected_output"],
                },
            ) as observation:
                result = {
                    "run_index": index,
                    "batch_id": batch_id,
                    "case_id": case["case_id"],
                    "trace_id": observation.trace_id,
                    "observation_id": observation.id,
                    "trace_url": client.get_trace_url(trace_id=observation.trace_id),
                }
            client.flush()
            results.append(result)
            output_path.write_text(
                json.dumps(results, ensure_ascii=False, indent=2) + "\n"
            )
            print(f"{index}回目: {result['trace_url']}")
        print(f"実行記録: {output_path}")
        print("送信完了。Jev呼び出しなし。GPT-4oの評価はLangfuseで非同期実行されます。")
        return results
    finally:
        client.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, choices=range(1, 4), default=1)
    main(repeat=parser.parse_args().repeat)
