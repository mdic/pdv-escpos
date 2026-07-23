from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast

import yaml

DitherMode = Literal["threshold", "floyd-steinberg", "none"]
ImageImplementation = Literal["bitImageRaster", "graphics", "bitImageColumn"]
CutMode = Literal["FULL", "PART"]


@dataclass(frozen=True)
class RenderConfig:
    width: int = 384
    dither: DitherMode = "threshold"
    threshold: int = 160
    contrast: float = 1.15
    brightness: float = 1.0


@dataclass(frozen=True)
class UsbConfig:
    vendor_id: int = 0x28E9
    product_id: int = 0x0289
    in_endpoint: int = 0x81
    out_endpoint: int = 0x01
    timeout: int = 0
    profile: str = "default"


@dataclass(frozen=True)
class PrintConfig:
    image_impl: ImageImplementation = "bitImageRaster"
    fragment_height: int = 960
    fragment_sleep_ms: int = 0
    feed_lines: int = 4
    cut: bool = False
    cut_mode: CutMode = "FULL"


@dataclass(frozen=True)
class AppConfig:
    render: RenderConfig = RenderConfig()
    usb: UsbConfig = UsbConfig()
    printing: PrintConfig = PrintConfig()


def _integer(value: Any, field: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as error:
            raise ValueError(
                f"{field} must be an integer or a hexadecimal value"
            ) from error
    raise ValueError(f"{field} must be an integer or a hexadecimal value")


def load_config(path: Path | None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("The configuration root must be a mapping")

    render_data = raw.get("render", {}) or {}
    usb_data = raw.get("usb", {}) or {}
    print_data = raw.get("printing", {}) or {}

    config = AppConfig(
        render=RenderConfig(
            width=_integer(render_data.get("width", 384), "render.width"),
            dither=cast(DitherMode, render_data.get("dither", "threshold")),
            threshold=_integer(render_data.get("threshold", 160), "render.threshold"),
            contrast=float(render_data.get("contrast", 1.15)),
            brightness=float(render_data.get("brightness", 1.0)),
        ),
        usb=UsbConfig(
            vendor_id=_integer(usb_data.get("vendor_id", 0x28E9), "usb.vendor_id"),
            product_id=_integer(usb_data.get("product_id", 0x0289), "usb.product_id"),
            in_endpoint=_integer(usb_data.get("in_endpoint", 0x81), "usb.in_endpoint"),
            out_endpoint=_integer(
                usb_data.get("out_endpoint", 0x01), "usb.out_endpoint"
            ),
            timeout=_integer(usb_data.get("timeout", 0), "usb.timeout"),
            profile=str(usb_data.get("profile", "default")),
        ),
        printing=PrintConfig(
            image_impl=cast(
                ImageImplementation,
                print_data.get("image_impl", "bitImageRaster"),
            ),
            fragment_height=_integer(
                print_data.get("fragment_height", 960), "printing.fragment_height"
            ),
            fragment_sleep_ms=_integer(
                print_data.get("fragment_sleep_ms", 0), "printing.fragment_sleep_ms"
            ),
            feed_lines=_integer(print_data.get("feed_lines", 4), "printing.feed_lines"),
            cut=bool(print_data.get("cut", False)),
            cut_mode=cast(
                CutMode,
                str(print_data.get("cut_mode", "FULL")).upper(),
            ),
        ),
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    if config.render.width < 64:
        raise ValueError("render.width must be at least 64 pixels")
    if config.render.dither not in {"threshold", "floyd-steinberg", "none"}:
        raise ValueError("render.dither must be threshold, floyd-steinberg or none")
    if not 0 <= config.render.threshold <= 255:
        raise ValueError("render.threshold must be between 0 and 255")
    if config.render.contrast <= 0 or config.render.brightness <= 0:
        raise ValueError("render contrast and brightness must be positive")
    if config.printing.image_impl not in {
        "bitImageRaster",
        "graphics",
        "bitImageColumn",
    }:
        raise ValueError("printing.image_impl is not supported")
    if config.printing.fragment_height < 1:
        raise ValueError("printing.fragment_height must be positive")
    if config.printing.fragment_sleep_ms < 0 or config.printing.feed_lines < 0:
        raise ValueError("fragment sleep and feed lines cannot be negative")
    if config.printing.cut_mode not in {"FULL", "PART"}:
        raise ValueError("printing.cut_mode must be FULL or PART")


def with_render_overrides(
    config: AppConfig,
    *,
    width: int | None = None,
    dither: DitherMode | None = None,
    threshold: int | None = None,
) -> AppConfig:
    render = replace(
        config.render,
        width=width if width is not None else config.render.width,
        dither=dither if dither is not None else config.render.dither,
        threshold=threshold if threshold is not None else config.render.threshold,
    )
    updated = replace(config, render=render)
    validate_config(updated)
    return updated


def with_usb_overrides(
    config: AppConfig,
    *,
    vendor_id: str | None = None,
    product_id: str | None = None,
    cut: bool | None = None,
) -> AppConfig:
    usb = replace(
        config.usb,
        vendor_id=_integer(vendor_id, "vendor_id")
        if vendor_id
        else config.usb.vendor_id,
        product_id=_integer(product_id, "product_id")
        if product_id
        else config.usb.product_id,
    )
    printing = replace(
        config.printing, cut=cut if cut is not None else config.printing.cut
    )
    updated = replace(config, usb=usb, printing=printing)
    validate_config(updated)
    return updated
