# `demo` template

A small declarative receipt used to verify the HTML/CSS, Playwright, Pillow and ESC/POS pipeline. It has no `generator.py`: values parsed from `template.yaml` are passed directly to Jinja2.

## Preview

```shell
uv run pdv-escpos demo render \
  --title "Thermal dispatch" \
  --subtitle "Local template check" \
  --message "The rendering pipeline is operational." \
  --status READY \
  --reference DEMO-001 \
  --item "First item" \
  --item "Second item" \
  --output output/demo.png
```

## Build and print

```shell
uv run pdv-escpos demo build --output output/demo.bin
uv run pdv-escpos demo print --no-cut
```

Use `uv run pdv-escpos demo render --help` for all content options.
