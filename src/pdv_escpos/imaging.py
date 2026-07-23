from __future__ import annotations

from PIL import Image, ImageEnhance

from .config import RenderConfig


def prepare_for_thermal_print(image: Image.Image, config: RenderConfig) -> Image.Image:
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, "white")
    white.alpha_composite(rgba)
    rgb = white.convert("RGB")

    if rgb.width != config.width:
        height = round(rgb.height * config.width / rgb.width)
        rgb = rgb.resize((config.width, height), Image.Resampling.LANCZOS)

    grey = rgb.convert("L")
    grey = ImageEnhance.Contrast(grey).enhance(config.contrast)
    grey = ImageEnhance.Brightness(grey).enhance(config.brightness)

    if config.dither == "none":
        return grey
    if config.dither == "floyd-steinberg":
        return grey.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    threshold_table = [0 if value < config.threshold else 255 for value in range(256)]
    return grey.point(threshold_table, mode="1")
