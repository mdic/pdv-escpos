from PIL import Image

from pdv_escpos.config import AppConfig
from pdv_escpos.printer import build_escpos_job


def test_dummy_printer_builds_binary_job() -> None:
    image = Image.new("1", (384, 32), 1)

    job = build_escpos_job(image, AppConfig())

    assert isinstance(job, bytes)
    assert len(job) > 0
