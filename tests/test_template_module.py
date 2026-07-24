from pathlib import Path

import pytest

from pdv_escpos.template_module import ManifestError, discover_template_modules


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
