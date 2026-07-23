from PIL import Image

from pdv_escpos.config import RenderConfig
from pdv_escpos.imaging import prepare_for_thermal_print


def test_threshold_output_is_monochrome_and_resized() -> None:
    source = Image.new("RGB", (200, 100), "grey")
    output = prepare_for_thermal_print(
        source,
        RenderConfig(width=384, dither="threshold", threshold=160),
    )

    assert output.mode == "1"
    assert output.size == (384, 192)
