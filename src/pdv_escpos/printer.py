from __future__ import annotations

from escpos.printer import Dummy, Usb
from PIL import Image

from .config import AppConfig


def build_escpos_job(image: Image.Image, config: AppConfig) -> bytes:
    printer = Dummy(profile=config.usb.profile)
    printer.image(
        image,
        impl=config.printing.image_impl,
        fragment_height=config.printing.fragment_height,
        center=False,
    )
    if config.printing.feed_lines:
        printer.ln(config.printing.feed_lines)
    if config.printing.cut:
        printer.cut(mode=config.printing.cut_mode, feed=False)
    return printer.output


def print_usb(image: Image.Image, config: AppConfig) -> None:
    printer = Usb(
        config.usb.vendor_id,
        config.usb.product_id,
        timeout=config.usb.timeout,
        in_ep=config.usb.in_endpoint,
        out_ep=config.usb.out_endpoint,
        profile=config.usb.profile,
    )
    try:
        sleep_in_fragment = getattr(printer, "set_sleep_in_fragment", None)
        if config.printing.fragment_sleep_ms and callable(sleep_in_fragment):
            _ = sleep_in_fragment(config.printing.fragment_sleep_ms)
        printer.image(
            image,
            impl=config.printing.image_impl,
            fragment_height=config.printing.fragment_height,
            center=False,
        )
        if config.printing.feed_lines:
            printer.ln(config.printing.feed_lines)
        if config.printing.cut:
            printer.cut(mode=config.printing.cut_mode, feed=False)
    finally:
        printer.close()
