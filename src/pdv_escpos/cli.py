from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, cast

import typer
import usb.core
from rich.console import Console
from rich.table import Table

from .config import (
    DitherMode,
    load_config,
    with_render_overrides,
    with_usb_overrides,
)
from .imaging import prepare_for_thermal_print
from .intelligences import build_observation
from .printer import build_escpos_job, print_usb
from .renderer import ReceiptRenderer

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Render HTML/CSS receipts and print them on a USB ESC/POS printer.",
)
console = Console()

ConfigPath = Annotated[
    Path | None, typer.Option("--config", "-c", help="YAML configuration file.")
]


def _receipt_context(
    title: str,
    subtitle: str,
    message: str,
    status: str,
    reference: str,
    footer: str,
    items: list[str] | None,
    *,
    template: str,
    questions: int | None,
    responses: list[float] | None,
    seed: str | None,
    coordinates: str | None,
    ra: str | None,
    dec: str | None,
    depth: str | None,
) -> dict[str, object]:
    if template == "intelligences":
        try:
            return build_observation(
                questions=questions,
                responses=responses,
                seed=seed,
                coordinates=coordinates,
                ra=ra,
                dec=dec,
                depth=depth,
            )
        except ValueError as error:
            raise typer.BadParameter(str(error)) from error

    return {
        "title": title,
        "subtitle": subtitle,
        "message": message,
        "status": status,
        "reference": reference,
        "footer": footer,
        "items": items or [],
    }


def _render_receipt(
    *,
    template: str,
    config_path: Path | None,
    width: int | None,
    dither: DitherMode | None,
    threshold: int | None,
    context: dict[str, object],
):
    config = with_render_overrides(
        load_config(config_path),
        width=width,
        dither=dither,
        threshold=threshold,
    )
    rendered = ReceiptRenderer().render(template, context, config.render)
    return prepare_for_thermal_print(rendered, config.render), config


