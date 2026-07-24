# `intelligences` template

Created for the art installation *Tracciare Costellazioni di Significato: INTELLIGENZE*. It renders participant responses as a fictional deep-space scientific readout. Coordinates and measurements are synthetic and must not be interpreted as astronomical data.

The module prints an observation ID, timestamp, question count, synthetic coordinates, one spectrum row per response, derived analysis and an ASCII constellation.

## Preview generated readings

```shell
uv run pdv-escpos intelligences render \
  --questions 5 \
  --seed "SESSION-004271" \
  --output output/intelligences-004271.png
```

Without `--response`, the generator creates one value per question. If `--questions` is omitted, it defaults to five. A fixed seed reproduces IDs, coordinates, metrics, values and constellation; the timestamp records the current rendering time.

## Use response values

```shell
uv run pdv-escpos intelligences render \
  --response 72 \
  --response 41 \
  --response 88 \
  --response 63 \
  --response 29 \
  --seed "SESSION-004271" \
  --output output/intelligences-responses.png
```

Values must be between `0` and `100`. When responses are supplied, their number determines the question count. If `--questions` is also supplied, both counts must match.

## Override coordinates

```shell
uv run pdv-escpos intelligences render \
  --questions 5 \
  --coordinates "17H 42M 11.8S / +28D 09M 44S / Z+017.62" \
  --output output/intelligences-coordinates.png
```

Or override fields individually with `--ra`, `--dec` and `--depth`. Do not combine individual fields with `--coordinates`.

## Build and print

```shell
uv run pdv-escpos intelligences build \
  --questions 5 \
  --seed "SESSION-004271" \
  --output output/intelligences-004271.bin

uv run pdv-escpos intelligences print \
  --response 72 \
  --response 41 \
  --response 88 \
  --seed "SESSION-004271" \
  --no-cut
```

## Constellation behaviour

The constellation is deterministic:

- each response creates one node;
- value determines horizontal position;
- response index and value determine vertical position;
- consecutive nodes are connected with `.`;
- nodes use `*`, and the final node uses `+`.

The same ordered response values produce the same constellation, even with a different seed. Different values or order produce a different shape. When values are generated, a fixed seed reproduces the constellation.

## Font

`template.yaml` declares `assets/DepartureMono-Regular.otf` under `fonts`. The core infers `opentype` from `.otf`, embeds it as a data URL and exposes it as `ReceiptPixel`. The font is licensed under the SIL Open Font License; its licence is stored beside the asset.

To use another font, replace or extend the `fonts` list and update `style.css` to reference its `family`.

## Editing sections

The independent blocks in `template.html.j2` are:

1. `<header>`;
2. metadata;
3. `INTERPRETATIVE COORDINATES`;
4. `RESPONSE SPECTRUM`;
5. `CONSTELLATION ANALYSIS`;
6. `<footer>`.

Delete an entire `<section>...</section>` to omit it. Within analysis, remove only `<dl class="values">` to keep the star map, or remove only `<figure class="star-map">` to keep numerical analysis. If removing the response spectrum, remove both `{% for reading in readings %}` and `{% endfor %}`.

Always preserve `<style>{{ stylesheet | safe }}</style>`, balanced Jinja2 tags and exactly one element with `id="receipt"`.

Preview every manual change before printing:

```shell
uv run pdv-escpos intelligences render \
  --response 72 \
  --response 41 \
  --response 88 \
  --seed "LAYOUT-CHECK" \
  --output output/intelligences-layout-check.png
```
