"""外部APIを呼ばず、一次判定から最終評価への受け渡しを確認する。"""

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import jev_experiment


def setup_run(monkeypatch, fail=False):
    import langfuse

    for key in (
        "TYPESAFE_API_KEY",
        "LANGFUSE_BASE_URL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.setenv(key, "test")
    monkeypatch.setattr(jev_experiment, "load_dotenv", lambda *_: None)
    client = MagicMock()
    events = []
    observations = []

    @contextmanager
    def observation(**kwargs):
        events.append(kwargs["name"])
        observations.append(kwargs)
        span = MagicMock()
        span.id = kwargs["name"]
        span.trace_id = "test-trace"
        yield span

    client.start_as_current_observation.side_effect = observation
    monkeypatch.setattr(langfuse, "Langfuse", lambda: client)

    def evaluate(state):
        if fail:
            raise RuntimeError("Jev unavailable")
        events.append("jev-complete")
        return SimpleNamespace(
            nouls={"is_correct": SimpleNamespace(noul=0.47)},
            choices={
                "primary_correctness_issue": SimpleNamespace(
                    choice="missing_required_detail",
                    confidence=0.8,
                    probabilities={"missing_required_detail": 0.8},
                )
            },
            scores={
                "correctness_materiality": SimpleNamespace(
                    score=2.0, confidence=0.8, probabilities={2: 0.8}
                )
            },
            model="jev-test",
            usage=SimpleNamespace(input_tokens=100, output_tokens=5),
            model_dump=lambda **_: {"probability": 0.47},
        )

    monkeypatch.setattr(jev_experiment, "evaluate", evaluate)
    return client, events, observations


def test_final_review_receives_completed_judgment(monkeypatch):
    client, events, observations = setup_run(monkeypatch)
    jev_experiment.main()
    assert events.index("jev-complete") < events.index("finalize-answer")
    final = next(o for o in observations if o["name"] == "finalize-answer")
    assert final["output"] == final["input"]["assistant_output"]
    assert final["metadata"]["expected_output"] == final["input"]["expected_output"]
    assessment = final["metadata"]["jev_correctness_assessment"]
    assert assessment["is_correct"]["probability"] == 0.47
    assert assessment["is_correct"]["passed"] is False
    assert (
        assessment["primary_correctness_issue"]["choice"] == "missing_required_detail"
    )
    assert assessment["correctness_materiality"]["score"] == 2.0
    assert all(
        c.kwargs["observation_id"] == "finalize-answer"
        for c in client.create_score.call_args_list
    )
    config = json.loads(
        (Path(__file__).parents[1] / "config/langfuse/evaluator.json").read_text()
    )
    assert {m["variable"]: m.get("jsonPath") for m in config["variableMapping"]} == {
        "assistant_output": None,
        "expected_output": "$.expected_output",
        "jev_correctness_assessment": "$.jev_correctness_assessment",
    }


def test_jev_failure_does_not_trigger_final_review(monkeypatch):
    client, events, _ = setup_run(monkeypatch, fail=True)
    with pytest.raises(RuntimeError, match="Jev unavailable"):
        jev_experiment.main()
    assert "finalize-answer" not in events
    client.create_score.assert_not_called()
    client.shutdown.assert_called_once()
