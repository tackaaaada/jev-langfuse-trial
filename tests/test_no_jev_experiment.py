"""Jevなし条件で一次評価が混入せず、3件を安全に送れることを確認する。"""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from src import no_jev_experiment


def test_without_jev_sends_three_observations(monkeypatch, tmp_path):
    import langfuse
    import typesafe_sdk

    for key in ("LANGFUSE_BASE_URL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.setenv(key, "test")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(no_jev_experiment, "load_dotenv", lambda *_: None)
    project = Path(__file__).parents[1]
    (tmp_path / "data").mkdir()
    case = json.loads((project / "data/long_semantic_match.json").read_text())
    (tmp_path / "data/long_semantic_match.json").write_text(json.dumps(case))
    monkeypatch.setattr(no_jev_experiment, "__file__", str(tmp_path / "src/module.py"))
    forbidden = MagicMock(side_effect=AssertionError("Jev must not be called"))
    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", forbidden)
    client = MagicMock()
    client.get_trace_url.return_value = "http://localhost/test"
    observations = []

    @contextmanager
    def observation(**kwargs):
        client.shutdown.assert_not_called()
        observations.append(kwargs)
        span = MagicMock()
        span.id = f"observation-{len(observations)}"
        span.trace_id = f"trace-{len(observations)}"
        yield span

    client.start_as_current_observation.side_effect = observation
    monkeypatch.setattr(langfuse, "Langfuse", lambda: client)
    results = no_jev_experiment.main(repeat=3)
    assert len(results) == 3
    assert len({r["trace_id"] for r in results}) == 3
    assert [o["metadata"]["run_index"] for o in observations] == [1, 2, 3]
    for o in observations:
        assert o["name"] == "finalize-answer-without-jev"
        assert o["output"] == case["assistant_output"]
        assert o["metadata"]["expected_output"] == case["expected_output"]
        assert "jev_result" not in o["metadata"]
    forbidden.assert_not_called()
    client.create_score.assert_not_called()
    client.shutdown.assert_called_once()


def test_control_preserves_rubric_and_model():
    directory = Path(__file__).parents[1] / "config/langfuse"
    treatment = json.loads((directory / "evaluator.json").read_text())
    control = json.loads((directory / "evaluator-without-jev.json").read_text())
    assert control["modelConfig"] == treatment["modelConfig"]
    assert (
        control["prompt"][0]["content"]
        == treatment["prompt"][0]["content"].split("\n\n## Preliminary Jev assessment")[
            0
        ]
    )
    assert control["variableMapping"] == [
        m for m in treatment["variableMapping"] if m["variable"] != "jev_result"
    ]
    assert "Jev" not in control["outputDefinition"]["scoreReasoningInstructions"]
