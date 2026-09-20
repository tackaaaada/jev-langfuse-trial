"""合成の回答1件をJevで評価し、Langfuseへ記録する。"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from src.jev_judge import (
    QUESTIONS,
    RUBRIC_VERSION,
    THRESHOLD,
    correctness_assessment,
    evaluate,
)


def main(*, run_index: int = 1, batch_id: str | None = None) -> dict:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    required = (
        "TYPESAFE_API_KEY",
        "LANGFUSE_BASE_URL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise SystemExit(f".envに設定してください: {', '.join(missing)}")

    from langfuse import Langfuse

    case = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/long_semantic_match.json"
        ).read_text()
    )
    state = {key: case[key] for key in ("assistant_output", "expected_output")}
    metadata = {
        "synthetic": True,
        "purpose": "jev-small-start",
        "rubric_version": RUBRIC_VERSION,
        "threshold": THRESHOLD,
        "threshold_calibrated": False,
        "case_id": case["case_id"],
        "batch_id": batch_id or str(uuid4()),
        "run_index": run_index,
    }
    langfuse = Langfuse()
    try:
        if not langfuse.auth_check():
            raise SystemExit(
                "Langfuseの認証に失敗しました。接続設定を確認してください。"
            )
        with langfuse.start_as_current_observation(
            name="evaluate-with-jev",
            as_type="span",
            input={
                "question": case["question"],
                "expected_output": state["expected_output"],
            },
            output=state["assistant_output"],
            metadata={**metadata, "expected_output": state["expected_output"]},
        ) as root:
            trace_id = root.trace_id
            with langfuse.start_as_current_observation(
                name="judge-semantic-equivalence",
                as_type="generation",
                model="jev-latest",
                input={
                    "state": state,
                    "questions": {
                        name: question.model_dump(mode="json")
                        for name, question in QUESTIONS.items()
                    },
                },
                metadata=metadata,
                version=RUBRIC_VERSION,
            ) as generation:
                response = evaluate(state)
                assessment = correctness_assessment(response)
                probability = assessment.probability
                passed = assessment.passed
                generation.update(
                    model=response.model,
                    output=response.model_dump(mode="json"),
                    usage_details={
                        "input": response.usage.input_tokens,
                        "output": response.usage.output_tokens,
                    },
                )
            # 完了済みのJev判定を最初から含む専用Observationだけを最終評価する。
            # 後着するScoreや兄弟Observationへの参照には依存しない。
            with langfuse.start_as_current_observation(
                name="finalize-answer",
                as_type="span",
                input=state,
                output=state["assistant_output"],
                metadata={
                    **metadata,
                    "expected_output": state["expected_output"],
                    "jev_correctness_assessment": assessment.metadata(),
                },
            ) as final_review:
                for score in assessment.langfuse_scores():
                    langfuse.create_score(
                        trace_id=trace_id,
                        observation_id=final_review.id,
                        name=score.name,
                        value=score.value,
                        data_type=score.data_type,
                        comment=score.comment,
                        metadata=metadata,
                    )
        langfuse.flush()
        print(f"Jev評価: probability={probability}, passed={passed}")
        print(f"トレースID: {trace_id}")
        print(f"確認URL: {langfuse.get_trace_url(trace_id=trace_id)}")
        print(f"最終評価対象Observation: {final_review.id}")
        print("送信完了。Langfuseの最終評価は非同期で実行されます。")
        return {
            "run_index": run_index,
            "batch_id": metadata["batch_id"],
            "case_id": case["case_id"],
            "trace_id": trace_id,
            "observation_id": final_review.id,
            "jev_probability": probability,
            "jev_passed": passed,
            "jev_correctness_assessment": assessment.metadata(),
        }
    finally:
        langfuse.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--run-index", type=int, default=1)
    args = parser.parse_args()
    batch_id = args.batch_id or str(uuid4())
    output_dir = Path(__file__).resolve().parents[1] / "results"
    output_dir.mkdir(exist_ok=True)
    if args.repeat == 1:
        result = main(run_index=args.run_index, batch_id=batch_id)
        result_path = output_dir / f"{batch_id}-{args.run_index}.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(f"実行記録: {result_path}")
    else:
        # SDKのプロセス単位リソースを終了後に再利用しない。
        for index in range(1, args.repeat + 1):
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.jev_experiment",
                    "--batch-id",
                    batch_id,
                    "--run-index",
                    str(index),
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
            )
