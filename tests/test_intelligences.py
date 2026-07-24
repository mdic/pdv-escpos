from pathlib import Path

import pytest

from pdv_escpos.config import RenderConfig
from pdv_escpos.imaging import prepare_for_thermal_print
from pdv_escpos.renderer import ReceiptRenderer
from pdv_escpos.template_module import load_template_module

TEMPLATE_DIR = (
    Path(__file__).parents[1] / "src" / "pdv_escpos" / "templates" / "intelligences"
)
MODULE = load_template_module(TEMPLATE_DIR)


def observation(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "questions": None,
        "response": [],
        "seed": None,
        "coordinates": None,
        "ra": None,
        "dec": None,
        "depth": None,
    }
    values.update(overrides)
    return MODULE.build_context(values)


def test_observation_is_reproducible_and_matches_question_count() -> None:
    first = observation(questions=5, seed="SESSION-004271")
    second = observation(questions=5, seed="SESSION-004271")

    assert first["observation_id"] == second["observation_id"]
    assert first["coordinates"] == second["coordinates"]
    assert first["readings"] == second["readings"]
    assert first["constellation"] == second["constellation"]
    assert first["question_count"] == 5
    assert len(first["readings"]) == 5  # type: ignore[arg-type]
    assert len(first["constellation"]) == 10  # type: ignore[arg-type]


def test_responses_and_manual_coordinates_are_preserved() -> None:
    result = observation(
        response=[72, 41, 88],
        seed="ANSWERS-001",
        coordinates="17H 42M 11.8S / +28D 09M 44S / Z+017.62",
    )

    assert result["question_count"] == 3
    assert result["coordinates"] == {
        "ra": "17H 42M 11.8S",
        "dec": "+28D 09M 44S",
        "depth": "Z+017.62",
        "origin": result["coordinates"]["origin"],  # type: ignore[index]
    }
    assert [reading["value"] for reading in result["readings"]] == [  # type: ignore[union-attr]
        72,
        41,
        88,
    ]


def test_invalid_observation_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="match the number"):
        observation(questions=2, response=[50])
    with pytest.raises(ValueError, match="between 0 and 100"):
        observation(response=[101])
    with pytest.raises(ValueError, match="separated by"):
        observation(coordinates="RA / DEC")


def test_many_identical_responses_generate_a_complete_constellation() -> None:
    result = observation(response=[50] * 20, seed="COLLISION-CHECK")

    assert len(result["readings"]) == 20  # type: ignore[arg-type]
    assert len(result["constellation"]) == 10  # type: ignore[arg-type]


def test_intelligences_template_renders_at_printer_width() -> None:
    config = RenderConfig(width=384)
    context = observation(response=[72, 41, 88], seed="RENDER-001")
    image = ReceiptRenderer(MODULE.directory.parent).render(
        MODULE.directory.name,
        context,
        config,
        html_file=MODULE.html_file,
        stylesheet_file=MODULE.stylesheet_file,
        fonts=MODULE.fonts,
    )
    thermal = prepare_for_thermal_print(image, config)

    assert thermal.width == 384
    assert thermal.height > 700
    assert thermal.mode == "1"
