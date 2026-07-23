from datetime import datetime, timezone

import pytest

from pdv_escpos.config import RenderConfig
from pdv_escpos.imaging import prepare_for_thermal_print
from pdv_escpos.intelligences import build_observation
from pdv_escpos.renderer import ReceiptRenderer

OBSERVED_AT = datetime(2026, 7, 23, 18, 42, tzinfo=timezone.utc)


def test_observation_is_reproducible_and_matches_question_count() -> None:
    first = build_observation(
        questions=5,
        seed="SESSION-004271",
        observed_at=OBSERVED_AT,
    )
    second = build_observation(
        questions=5,
        seed="SESSION-004271",
        observed_at=OBSERVED_AT,
    )

    assert first == second
    assert first["question_count"] == 5
    assert len(first["readings"]) == 5  # type: ignore[arg-type]
    assert len(first["constellation"]) == 10  # type: ignore[arg-type]


def test_responses_and_manual_coordinates_are_preserved() -> None:
    observation = build_observation(
        responses=[72, 41, 88],
        seed="ANSWERS-001",
        coordinates="17H 42M 11.8S / +28D 09M 44S / Z+017.62",
        observed_at=OBSERVED_AT,
    )

    assert observation["question_count"] == 3
    assert observation["coordinates"] == {
        "ra": "17H 42M 11.8S",
        "dec": "+28D 09M 44S",
        "depth": "Z+017.62",
        "origin": observation["coordinates"]["origin"],  # type: ignore[index]
    }
    assert [reading["value"] for reading in observation["readings"]] == [  # type: ignore[union-attr]
        72,
        41,
        88,
    ]


def test_invalid_observation_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="match the number"):
        build_observation(questions=2, responses=[50])
    with pytest.raises(ValueError, match="between 0 and 100"):
        build_observation(responses=[101])
    with pytest.raises(ValueError, match="separated by"):
        build_observation(coordinates="RA / DEC")


def test_many_identical_responses_generate_a_complete_constellation() -> None:
    observation = build_observation(
        responses=[50] * 20,
        seed="COLLISION-CHECK",
        observed_at=OBSERVED_AT,
    )

    assert len(observation["readings"]) == 20  # type: ignore[arg-type]
    assert len(observation["constellation"]) == 10  # type: ignore[arg-type]


def test_intelligences_template_renders_at_printer_width() -> None:
    config = RenderConfig(width=384)
    observation = build_observation(
        responses=[72, 41, 88],
        seed="RENDER-001",
        observed_at=OBSERVED_AT,
    )
    image = ReceiptRenderer().render("intelligences", observation, config)
    thermal = prepare_for_thermal_print(image, config)

    assert thermal.width == 384
    assert thermal.height > 700
    assert thermal.mode == "1"
