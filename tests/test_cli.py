from pathlib import Path

from click.testing import CliRunner

from pdv_escpos.cli import TEMPLATE_ROOT, create_app


def test_discovery_registers_template_groups_and_commands() -> None:
    runner = CliRunner()
    app = create_app(TEMPLATE_ROOT)

    root_help = runner.invoke(app, ["--help"])
    module_help = runner.invoke(app, ["intelligences", "render", "--help"])

    assert root_help.exit_code == 0
    assert "intelligences" in root_help.output
    assert "templates" in root_help.output
    assert module_help.exit_code == 0
    assert "--questions" in module_help.output
    assert "--response" in module_help.output
    assert "--output" in module_help.output


def test_module_options_are_limited_to_their_template() -> None:
    runner = CliRunner()
    app = create_app(TEMPLATE_ROOT)

    result = runner.invoke(app, ["demo", "render", "--questions", "3"])

    assert result.exit_code == 2
    assert "No such option '--questions'" in result.output


def test_templates_command_reports_generator_type() -> None:
    runner = CliRunner()
    app = create_app(TEMPLATE_ROOT)

    result = runner.invoke(app, ["templates"])

    assert result.exit_code == 0
    assert "demo" in result.output
    assert "declarative" in result.output
    assert "intelligences" in result.output
    assert "generator" in result.output


def test_new_command_bootstraps_an_auto_discovered_module(tmp_path: Path) -> None:
    runner = CliRunner()
    initial_app = create_app(tmp_path)

    created = runner.invoke(
        initial_app,
        [
            "new",
            "star-log",
            "--description",
            "Generated from the CLI.",
            "--with-generator",
        ],
    )
    discovered_app = create_app(tmp_path)
    module_help = runner.invoke(discovered_app, ["star-log", "render", "--help"])

    assert created.exit_code == 0, created.output
    assert "Created template module" in created.output
    assert module_help.exit_code == 0
    assert "--message" in module_help.output


def test_modular_render_writes_preview(tmp_path: Path) -> None:
    runner = CliRunner()
    app = create_app(TEMPLATE_ROOT)
    output = tmp_path / "preview.png"

    result = runner.invoke(
        app,
        [
            "intelligences",
            "render",
            "--questions",
            "2",
            "--seed",
            "CLI-TEST",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.is_file()
    assert "Rendered" in result.output
