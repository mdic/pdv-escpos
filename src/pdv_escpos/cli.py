from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import click
import usb.core
from PIL import Image

from .config import (
    AppConfig,
    DitherMode,
    load_config,
    with_render_overrides,
    with_usb_overrides,
)
from .imaging import prepare_for_thermal_print
from .printer import build_escpos_job, print_usb
from .renderer import ReceiptRenderer
from .template_module import (
    ManifestError,
    TemplateModule,
    discover_template_modules,
)

TEMPLATE_ROOT = Path(__file__).parent / "templates"


def _config_option() -> click.Option:
    return click.Option(
        ["--config", "-c"],
        type=click.Path(path_type=Path),
        default=Path("config.yaml"),
        show_default=True,
        help="YAML printer configuration file.",
    )


def _width_option() -> click.Option:
    return click.Option(
        ["--width"],
        type=click.IntRange(min=64),
        help="Override printable width in dots.",
    )


def _render_options(module: TemplateModule) -> list[click.Option]:
    return [
        click.Option(
            ["--output", "-o"],
            type=click.Path(path_type=Path),
            default=Path(f"output/{module.name}.png"),
            show_default=True,
            help="Output PNG path.",
        ),
        _config_option(),
        _width_option(),
        click.Option(
            ["--dither"],
            type=click.Choice(("threshold", "floyd-steinberg", "none")),
            help="Override monochrome conversion mode.",
        ),
        click.Option(
            ["--threshold"],
            type=click.IntRange(min=0, max=255),
            help="Override the black/white threshold.",
        ),
    ]


def _build_options(module: TemplateModule) -> list[click.Option]:
    return [
        click.Option(
            ["--output", "-o"],
            type=click.Path(path_type=Path),
            default=Path(f"output/{module.name}.bin"),
            show_default=True,
            help="Output ESC/POS binary path.",
        ),
        _config_option(),
        _width_option(),
    ]


def _print_options() -> list[click.Option]:
    return [
        _config_option(),
        _width_option(),
        click.Option(
            ["--vendor-id"],
            help="Override USB vendor ID, for example 0x28e9.",
        ),
        click.Option(
            ["--product-id"],
            help="Override USB product ID, for example 0x0289.",
        ),
        click.Option(
            ["--cut/--no-cut"],
            default=None,
            help="Override cutter use.",
        ),
    ]


def _module_values(
    module: TemplateModule, values: dict[str, object]
) -> dict[str, object]:
    return {option.name: values.pop(option.name) for option in module.options}


def _render_image(
    module: TemplateModule,
    values: dict[str, object],
    *,
    dither: DitherMode | None = None,
    threshold: int | None = None,
) -> tuple[Image.Image, AppConfig]:
    module_values = _module_values(module, values)
    context = module.build_context(module_values)
    config_path = cast(Path | None, values.pop("config"))
    width = cast(int | None, values.pop("width"))
    config = with_render_overrides(
        load_config(config_path),
        width=width,
        dither=dither,
        threshold=threshold,
    )
    rendered = ReceiptRenderer(module.directory.parent).render(
        module.directory.name,
        context,
        config.render,
        html_file=module.html_file,
        stylesheet_file=module.stylesheet_file,
        font_file=module.font_file,
        font_family=module.font_family,
        font_format=module.font_format,
    )
    return prepare_for_thermal_print(rendered, config.render), config


def _run_render(module: TemplateModule, values: dict[str, object]) -> None:
    output = cast(Path, values.pop("output"))
    dither = cast(DitherMode | None, values.pop("dither"))
    threshold = cast(int | None, values.pop("threshold"))
    image, _ = _render_image(module, values, dither=dither, threshold=threshold)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    click.secho(
        f"Rendered {output} ({image.width}×{image.height}px, mode {image.mode})",
        fg="green",
    )


def _run_build(module: TemplateModule, values: dict[str, object]) -> None:
    output = cast(Path, values.pop("output"))
    image, config = _render_image(module, values)
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_bytes(build_escpos_job(image, config))
    click.secho(f"Built {output} ({output.stat().st_size} bytes)", fg="green")


