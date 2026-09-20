"""10件の意味的一致データをJevあり・なしでLangfuseへ送信する。"""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from src.jev_judge import RUBRIC_VERSION, THRESHOLD, correctness_assessment, evaluate

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_DIR / "data/semantic_equivalence_v0.json"


def load_cases() -> list[dict]:
    cases = json.loads(DATA_PATH.read_text())["cases"]
    ids = [case["id"] for case in cases]
    if len(cases) != 10 or len(set(ids)) != len(ids):
        raise ValueError("検証データは重複しない10件である必要があります。")
    if any(not isinstance(case["expected_match"], bool) for case in cases):
        raise ValueError("各ケースにtrue/falseの期待判定が必要です。")
    return cases


def required_environment(condition: str) -> tuple[str, ...]:
    langfuse_keys = ("LANGFUSE_BASE_URL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    return (
        ("TYPESAFE_API_KEY", *langfuse_keys)
        if condition == "with-jev"
        else langfuse_keys
    )


def send_without_jev(client, case: dict, benchmark_id: str) -> dict:
    with client.start_as_current_observation(
        name="finalize-answer-without-jev",
        as_type="span",
        input={
            "assistant_output": case["assistant_output"],
            "expected_output": case["expected_output"],
        },
        output=case["assistant_output"],
        metadata={
            "synthetic": True,
            "condition": "without-jev",
            "benchmark_id": benchmark_id,
            "case_id": case["id"],
            "category": case["category"],
            "human_expected_match": case["expected_match"],
            "expected_output": case["expected_output"],
        },
    ) as observation:
        return {
            "condition": "without-jev",
            "case_id": case["id"],
            "human_expected_match": case["expected_match"],
            "trace_id": observation.trace_id,
            "observation_id": observation.id,
            "trace_url": client.get_trace_url(trace_id=observation.trace_id),
        }


def send_with_jev(client, case: dict, benchmark_id: str) -> dict:
    state = {
        "assistant_output": case["assistant_output"],
        "expected_output": case["expected_output"],
    }
    metadata = {
        "synthetic": True,
        "condition": "with-jev",
        "benchmark_id": benchmark_id,
        "case_id": case["id"],
        "category": case["category"],
        "human_expected_match": case["expected_match"],
        "rubric_version": RUBRIC_VERSION,
        "threshold": THRESHOLD,
        "threshold_calibrated": False,
    }
    with client.start_as_current_observation(
        name="evaluate-with-jev-benchmark",
        as_type="span",
        input=state,
        output=case["assistant_output"],
        metadata={**metadata, "expected_output": case["expected_output"]},
    ) as root:
        with client.start_as_current_observation(
            name="judge-semantic-equivalence",
            as_type="generation",
            model="jev-latest",
            input={"state": state},
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
        with client.start_as_current_observation(
            name="finalize-answer",
            as_type="span",
            input=state,
            output=case["assistant_output"],
            metadata={
                **metadata,
                "expected_output": case["expected_output"],
                "jev_correctness_assessment": assessment.metadata(),
            },
        ) as final_review:
            for score in assessment.langfuse_scores():
                client.create_score(
                    trace_id=root.trace_id,
                    observation_id=final_review.id,
                    name=score.name,
                    value=score.value,
                    data_type=score.data_type,
                    comment=score.comment,
                    metadata=metadata,
                )
        return {
            "condition": "with-jev",
            "case_id": case["id"],
            "human_expected_match": case["expected_match"],
            "trace_id": root.trace_id,
            "observation_id": final_review.id,
            "trace_url": client.get_trace_url(trace_id=root.trace_id),
            "jev_probability": probability,
            "jev_passed": passed,
            "jev_correctness_assessment": assessment.metadata(),
        }


def main(*, condition: str = "both") -> list[dict]:
    load_dotenv(PROJECT_DIR / ".env")
    conditions = ("with-jev", "without-jev") if condition == "both" else (condition,)
    required = tuple({key for item in conditions for key in required_environment(item)})
    missing = [key for key in required if not os.getenv(key, "").strip()]
    if missing:
        raise SystemExit(f".envに設定してください: {', '.join(sorted(missing))}")

    from langfuse import Langfuse

    cases = load_cases()
    benchmark_id = str(uuid4())
    results: list[dict] = []
    output_path = PROJECT_DIR / "results" / f"semantic-equivalence-{benchmark_id}.json"
    output_path.parent.mkdir(exist_ok=True)
    client = Langfuse()
    try:
        if not client.auth_check():
            raise SystemExit("Langfuseの認証に失敗しました。")
        for item in conditions:
            for case in cases:
                result = (
                    send_with_jev(client, case, benchmark_id)
                    if item == "with-jev"
                    else send_without_jev(client, case, benchmark_id)
                )
                results.append(result)
                client.flush()
                output_path.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2) + "\n"
                )
                print(f"{item:12} {case['id']:32} {result['trace_url']}")
        print(f"benchmark_id: {benchmark_id}")
        print(f"実行記録: {output_path}")
        print("送信完了。LangfuseのGPT-4o評価は非同期で実行されます。")
        return results
    finally:
        client.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--condition", choices=("both", "with-jev", "without-jev"), default="both"
    )
    main(condition=parser.parse_args().condition)
