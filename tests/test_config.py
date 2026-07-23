from pathlib import Path

from pdv_escpos.config import load_config, with_render_overrides


def test_load_hexadecimal_usb_ids(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
render:
  width: 576
usb:
  vendor_id: 0x28e9
  product_id: 0x0289
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.render.width == 576
    assert config.usb.vendor_id == 0x28E9
    assert config.usb.product_id == 0x0289


def test_cli_render_overrides_are_applied() -> None:
    config = with_render_overrides(load_config(None), width=512, threshold=180)

    assert config.render.width == 512
    assert config.render.threshold == 180