def _run_print(module: TemplateModule, values: dict[str, object]) -> None:
    vendor_id = cast(str | None, values.pop("vendor_id"))
    product_id = cast(str | None, values.pop("product_id"))
    cut = cast(bool | None, values.pop("cut"))
    image, config = _render_image(module, values)
    config = with_usb_overrides(
        config,
        vendor_id=vendor_id,
        product_id=product_id,
        cut=cut,
    )
    destination = f"{config.usb.vendor_id:#06x}:{config.usb.product_id:#06x}"
    click.echo(f"Printing {image.width}×{image.height}px to USB {destination}…")
    try:
        print_usb(image, config)
    except Exception as error:
        raise click.ClickException(f"USB printing failed: {error}") from error
    click.secho("Print job sent.", fg="green")


def _action_callback(module: TemplateModule, action: str):
    def callback(**values: object) -> None:
        try:
            if action == "render":
                _run_render(module, values)
            elif action == "build":
                _run_build(module, values)
            else:
                _run_print(module, values)
        except (ManifestError, ValueError) as error:
            raise click.ClickException(str(error)) from error

    return callback


def _module_command(module: TemplateModule, action: str) -> click.Command:
    module_options = [option.to_click_option() for option in module.options]
    if action == "render":
        help_text = "Render a PNG preview without accessing the printer."
        common_options = _render_options(module)
    elif action == "build":
        help_text = "Build a raw ESC/POS job without opening the USB device."
        common_options = _build_options(module)
    else:
        help_text = "Render and print on the configured USB ESC/POS printer."
        common_options = _print_options()
    return click.Command(
        name=action,
        callback=_action_callback(module, action),
        params=[*module_options, *common_options],
        help=help_text,
    )


def _module_group(module: TemplateModule) -> click.Group:
    group = click.Group(
        name=module.name,
        help=module.description,
        no_args_is_help=True,
    )
    for action in ("render", "build", "print"):
        group.add_command(_module_command(module, action))
    return group


def _templates_command(modules: list[TemplateModule]) -> click.Command:
    def callback() -> None:
        if not modules:
            click.echo("No template modules found.")
            return
        name_width = max(len(module.name) for module in modules)
        for module in modules:
            generator = "generator" if module.generator_file else "declarative"
            click.echo(
                f"{module.name:<{name_width}}  {generator:<11}  {module.description}"
            )

    return click.Command(
        name="templates",
        callback=callback,
        help="List template modules discovered from template.yaml manifests.",
    )


def _usb_info() -> None:
    click.echo("VID:PID    PRINTER  MANUFACTURER  PRODUCT")
    found = usb.core.find(find_all=True)
    devices = cast(Iterable[object], found) if found is not None else ()
    for device in devices:
        is_printer = False
        try:
            is_printer = any(
                getattr(interface, "bInterfaceClass", None) == 7
                for configuration in cast(Iterable[object], device)
                for interface in cast(Iterable[object], configuration)
            )
        except (OSError, TypeError, ValueError):
            pass
        try:
            manufacturer = str(getattr(device, "manufacturer", "") or "")
            product = str(getattr(device, "product", "") or "")
        except (OSError, TypeError, ValueError):
            manufacturer = "<permission denied>"
            product = "<permission denied>"
        vendor_id = int(getattr(device, "idVendor", 0))
        product_id = int(getattr(device, "idProduct", 0))
        click.echo(
            f"{vendor_id:04x}:{product_id:04x}  "
            f"{'yes' if is_printer else 'no ':<7}  "
            f"{manufacturer:<12}  {product}"
        )


def create_app(template_root: Path = TEMPLATE_ROOT) -> click.Group:
    modules = discover_template_modules(template_root)
    root = click.Group(
        name="pdv-escpos",
        help="Render modular HTML/CSS receipts and print them over ESC/POS.",
        no_args_is_help=True,
    )
    for module in modules:
        root.add_command(_module_group(module))
    root.add_command(_templates_command(modules))
    root.add_command(
        click.Command(
            name="usb-info",
            callback=_usb_info,
            help="List attached USB devices and mark printer-class interfaces.",
        )
    )
    return root


app = create_app()