@app.command()
def render(
    title: Annotated[
        str, typer.Option(help="Main receipt title.")
    ] = "Thermal dispatch",
    subtitle: Annotated[
        str, typer.Option(help="Secondary heading.")
    ] = "HTML/CSS rendering prototype",
    message: Annotated[
        str, typer.Option(help="Main receipt copy.")
    ] = "The rendering pipeline is operational.",
    status: Annotated[str, typer.Option(help="Short status label.")] = "READY",
    reference: Annotated[str, typer.Option(help="Document reference.")] = "PDV-001",
    footer: Annotated[str, typer.Option(help="Footer copy.")] = "End of transmission",
    item: Annotated[
        list[str] | None, typer.Option("--item", help="Repeatable list item.")
    ] = None,
    questions: Annotated[
        int | None, typer.Option(help="Number of synthetic response readings.")
    ] = None,
    response: Annotated[
        list[float] | None,
        typer.Option("--response", help="Repeatable response value from 0 to 100."),
    ] = None,
    seed: Annotated[
        str | None, typer.Option(help="Seed used to reproduce an observation.")
    ] = None,
    coordinates: Annotated[
        str | None, typer.Option(help="RA / DEC / depth coordinate override.")
    ] = None,
    ra: Annotated[str | None, typer.Option(help="RA-SYN coordinate override.")] = None,
    dec: Annotated[
        str | None, typer.Option(help="DEC-SYN coordinate override.")
    ] = None,
    depth: Annotated[str | None, typer.Option(help="Depth vector override.")] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output PNG path.")
    ] = Path("output/preview.png"),
    template: Annotated[str, typer.Option(help="Template directory name.")] = "demo",
    config: ConfigPath = Path("config.yaml"),
    width: Annotated[
        int | None, typer.Option(help="Override printable width in dots.")
    ] = None,
    dither: Annotated[
        DitherMode | None, typer.Option(help="threshold, floyd-steinberg or none.")
    ] = None,
    threshold: Annotated[
        int | None, typer.Option(help="Black/white threshold from 0 to 255.")
    ] = None,
) -> None:
    """Render a receipt preview without accessing the printer."""
    context = _receipt_context(
        title,
        subtitle,
        message,
        status,
        reference,
        footer,
        item,
        template=template,
        questions=questions,
        responses=response,
        seed=seed,
        coordinates=coordinates,
        ra=ra,
        dec=dec,
        depth=depth,
    )
    image, _ = _render_receipt(
        template=template,
        config_path=config,
        width=width,
        dither=dither,
        threshold=threshold,
        context=context,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    console.print(
        f"[green]Rendered[/green] {output} ({image.width}×{image.height}px, mode {image.mode})"
    )


@app.command("build")
def build(
    title: Annotated[
        str, typer.Option(help="Main receipt title.")
    ] = "Thermal dispatch",
    subtitle: Annotated[
        str, typer.Option(help="Secondary heading.")
    ] = "HTML/CSS rendering prototype",
    message: Annotated[
        str, typer.Option(help="Main receipt copy.")
    ] = "The rendering pipeline is operational.",
    status: Annotated[str, typer.Option(help="Short status label.")] = "READY",
    reference: Annotated[str, typer.Option(help="Document reference.")] = "PDV-001",
    footer: Annotated[str, typer.Option(help="Footer copy.")] = "End of transmission",
    item: Annotated[
        list[str] | None, typer.Option("--item", help="Repeatable list item.")
    ] = None,
    questions: Annotated[
        int | None, typer.Option(help="Number of synthetic response readings.")
    ] = None,
    response: Annotated[
        list[float] | None,
        typer.Option("--response", help="Repeatable response value from 0 to 100."),
    ] = None,
    seed: Annotated[
        str | None, typer.Option(help="Seed used to reproduce an observation.")
    ] = None,
    coordinates: Annotated[
        str | None, typer.Option(help="RA / DEC / depth coordinate override.")
    ] = None,
    ra: Annotated[str | None, typer.Option(help="RA-SYN coordinate override.")] = None,
    dec: Annotated[
        str | None, typer.Option(help="DEC-SYN coordinate override.")
    ] = None,
    depth: Annotated[str | None, typer.Option(help="Depth vector override.")] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output ESC/POS binary path.")
    ] = Path("output/receipt.bin"),
    template: Annotated[str, typer.Option(help="Template directory name.")] = "demo",
    config: ConfigPath = Path("config.yaml"),
    width: Annotated[
        int | None, typer.Option(help="Override printable width in dots.")
    ] = None,
) -> None:
    """Build a raw ESC/POS job without opening the USB device."""
    context = _receipt_context(
        title,
        subtitle,
        message,
        status,
        reference,
        footer,
        item,
        template=template,
        questions=questions,
        responses=response,
        seed=seed,
        coordinates=coordinates,
        ra=ra,
        dec=dec,
        depth=depth,
    )
    image, loaded = _render_receipt(
        template=template,
        config_path=config,
        width=width,
        dither=None,
        threshold=None,
        context=context,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_bytes(build_escpos_job(image, loaded))
    console.print(f"[green]Built[/green] {output} ({output.stat().st_size} bytes)")


@app.command("print")
def print_receipt(
    title: Annotated[
        str, typer.Option(help="Main receipt title.")
    ] = "Thermal dispatch",
    subtitle: Annotated[
        str, typer.Option(help="Secondary heading.")
    ] = "HTML/CSS rendering prototype",
    message: Annotated[
        str, typer.Option(help="Main receipt copy.")
    ] = "The rendering pipeline is operational.",
    status: Annotated[str, typer.Option(help="Short status label.")] = "READY",
    reference: Annotated[str, typer.Option(help="Document reference.")] = "PDV-001",
    footer: Annotated[str, typer.Option(help="Footer copy.")] = "End of transmission",
    item: Annotated[
        list[str] | None, typer.Option("--item", help="Repeatable list item.")
    ] = None,
    questions: Annotated[
        int | None, typer.Option(help="Number of synthetic response readings.")
    ] = None,
    response: Annotated[
        list[float] | None,
        typer.Option("--response", help="Repeatable response value from 0 to 100."),
    ] = None,
    seed: Annotated[
        str | None, typer.Option(help="Seed used to reproduce an observation.")
    ] = None,
    coordinates: Annotated[
        str | None, typer.Option(help="RA / DEC / depth coordinate override.")
    ] = None,
    ra: Annotated[str | None, typer.Option(help="RA-SYN coordinate override.")] = None,
    dec: Annotated[
        str | None, typer.Option(help="DEC-SYN coordinate override.")
    ] = None,
    depth: Annotated[str | None, typer.Option(help="Depth vector override.")] = None,
    template: Annotated[str, typer.Option(help="Template directory name.")] = "demo",
    config: ConfigPath = Path("config.yaml"),
    width: Annotated[
        int | None, typer.Option(help="Override printable width in dots.")
    ] = None,
    vendor_id: Annotated[
        str | None, typer.Option(help="Override USB vendor ID, for example 0x28e9.")
    ] = None,
    product_id: Annotated[
        str | None, typer.Option(help="Override USB product ID, for example 0x0289.")
    ] = None,
    cut: Annotated[
        bool | None, typer.Option("--cut/--no-cut", help="Override cutter use.")
    ] = None,
) -> None:
    """Render and print a receipt on the configured USB ESC/POS printer."""
    context = _receipt_context(
        title,
        subtitle,
        message,
        status,
        reference,
        footer,
        item,
        template=template,
        questions=questions,
        responses=response,
        seed=seed,
        coordinates=coordinates,
        ra=ra,
        dec=dec,
        depth=depth,
    )
    image, loaded = _render_receipt(
        template=template,
        config_path=config,
        width=width,
        dither=None,
        threshold=None,
        context=context,
    )
    loaded = with_usb_overrides(
        loaded,
        vendor_id=vendor_id,
        product_id=product_id,
        cut=cut,
    )
    destination = f"{loaded.usb.vendor_id:#06x}:{loaded.usb.product_id:#06x}"
    console.print(f"Printing {image.width}×{image.height}px to USB {destination}…")
    try:
        print_usb(image, loaded)
    except Exception as error:
        console.print(f"[red]USB printing failed:[/red] {error}")
        raise typer.Exit(1) from error
    console.print("[green]Print job sent.[/green]")


@app.command("usb-info")
def usb_info() -> None:
    """List attached USB devices and highlight printer-class interfaces."""
    table = Table("VID:PID", "Manufacturer", "Product", "Printer interface")
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
        except Exception:
            pass
        try:
            manufacturer = str(getattr(device, "manufacturer", "") or "")
            product = str(getattr(device, "product", "") or "")
        except Exception:
            manufacturer = "<permission denied>"
            product = "<permission denied>"
        vendor_id = int(getattr(device, "idVendor", 0))
        product_id = int(getattr(device, "idProduct", 0))
        table.add_row(
            f"{vendor_id:04x}:{product_id:04x}",
            manufacturer,
            product,
            "yes" if is_printer else "no",
        )
    console.print(table)
