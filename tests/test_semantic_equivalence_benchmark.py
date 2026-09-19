"""10件比較実験の入力、条件分離、ラベル非送信を確認する。"""

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src import semantic_equivalence_benchmark as benchmark


def test_cases_are_ten_unique_and_have_both_expected_labels():
    cases = benchmark.load_cases()
    assert len(cases) == 10
    assert len({case["id"] for case in cases}) == 10
    assert {case["expected_match"] for case in cases} == {True, False}


def test_jev_condition_records_result_and_control_omits_it(monkeypatch):
    client = MagicMock()
    client.get_trace_url.return_value = "http://localhost/test"
    observations = []

    @contextmanager
    def observation(**kwargs):
        observations.append(kwargs)
        span = MagicMock()
        span.id = f"observation-{len(observations)}"
        span.trace_id = "trace-id"
        yield span

    client.start_as_current_observation.side_effect = observation
    response = SimpleNamespace(
        nouls={"semantic_match": SimpleNamespace(noul=0.8)},
        model="jev-test",
        usage=SimpleNamespace(input_tokens=10, output_tokens=1),
        model_dump=lambda **_: {"answers": {"semantic_match": {"noul": 0.8}}},
    )
    monkeypatch.setattr(benchmark, "evaluate", lambda _state: response)
    case = benchmark.load_cases()[0]

    with_jev = benchmark.send_with_jev(client, case, "benchmark-id")
    benchmark.send_without_jev(client, case, "benchmark-id")

    final_with = next(
        item for item in observations if item["name"] == "finalize-answer"
    )
    final_without = next(
        item for item in observations if item["name"] == "finalize-answer-without-jev"
    )
    assert with_jev["jev_probability"] == 0.8
    assert final_with["metadata"]["jev_result"]["passed"] is True
    assert "jev_result" not in final_without["metadata"]
    assert final_with["metadata"]["human_expected_match"] == case["expected_match"]
    assert final_without["metadata"]["human_expected_match"] == case["expected_match"]
    assert client.create_score.call_count == 2


def test_evaluators_do_not_map_human_labels_into_prompts():
    directory = Path(__file__).parents[1] / "config/langfuse"
    for name in ("evaluator.json", "evaluator-without-jev.json"):
        evaluator = json.loads((directory / name).read_text())
        assert "human_expected_match" not in json.dumps(evaluator)
        assert "expected_output" in {
            item["variable"] for item in evaluator["variableMapping"]
        }
