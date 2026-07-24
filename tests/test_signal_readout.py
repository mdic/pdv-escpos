from pathlib import Path

from click.testing import CliRunner

from pdv_escpos.cli import TEMPLATE_ROOT, create_app
from pdv_escpos.config import RenderConfig
from pdv_escpos.imaging import prepare_for_thermal_print
from pdv_escpos.renderer import ReceiptRenderer
from pdv_escpos.template_module import load_template_module

TEMPLATE_DIR = TEMPLATE_ROOT / "signal-readout"
MODULE = load_template_module(TEMPLATE_DIR)


def signal_context(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        option.name: []
        if option.repeatable and option.default is None
        else option.default
        for option in MODULE.options
    }
    values.update(overrides)
    return MODULE.build_context(values)


def test_synthetic_preset_honours_count_channels_and_range() -> None:
    context = signal_context(
        preset="seismic",
        count=64,
        channels=3,
        minimum=-2.5,
        maximum=4.0,
        seed="SYNTHETIC-TEST",
    )

    assert context["mode"] == "SYNTHETIC"
    assert context["sample_count"] == 64
    assert context["channel_count"] == 3
    assert context["layout"] == "SEPARATE"
    assert -2.5 <= context["global_min"] <= 4.0  # type: ignore[operator]
    assert -2.5 <= context["global_max"] <= 4.0  # type: ignore[operator]
    assert context["canvas_length"] == 900


def test_csv_columns_become_separate_channels(tmp_path: Path) -> None:
    source = tmp_path / "sample.csv"
    source.write_text(
        "time,alpha,beta\n0,0.1,1.0\n1,0.4,0.7\n2,-0.2,1.2\n3,0.8,0.1\n",
        encoding="utf-8",
    )

    context = signal_context(
        source=source,
        format="csv",
        column=["alpha", "beta"],
        sample_rate=2.0,
    )

    assert context["mode"] == "EXTERNAL"
    assert context["data_format"] == "CSV"
    assert context["channel_count"] == 2
    assert context["sample_count"] == 4
    assert context["duration"] == 1.5


def test_json_can_request_overlay_layout(tmp_path: Path) -> None:
    source = tmp_path / "sample.json"
    source.write_text(
        '{"layout":"overlay","channels":{"north":[1,2,3],"south":[3,2,1]}}',
        encoding="utf-8",
    )

    context = signal_context(source=source, format="auto")

    assert context["data_format"] == "JSON"
    assert context["layout"] == "OVERLAY"
    assert context["channel_count"] == 2


def test_text_input_is_a_single_channel(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("# sample\n0.1\n0.2\n-0.4\n", encoding="utf-8")

    context = signal_context(source=source, format="text")

    assert context["data_format"] == "TEXT"
    assert context["channel_count"] == 1
    assert context["sample_count"] == 3


def test_landscape_template_rotates_to_printer_width() -> None:
    config = RenderConfig(width=384)
    context = signal_context(preset="ecg", count=80, channels=2, seed="ROTATE")
    image = ReceiptRenderer(MODULE.directory.parent).render(
        MODULE.directory.name,
        context,
        config,
        html_file=MODULE.html_file,
        stylesheet_file=MODULE.stylesheet_file,
        fonts=MODULE.fonts,
        orientation=MODULE.orientation,
        canvas_length=MODULE.resolve_canvas_length(context, config.width),
    )
    thermal = prepare_for_thermal_print(image, config)

    assert thermal.size == (384, 940)
    assert thermal.mode == "1"


def test_canvas_length_grows_with_the_number_of_samples() -> None:
    short = signal_context(count=40, seed="LENGTH")
    long = signal_context(count=400, seed="LENGTH")

    assert short["canvas_length"] == 900
    assert long["canvas_length"] == 1900


def test_stdin_supplies_a_complete_text_sample(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "stdin.png"

    result = runner.invoke(
        create_app(TEMPLATE_ROOT),
        [
            "signal-readout",
            "render",
            "--stdin",
            "--format",
            "text",
            "--output",
            str(output),
        ],
        input="0.1\n0.3\n-0.2\n0.7\n",
    )

    assert result.exit_code == 0, result.output
    assert output.is_file()
