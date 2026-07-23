from pdv_escpos.config import RenderConfig
from pdv_escpos.imaging import prepare_for_thermal_print
from pdv_escpos.renderer import ReceiptRenderer


def test_demo_template_renders_at_printer_width() -> None:
    config = RenderConfig(width=384)
    image = ReceiptRenderer().render(
        "demo",
        {
            "title": "Test receipt",
            "subtitle": "Playwright smoke test",
            "message": "Rendered from HTML and CSS.",
            "status": "TEST",
            "reference": "T-001",
            "footer": "End",
            "items": ["First item", "Second item"],
        },
        config,
    )
    thermal = prepare_for_thermal_print(image, config)

    assert thermal.width == 384
    assert thermal.height > 300
    assert thermal.mode == "1"
