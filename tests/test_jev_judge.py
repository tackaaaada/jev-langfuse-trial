"""Jev応答をLangfuseへ渡す前の境界検証を確認する。"""

from types import SimpleNamespace

import pytest

from src.jev_judge import correctness_assessment


def response(*, choice="no_material_issue", score=0.0):
    return SimpleNamespace(
        nouls={"is_correct": SimpleNamespace(noul=0.8)},
        choices={
            "primary_correctness_issue": SimpleNamespace(
                choice=choice,
                confidence=0.9,
                probabilities={"no_material_issue": 0.9},
            )
        },
        scores={
            "correctness_materiality": SimpleNamespace(
                score=score,
                confidence=0.8,
                probabilities={0: 0.8, 1: 0.2},
            )
        },
        model="jev-test",
    )


def test_assessment_snapshots_response_and_defines_all_langfuse_scores():
    value = response()
    assessment = correctness_assessment(value)
    value.choices["primary_correctness_issue"].probabilities["no_material_issue"] = 0.1

    metadata = assessment.metadata()
    assert metadata["primary_correctness_issue"]["probabilities"] == {
        "no_material_issue": 0.9
    }
    assert [score.name for score in assessment.langfuse_scores()] == [
        "jev_correctness_probability",
        "jev_is_correct",
        "jev_primary_correctness_issue",
        "jev_correctness_materiality",
    ]


@pytest.mark.parametrize(
    ("choice", "score", "message"),
    [
        ("unknown", 0.0, "定義済みの評価軸"),
        ("no_material_issue", 4.0, "0から3"),
    ],
)
def test_assessment_rejects_values_outside_the_rubric(choice, score, message):
    with pytest.raises(ValueError, match=message):
        correctness_assessment(response(choice=choice, score=score))
