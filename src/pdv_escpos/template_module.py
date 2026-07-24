from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import cast

import click
import yaml

SCHEMA_VERSION = 1
_RESERVED_OPTION_NAMES = {
    "config",
    "cut",
    "dither",
    "output",
    "product_id",
    "threshold",
    "vendor_id",
    "width",
}
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_RESERVED_MODULE_NAMES = {"new", "templates", "usb-info"}


class ManifestError(ValueError):
    """Raised when a local template manifest is invalid."""


@dataclass(frozen=True)
class OptionSpec:
    name: str
    flags: tuple[str, ...]
    value_type: str
    help: str
    default: object = None
    required: bool = False
    repeatable: bool = False
    minimum: float | int | None = None
    maximum: float | int | None = None
    choices: tuple[object, ...] = ()

    def click_type(self) -> click.ParamType:
        if self.choices:
            return click.Choice(self.choices)
        if self.value_type == "integer":
            return click.IntRange(
                min=cast(int | None, self.minimum),
                max=cast(int | None, self.maximum),
            )
        if self.value_type == "number":
            return click.FloatRange(
                min=cast(float | None, self.minimum),
                max=cast(float | None, self.maximum),
            )
        if self.value_type == "boolean":
            return click.BOOL
        if self.value_type == "path":
            return click.Path(path_type=Path)
        return click.STRING

    def to_click_option(self) -> click.Option:
        declarations = [*self.flags, self.name]
        default = () if self.repeatable and self.default is None else self.default
        return click.Option(
            param_decls=declarations,
            type=self.click_type(),
            help=self.help,
            default=default,
            required=self.required,
            multiple=self.repeatable,
            is_flag=self.value_type == "boolean",
            show_default=self.default is not None,
        )


@dataclass(frozen=True)
class TemplateModule:
    name: str
    description: str
    directory: Path
    html_file: str
    stylesheet_file: str
    generator_file: str | None
    font_file: str | None
    font_family: str | None
    font_format: str | None
    options: tuple[OptionSpec, ...]

    def build_context(self, values: Mapping[str, object]) -> dict[str, object]:
        normalised: dict[str, object] = {}
        for option in self.options:
            value = values.get(option.name)
            if option.repeatable and isinstance(value, tuple):
                value = list(value)
            normalised[option.name] = value
        if self.generator_file is None:
            return normalised

        generator_path = self.directory / self.generator_file
        module = _load_python_module(self.name, generator_path)
        callback = getattr(module, "build_context", None)
        if not callable(callback):
            raise ManifestError(
                f"{generator_path} must define a callable build_context(options)"
            )
        result = callback(normalised)
        if not isinstance(result, dict) or not all(
            isinstance(key, str) for key in result
        ):
            raise ManifestError(
                f"{generator_path} build_context() must return a string-keyed mapping"
            )
        return cast(dict[str, object], result)


def _load_python_module(name: str, path: Path) -> ModuleType:
    module_name = f"pdv_escpos_local_template_{name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ManifestError(f"Cannot load template generator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ManifestError(f"{field} must be a string-keyed mapping")
    return cast(dict[str, object], value)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string")
    return value.strip()


