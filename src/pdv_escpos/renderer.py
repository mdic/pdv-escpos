from __future__ import annotations

from base64 import b64encode
from io import BytesIO
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from playwright.sync_api import sync_playwright

from .config import RenderConfig


class ReceiptRenderer:
    def __init__(self, template_root: Path | None = None) -> None:
        self.template_root = template_root or Path(__file__).parent / "templates"
        self.environment = Environment(
            loader=FileSystemLoader(self.template_root),
            autoescape=select_autoescape(("html", "xml", "j2")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_html(
        self,
        template_name: str,
        context: dict[str, Any],
        width: int,
        *,
        html_file: str = "template.html.j2",
        stylesheet_file: str = "style.css",
        font_file: str | None = None,
        font_family: str | None = None,
        font_format: str | None = None,
    ) -> str:
        template_dir = self.template_root / template_name
        if not template_dir.is_dir():
            raise ValueError(f"Unknown template: {template_name}")

        stylesheet = (template_dir / stylesheet_file).read_text(encoding="utf-8")
        if font_file and font_family and font_format:
            font_path = template_dir / font_file
            font_data = b64encode(font_path.read_bytes()).decode("ascii")
            stylesheet = (
                f'@font-face {{ font-family: "{font_family}"; '
                f'src: url("data:font;base64,{font_data}") format("{font_format}"); '
                "font-style: normal; font-weight: 400; font-display: block; }\n"
                + stylesheet
            )
        template = self.environment.get_template(f"{template_name}/{html_file}")
        return template.render(**context, stylesheet=stylesheet, receipt_width=width)

    def html_to_image(self, html: str, width: int) -> Image.Image:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": width, "height": 1000},
                device_scale_factor=1,
                color_scheme="light",
            )
            context.route("http://**/*", lambda route: route.abort())
            context.route("https://**/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            receipt = page.locator("#receipt")
            if receipt.count() != 1:
                browser.close()
                raise ValueError(
                    "Template must contain exactly one element with id='receipt'"
                )
            screenshot = receipt.screenshot(type="png", animations="disabled")
            browser.close()

        image = Image.open(BytesIO(screenshot))
        image.load()
        return image

    def render(
        self,
        template_name: str,
        context: dict[str, Any],
        config: RenderConfig,
        *,
        html_file: str = "template.html.j2",
        stylesheet_file: str = "style.css",
        font_file: str | None = None,
        font_family: str | None = None,
        font_format: str | None = None,
    ) -> Image.Image:
        html = self.render_html(
            template_name,
            context,
            config.width,
            html_file=html_file,
            stylesheet_file=stylesheet_file,
            font_file=font_file,
            font_family=font_family,
            font_format=font_format,
        )
        return self.html_to_image(html, config.width)
