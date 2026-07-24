from pathlib import Path

import pytest

from pdv_escpos.template_module import (
    ManifestError,
    create_template_skeleton,
    discover_template_modules,
)


def _write_minimal_template(directory: Path, manifest: str) -> None:
    directory.mkdir()
    (directory / "template.html.j2").write_text(
        '<article id="receipt">{{ message }}</article>', encoding="utf-8"
    )
    (directory / "style.css").write_text("body { color: black; }", encoding="utf-8")
    (directory / "template.yaml").write_text(manifest, encoding="utf-8")


def test_discovery_loads_a_declarative_template(tmp_path: Path) -> None:
    _write_minimal_template(
        tmp_path / "message",
        """
schema_version: 1
name: message
description: Local message receipt.
options:
  - name: message
    type: string
    required: true
    help: Message to print.
""",
    )

    modules = discover_template_modules(tmp_path)

    assert [module.name for module in modules] == ["message"]
    assert modules[0].generator_file is None
    assert modules[0].options[0].flags == ("--message",)


def test_skeleton_creates_a_valid_generated_module(tmp_path: Path) -> None:
    destination = create_template_skeleton(
        tmp_path,
        "star-log",
        description="A generated star log.",
        with_generator=True,
    )

    modules = discover_template_modules(tmp_path)

    assert destination == tmp_path / "star-log"
    assert (destination / "template.yaml").is_file()
    assert (destination / "template.html.j2").is_file()
    assert (destination / "style.css").is_file()
    assert (destination / "generator.py").is_file()
    assert (destination / "README.md").is_file()
    assert (destination / "assets" / "README.md").is_file()
    assert [module.name for module in modules] == ["star-log"]
    assert modules[0].generator_file == "generator.py"
    assert modules[0].build_context({"message": "Hello"}) == {"message": "Hello"}


def test_skeleton_never_overwrites_an_existing_directory(tmp_path: Path) -> None:
    create_template_skeleton(tmp_path, "message")

    with pytest.raises(ManifestError, match="already exists"):
        create_template_skeleton(tmp_path, "message")


def test_manifest_infers_multiple_font_formats(tmp_path: Path) -> None:
    directory = tmp_path / "fonts"
    _write_minimal_template(
        directory,
        """
schema_version: 1
name: fonts
description: Multiple local fonts.
fonts:
  - file: assets/Regular.otf
    family: ReceiptText
  - file: assets/Bold.woff2
    family: ReceiptText
    weight: 700
""",
    )
    (directory / "assets").mkdir()
    (directory / "assets" / "Regular.otf").write_bytes(b"font")
    (directory / "assets" / "Bold.woff2").write_bytes(b"font")

    module = discover_template_modules(tmp_path)[0]

    assert [font.font_format for font in module.fonts] == ["opentype", "woff2"]
    assert [font.weight for font in module.fonts] == ["400", "700"]


def test_manifest_rejects_reserved_module_option(tmp_path: Path) -> None:
    _write_minimal_template(
        tmp_path / "invalid",
        """
schema_version: 1
name: invalid
description: Invalid template.
options:
  - name: output
    type: path
""",
    )

    with pytest.raises(ManifestError, match="reserved"):
        discover_template_modules(tmp_path)
