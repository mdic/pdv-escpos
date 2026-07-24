# `testing` template

A local generated template used for experimentation. Its `--message` option is declared in `template.yaml` and processed by `generator.py` before rendering.

## Preview

```shell
uv run pdv-escpos testing render \
  --message "Local testing receipt" \
  --output output/testing.png
```

## Build and print

```shell
uv run pdv-escpos testing build --message "Local testing receipt" --output output/testing.bin
uv run pdv-escpos testing print --message "Local testing receipt" --no-cut
```