def _boolean(value: object, field: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ManifestError(f"{field} must be a boolean")
    return value


def _number(value: object, field: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{field} must be numeric")
    return value


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ManifestError(f"{field} must be a list")
    return value


def _load_option(value: object, index: int) -> OptionSpec:
    field = f"options[{index}]"
    data = _mapping(value, field)
    name = _string(data.get("name"), f"{field}.name")
    if not _NAME_PATTERN.fullmatch(name):
        raise ManifestError(f"{field}.name must use lowercase snake_case")
    if name in _RESERVED_OPTION_NAMES:
        raise ManifestError(f"{field}.name '{name}' is reserved by render/build/print")

    raw_flags = data.get("flags", [f"--{name.replace('_', '-')}"])
    flags = tuple(
        _string(flag, f"{field}.flags")
        for flag in _sequence(raw_flags, f"{field}.flags")
    )
    if not flags or any(not flag.startswith("-") for flag in flags):
        raise ManifestError(f"{field}.flags must contain CLI option names")

    value_type = _string(data.get("type", "string"), f"{field}.type")
    if value_type not in {"string", "integer", "number", "boolean", "path"}:
        raise ManifestError(
            f"{field}.type must be string, integer, number, boolean or path"
        )
    repeatable = _boolean(data.get("repeatable"), f"{field}.repeatable")
    if value_type == "boolean" and repeatable:
        raise ManifestError(f"{field} boolean options cannot be repeatable")

    choices_value = data.get("choices", [])
    choices = tuple(_sequence(choices_value, f"{field}.choices"))
    minimum = _number(data.get("minimum"), f"{field}.minimum")
    maximum = _number(data.get("maximum"), f"{field}.maximum")
    if value_type not in {"integer", "number"} and (
        minimum is not None or maximum is not None
    ):
        raise ManifestError(f"{field} ranges require an integer or number type")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ManifestError(f"{field}.minimum cannot exceed maximum")

    return OptionSpec(
        name=name,
        flags=flags,
        value_type=value_type,
        help=str(data.get("help", "")),
        default=data.get("default"),
        required=_boolean(data.get("required"), f"{field}.required"),
        repeatable=repeatable,
        minimum=minimum,
        maximum=maximum,
        choices=choices,
    )


def load_template_module(directory: Path) -> TemplateModule:
    manifest_path = directory / "template.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    data = _mapping(raw, str(manifest_path))
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ManifestError(f"{manifest_path}: schema_version must be {SCHEMA_VERSION}")

    name = _string(data.get("name"), "name")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise ManifestError("name must use lowercase letters, numbers and hyphens")
    if name in _RESERVED_MODULE_NAMES:
        raise ManifestError(f"module name '{name}' is reserved by the core CLI")
    description = _string(data.get("description"), "description")
    html_file = _string(data.get("template", "template.html.j2"), "template")
    stylesheet_file = _string(data.get("stylesheet", "style.css"), "stylesheet")
    generator_value = data.get("generator")
    generator_file = (
        _string(generator_value, "generator") if generator_value is not None else None
    )
    font_value = data.get("font")
    if font_value is None:
        font_file = None
        font_family = None
        font_format = None
    else:
        font_data = _mapping(font_value, "font")
        font_file = _string(font_data.get("file"), "font.file")
        font_family = _string(font_data.get("family", "ReceiptPixel"), "font.family")
        font_format = _string(font_data.get("format", "truetype"), "font.format")
        if font_format not in {"truetype", "opentype", "woff2"}:
            raise ManifestError("font.format must be truetype, opentype or woff2")

    for filename, field in ((html_file, "template"), (stylesheet_file, "stylesheet")):
        if not (directory / filename).is_file():
            raise ManifestError(f"{field} file does not exist: {directory / filename}")
    if generator_file is not None and not (directory / generator_file).is_file():
        raise ManifestError(
            f"generator file does not exist: {directory / generator_file}"
        )
    if font_file is not None and not (directory / font_file).is_file():
        raise ManifestError(f"font file does not exist: {directory / font_file}")

    raw_options = _sequence(data.get("options", []), "options")
    options = tuple(
        _load_option(option, index) for index, option in enumerate(raw_options)
    )
    option_names = [option.name for option in options]
    if len(option_names) != len(set(option_names)):
        raise ManifestError(f"{manifest_path}: option names must be unique")

    return TemplateModule(
        name=name,
        description=description,
        directory=directory,
        html_file=html_file,
        stylesheet_file=stylesheet_file,
        generator_file=generator_file,
        font_file=font_file,
        font_family=font_family,
        font_format=font_format,
        options=options,
    )


def create_template_skeleton(
    template_root: Path,
    name: str,
    *,
    description: str | None = None,
    with_generator: bool = False,
) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise ManifestError(
            "template name must use lowercase letters, numbers and hyphens"
        )
    if name in _RESERVED_MODULE_NAMES:
        raise ManifestError(f"template name '{name}' is reserved by the core CLI")

    destination = template_root / name
    if destination.exists():
        raise ManifestError(f"template directory already exists: {destination}")

    destination.mkdir(parents=True)
    (destination / "assets").mkdir()
    schema_comment = (
        "# yaml-language-server: $schema=../../template.schema.json\n"
        if (template_root.parent / "template.schema.json").is_file()
        else ""
    )
    generator_declaration = "generator: generator.py\n" if with_generator else ""
    manifest_description = description or f"Local {name} receipt template."
    escaped_description = json.dumps(manifest_description, ensure_ascii=False)
    manifest = (
        f"{schema_comment}"
        "schema_version: 1\n"
        f"name: {name}\n"
        f"description: {escaped_description}\n"
        "template: template.html.j2\n"
        "stylesheet: style.css\n"
        f"{generator_declaration}\n"
        "options:\n"
        "  - name: message\n"
        "    flags: [--message, -m]\n"
        "    type: string\n"
        "    default: Hello from a local template.\n"
        "    help: Message printed by this template.\n"
    )
    (destination / "template.yaml").write_text(manifest, encoding="utf-8")
    (destination / "template.html.j2").write_text(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width={{ receipt_width }}, initial-scale=1" />
    <style>{{ stylesheet | safe }}</style>
  </head>
  <body>
    <article id="receipt" class="receipt">
      <h1>LOCAL READOUT</h1>
      <p>{{ message }}</p>
    </article>
  </body>
</html>
""",
        encoding="utf-8",
    )
    (destination / "style.css").write_text(
        """* { box-sizing: border-box; }
html, body { margin: 0; background: #fff; color: #000; }
body { font-family: monospace; }
.receipt { width: 100%; padding: 12px 10px 24px; font-size: 18px; }
h1 { margin: 0 0 16px; border-bottom: 2px solid #000; font-size: 28px; }
p { margin: 0; overflow-wrap: anywhere; }
""",
        encoding="utf-8",
    )
    (destination / "assets" / "README.md").write_text(
        "Place local fonts, images and licence files in this directory.\n",
        encoding="utf-8",
    )
    if with_generator:
        (destination / "generator.py").write_text(
            """from __future__ import annotations

from collections.abc import Mapping


def build_context(options: Mapping[str, object]) -> dict[str, object]:
    return {"message": str(options.get("message") or "")}
""",
            encoding="utf-8",
        )

    _ = load_template_module(destination)
    return destination


def discover_template_modules(template_root: Path) -> list[TemplateModule]:
    modules = [
        load_template_module(directory)
        for directory in sorted(template_root.iterdir())
        if directory.is_dir() and (directory / "template.yaml").is_file()
    ]
    names = [module.name for module in modules]
    if len(names) != len(set(names)):
        raise ManifestError("template module names must be unique")
    return modules
