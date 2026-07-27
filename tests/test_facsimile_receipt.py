from pathlib import Path

from pdv_escpos.cli import TEMPLATE_ROOT
from pdv_escpos.config import RenderConfig
from pdv_escpos.imaging import prepare_for_thermal_print
from pdv_escpos.renderer import ReceiptRenderer
from pdv_escpos.template_module import load_template_module

TEMPLATE_DIR = TEMPLATE_ROOT / "facsimile-receipt"
MODULE = load_template_module(TEMPLATE_DIR)


def receipt_context(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        option.name: []
        if option.repeatable and option.default is None
        else option.default
        for option in MODULE.options
    }
    values.update(overrides)
    return MODULE.build_context(values)


def test_inline_items_calculate_totals_tax_and_change() -> None:
    context = receipt_context(
        item=["Coffee|2|1.40|10", "Notebook|1|6.90|22"],
        paid=20,
        seed="TOTALS",
    )

    assert context["item_count"] == 2
    assert context["total"] == "9,70 €"
    assert context["paid"] == "20,00 €"
    assert context["change"] == "10,30 €"
    assert context["has_change"] is True
    assert len(context["taxes"]) == 2  # type: ignore[arg-type]


def test_json_items_and_custom_svg_logo_are_embedded(tmp_path: Path) -> None:
    items = tmp_path / "items.json"
    items.write_text(
        '{"items":[{"description":"Cable","quantity":2,"unit_price":3.5,"tax_rate":22}]}',
        encoding="utf-8",
    )
    logo = tmp_path / "logo.svg"
    logo.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
        encoding="utf-8",
    )

    context = receipt_context(items_file=items, logo=logo, seed="JSON")

    assert context["item_count"] == 1
    assert context["total"] == "7,00 €"
    assert str(context["logo_data"]).startswith("data:image/svg+xml;base64,")
    assert context["logo_name"] == "logo.svg"


def test_csv_items_can_be_combined_with_cli_items(tmp_path: Path) -> None:
    items = tmp_path / "items.csv"
    items.write_text(
        "description,quantity,unit_price,tax_rate\nAdapter,1,12.50,22\n",
        encoding="utf-8",
    )

    context = receipt_context(
        item=["Coffee|1|1.40|10"],
        items_file=items,
        seed="CSV",
    )

    assert context["item_count"] == 2
    assert context["total"] == "13,90 €"


def test_template_contains_permanent_non_fiscal_markers() -> None:
    config = RenderConfig(width=384)
    context = receipt_context(item=["Demo|1|1.00|22"], seed="MARKER")
    html = ReceiptRenderer(MODULE.directory.parent).render_html(
        MODULE.directory.name,
        context,
        config.width,
        html_file=MODULE.html_file,
        stylesheet_file=MODULE.stylesheet_file,
        fonts=MODULE.fonts,
    )

    assert "FACSIMILE · NON FISCALE · PRIVO DI VALIDITÀ" in html
    assert "DOCUMENTO SCENICO · NON UTILIZZABILE A FINI FISCALI" in html


def test_facsimile_receipt_renders_at_printer_width() -> None:
    config = RenderConfig(width=384)
    context = receipt_context(
        item=[
            "Synthetic coffee|2|1.40|10",
            "Orbital notebook|1|6.90|22",
            "Signal adapter|1|12.50|22",
        ],
        seed="RENDER",
    )
    image = ReceiptRenderer(MODULE.directory.parent).render(
        MODULE.directory.name,
        context,
        config,
        html_file=MODULE.html_file,
        stylesheet_file=MODULE.stylesheet_file,
        fonts=MODULE.fonts,
    )
    thermal = prepare_for_thermal_print(image, config)

    assert thermal.width == 384
    assert thermal.height > 900
    assert thermal.mode == "1"
