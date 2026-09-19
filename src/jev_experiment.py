"""合成の回答1件をJevで評価し、Langfuseへ記録する。"""

import os
from pathlib import Path

from dotenv import load_dotenv

from src.jev_judge import INSTRUCTIONS, RUBRIC_VERSION, THRESHOLD, evaluate


def main() -> None:
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

    state = {
        "assistant_output": "午前10時に開店します。",
        "expected_output": "サンプルショップの開店時刻は午前10時です。",
    }
    metadata = {
        "synthetic": True,
        "purpose": "jev-small-start",
        "rubric_version": RUBRIC_VERSION,
        "threshold": THRESHOLD,
        "threshold_calibrated": False,
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
                "question": "サンプルショップの開店時刻は？",
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
                        "semantic_match": {
                            "type": "noul",
                            "instructions": INSTRUCTIONS,
                        },
                    },
                },
                metadata=metadata,
                version=RUBRIC_VERSION,
            ) as generation:
                response = evaluate(state)
                probability = response.nouls["semantic_match"].noul
                passed = probability >= THRESHOLD
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
            jev_result = {
                "probability": probability,
                "passed": passed,
                "threshold": THRESHOLD,
                "threshold_calibrated": False,
                "model": response.model,
                "rubric_version": RUBRIC_VERSION,
            }
            with langfuse.start_as_current_observation(
                name="finalize-answer",
                as_type="span",
                input=state,
                output=state["assistant_output"],
                metadata={
                    **metadata,
                    "expected_output": state["expected_output"],
                    "jev_result": jev_result,
                },
            ) as final_review:
                for name, value, data_type in (
                    ("jev_semantic_match_probability", probability, "NUMERIC"),
                    ("jev_semantic_match", int(passed), "BOOLEAN"),
                ):
                    langfuse.create_score(
                        trace_id=trace_id,
                        observation_id=final_review.id,
                        name=name,
                        value=value,
                        data_type=data_type,
                        comment="Jev Noulによる意味的一致。閾値0.5は未校正の仮値。",
                        metadata=metadata,
                    )
        langfuse.flush()
        print(f"Jev評価: probability={probability}, passed={passed}")
        print(f"トレースID: {trace_id}")
        print(f"確認URL: {langfuse.get_trace_url(trace_id=trace_id)}")
        print(f"最終評価対象Observation: {final_review.id}")
        print("送信完了。Langfuseの最終評価は非同期で実行されます。")
    finally:
        langfuse.shutdown()


if __name__ == "__main__":
    main()
