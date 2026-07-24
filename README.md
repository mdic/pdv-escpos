# pdv-escpos

A Python prototype that renders receipt templates from HTML and CSS with Playwright, converts them to thermal-print bitmaps with Pillow, and sends them to a USB ESC/POS printer with `python-escpos`.

The project is managed entirely by [`uv`](https://docs.astral.sh/uv/). Use `uv add` to change dependencies; do not use `uv pip`.

The modular CLI uses Click directly. Typer 0.26 and later vendors Click and no longer supports Click-specific plug-ins or extracting and extending the underlying Click application; direct Click groups and options are therefore used for commands discovered dynamically from YAML manifests.

## Pipeline

```text
CLI arguments
    → Jinja2 HTML template
    → Playwright / Chromium screenshot
    → Pillow monochrome processing
    → python-escpos
    → USB thermal printer
```

## Detected printer

The development machine currently exposes:

```text
28e9:0289  GDMicroelectronics / YICHIP YC Printer demo
interface  0
OUT        0x01
IN         0x81
```

These values are included in `config.example.yaml`. The printer appears to use a standard USB printer-class interface.

## Set-up

Create the environment and install dependencies from `uv.lock`:

```shell
uv sync
```

Install the Chromium binary used by Playwright:

```shell
uv run playwright install chromium
```

Create the local printer configuration:

```shell
cp config.example.yaml config.yaml
```

`config.yaml` is ignored by Git so each machine can use its own USB IDs, endpoints and print settings.

### Linux USB permissions

If `uv run pdv-escpos usb-info` shows `<permission denied>` for the printer, create `/etc/udev/rules.d/99-pdv-escpos.rules`. The following rule grants access to members of the standard `users` group:

```shell
sudo tee /etc/udev/rules.d/99-pdv-escpos.rules >/dev/null <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="28e9", ATTR{idProduct}=="0289", GROUP:="users", MODE:="0660", TAG+="uaccess"
EOF
```

Confirm that the current user belongs to that group:

```shell
id
```

If the machine uses a different group for local users, replace `users` in the rule with the appropriate group. Reload the rules, then physically disconnect and reconnect the printer so that udev creates a new device node with the updated permissions:

```shell
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Verify access without printing:

```shell
lsusb -d 28e9:0289
uv run pdv-escpos usb-info
```

For the detected printer, `usb-info` should display `YICHIP` and `YC Printer demo` rather than `<permission denied>`. Do not run the application as root merely to work around USB permissions.

## CLI

Show available commands:

```shell
uv run pdv-escpos --help
```

Template modules are discovered automatically from `src/pdv_escpos/templates/`. List them with:

```shell
uv run pdv-escpos templates
```

The modular CLI syntax is:

```text
uv run pdv-escpos MODULE ACTION [OPTIONS]
```

For example:

```shell
uv run pdv-escpos intelligences render --questions 5
```

Options belong to a specific action and must come after `render`, `build` or `print`. This is valid:

```shell
uv run pdv-escpos intelligences render --output output/preview.png
```

This is not valid because `--output` belongs to `render`, not to the `intelligences` group:

```shell
uv run pdv-escpos intelligences --output output/preview.png render
```

Each module exposes the same core actions:

| Action   | `--output` / `-o` | Result                                 | Opens the USB printer |
| -------- | ----------------- | -------------------------------------- | --------------------- |
| `render` | yes               | writes a PNG preview                   | no                    |
| `build`  | yes               | writes a raw ESC/POS `.bin` job        | no                    |
| `print`  | no                | sends the rendered job directly to USB | yes                   |

`templates` and `usb-info` are root utility commands and do not belong to a module. Use module-specific help whenever an option is rejected:

```shell
uv run pdv-escpos intelligences --help
uv run pdv-escpos intelligences render --help
uv run pdv-escpos intelligences build --help
uv run pdv-escpos intelligences print --help
```

### Render a PNG preview

```shell
uv run pdv-escpos demo render \
  --title "Continuity breach" \
  --subtitle "Recovery order" \
  --message "Restore the relay before the next pressure cycle." \
  --status ACTIVE \
  --reference DEMO-042 \
  --item "Enter through service lock C" \
  --item "Replace the continuity bridge" \
  --output output/dispatch.png
```

No printer is accessed by `render`.

### Build a raw ESC/POS job

```shell
uv run pdv-escpos demo build \
  --title "Continuity breach" \
  --item "Enter through service lock C" \
  --output output/dispatch.bin
```

This uses the `python-escpos` Dummy printer and does not open the USB device.

### Print over USB

`print` does not accept `--output`: it sends the generated ESC/POS job directly to the configured USB device. Use `render` first if a PNG preview is required, or `build` if the raw ESC/POS bytes must be saved.

```shell
uv run pdv-escpos demo print \
  --title "Continuity breach" \
  --subtitle "Recovery order" \
  --message "Restore the relay before the next pressure cycle." \
  --status ACTIVE \
  --reference DEMO-042 \
  --item "Enter through service lock C" \
  --item "Replace the continuity bridge"
```

The cutter is disabled by default because the capabilities of the detected printer are not yet known. Enable it in `config.yaml` or pass `--cut` only if the printer has a supported cutter.

USB IDs can be overridden without changing the configuration file:

```shell
uv run pdv-escpos demo print --vendor-id 0x28e9 --product-id 0x0289
```

### Inspect USB devices

```shell
uv run pdv-escpos usb-info
```

## Configuration

`config.yaml` controls:

- printable width in dots;
- monochrome conversion and threshold;
- contrast and brightness;
- USB VID, PID and endpoints;
- `python-escpos` printer profile;
- image implementation (`bitImageRaster`, `graphics` or `bitImageColumn`);
- fragment height and optional fragment delay;
- feed lines and cutter behaviour.

A width of 384 dots is a common starting point for 58 mm printers. It must be adjusted if the printer uses a different printable width.

## Template modules

Every directory inside `src/pdv_escpos/templates/` that contains a valid `template.yaml` is discovered automatically and registered as a CLI group. Adding or removing a module does not require editing the core CLI.

A complete module can contain:

```text
src/pdv_escpos/templates/example/
├── template.yaml
├── generator.py          # optional
├── template.html.j2
├── style.css
└── assets/
    ├── font.ttf          # optional
    └── licence.txt
```

`template.yaml` is required. HTML, stylesheet and generator filenames are declared by the manifest. The generator is optional: a declarative module passes parsed option values directly to Jinja2, while a generated module uses `generator.py` to derive a richer template context. The repository includes `src/pdv_escpos/template.schema.json`; add `# yaml-language-server: $schema=../../template.schema.json` as the first manifest line to enable editor validation from a standard module directory.

A minimal declarative manifest looks like:

```yaml
schema_version: 1
name: message
description: Print a local message.
template: template.html.j2
stylesheet: style.css

options:
  - name: message
    flags: [--message, -m]
    type: string
    required: true
    help: Message to print.
```

The supported option types are `string`, `integer`, `number`, `boolean` and `path`. Option declarations can also use:

- `default`;
- `required`;
- `repeatable`;
- `minimum` and `maximum` for numeric ranges;
- `choices`;
- one or more `flags`;
- `help`.

The names `output`, `config`, `width`, `dither`, `threshold`, `vendor_id`, `product_id` and `cut` are reserved by the core actions and cannot be declared as module options.

For generated modules, declare:

```yaml
generator: generator.py
```

The file must expose:

```python
def build_context(options):
    return {"value_for_jinja": options["input_value"]}
```

`options` contains values already parsed and range-checked from the manifest. `build_context()` may perform cross-field validation and must return a string-keyed mapping for Jinja2.

A module can declare one embedded local font:

```yaml
font:
  file: assets/font.otf
  family: ReceiptPixel
  format: opentype
```

Supported font formats are `truetype`, `opentype` and `woff2`. The renderer embeds the font as a data URL, so printing remains offline.

The root printable element must have `id="receipt"`. Playwright captures that element at a device scale factor of 1, so one CSS pixel corresponds to one printer dot. The renderer also injects `receipt_width` and `stylesheet` into the Jinja2 context.

Remote HTTP and HTTPS requests are blocked during rendering. Keep fonts, images and other assets inside the module. Because `generator.py` is imported and executed as local Python code, only use trusted local modules.

The bundled `demo` module is declarative and receives `title`, `subtitle`, `message`, `status`, `reference`, `footer` and repeatable `items` directly from its manifest options.

### `intelligences`: synthetic constellation readout

The `intelligences` template was created for the art installation _Tracciare Costellazioni di Significato: INTELLIGENZE_. It renders participant responses as a fictional deep-space scientific readout. Its coordinates and measurements are synthetic and must not be interpreted as astronomical data.

Its old-style receipt typography uses the locally bundled Departure Mono pixel typeface. The renderer embeds the font declared by `template.yaml` directly in the generated HTML, so previews and prints remain fully offline and consistent across machines. Departure Mono is distributed under the SIL Open Font License 1.1; the licence text is stored in `src/pdv_escpos/templates/intelligences/assets/LICENSE`.

The template prints:

- an observation and catalogue identifier;
- a timestamp and question count;
- synthetic interpretative coordinates;
- exactly one response-spectrum row per question;
- derived resonance, coherence and semantic-magnitude values;
- a generated ASCII constellation plot.

Generate five fictional readings and a PNG preview:

```shell
uv run pdv-escpos intelligences render \
  --questions 5 \
  --seed "SESSION-004271" \
  --output output/intelligences-004271.png
```

Without `--response`, the generator creates one value for each question. If `--questions` is omitted as well, it defaults to five readings. The seed determines the observation ID, coordinates, metrics, values and constellation, making those generated data reproducible; the printed timestamp records the current rendering time.

Pass actual response values by repeating `--response`:

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

Response values must be between `0` and `100`. When responses are supplied, the question count is inferred from their number. `--questions` may also be supplied, but it must match the number of `--response` options.

Coordinates are normally generated from the seed. Override all three coordinate fields with one slash-separated value:

```shell
uv run pdv-escpos intelligences render \
  --questions 5 \
  --coordinates "17H 42M 11.8S / +28D 09M 44S / Z+017.62" \
  --output output/intelligences-coordinates.png
```

Alternatively, override individual fields:

```shell
uv run pdv-escpos intelligences render \
  --questions 5 \
  --ra "17H 42M 11.8S" \
  --dec "+28D 09M 44S" \
  --depth "Z+017.62"
```

Do not combine `--coordinates` with `--ra`, `--dec` or `--depth`. The synthetic signal origin remains generator-controlled so that the catalogue ID stays linked to the observation seed.

Build an offline ESC/POS job without opening the USB device:

```shell
uv run pdv-escpos intelligences build \
  --questions 5 \
  --seed "SESSION-004271" \
  --output output/intelligences-004271.bin
```

Print directly to the configured USB printer, with the cutter explicitly disabled:

```shell
uv run pdv-escpos intelligences print \
  --response 72 \
  --response 41 \
  --response 88 \
  --response 63 \
  --response 29 \
  --seed "SESSION-004271" \
  --no-cut
```

The module options are declared in `src/pdv_escpos/templates/intelligences/template.yaml`. Its content generator is implemented next to the Jinja2 template in `src/pdv_escpos/templates/intelligences/generator.py`, keeping response processing and deterministic data generation independent from the printable HTML/CSS presentation.

#### How the ASCII constellation changes

The constellation is deterministic rather than independently random. Its geometry is calculated in `_constellation()` inside `src/pdv_escpos/templates/intelligences/generator.py`:

- each response produces one node;
- the response value determines its horizontal position;
- the response index and value determine its vertical position;
- consecutive nodes are joined with `.` characters;
- nodes use `*`, while the final node uses `+`.

Consequently, the same ordered response values always produce the same constellation, even if `--seed` changes. Different response values or a different response order produce a different shape.

When only `--questions` is supplied, values are generated from the seed. A fixed seed therefore reproduces the same values and constellation. Without an explicit seed, the current timestamp is used as the seed, so each invocation normally generates a different set of values and a different constellation.

#### Editing the `intelligences` template manually

The printable structure is in:

```text
src/pdv_escpos/templates/intelligences/template.html.j2
```

Its presentation is in:

```text
src/pdv_escpos/templates/intelligences/style.css
```

The `.j2` file is ordinary HTML with Jinja2 expressions:

- `{{ value }}` prints a generated value;
- `{% for item in items %}` and `{% endfor %}` repeat a block;
- fixed text can be edited directly as normal HTML.

The template is divided into independent blocks:

1. `<header>` — installation name and instrument label;
2. `<section class="metadata ruled">` — observation ID, timestamp and question count;
3. the section headed `INTERPRETATIVE COORDINATES`;
4. the section headed `RESPONSE SPECTRUM`;
5. the section headed `CONSTELLATION ANALYSIS`;
6. `<footer>` — catalogue ID, status and disclaimer.

To remove a complete section, delete its opening `<section ...>` tag, everything inside it, and its closing `</section>` tag. For example, removing the interpretative-coordinate section does not require any Python changes: the generator may continue to calculate coordinates, but unused values are simply not rendered.

The constellation analysis section contains two parts. Delete only the `<dl class="values"> ... </dl>` block to hide the numerical analysis while retaining the star map. Delete only the `<figure class="star-map"> ... </figure>` block to hide the map while retaining the numerical analysis.

The response spectrum contains a Jinja2 loop. If removing it, delete the entire section, including both `{% for reading in readings %}` and `{% endfor %}`. Leaving only one of those tags will make template rendering fail.

The footer can be shortened by removing individual elements such as:

```html
<p class="disclaimer">SYNTHETIC COORDINATES / NON-ASTRONOMICAL DATA</p>
```

Keep these structural elements in the document:

- `<style>{{ stylesheet | safe }}</style>`, which injects the local CSS and embedded font;
- one and only one element with `id="receipt"`, which Playwright uses as the screenshot boundary;
- balanced HTML and Jinja2 opening and closing tags.

Use `style.css` to change sizes and spacing without changing content. Important selectors include:

- `.receipt` — base type size, line height and outer padding;
- `h1` — the `INTELLIGENZE` title;
- `h2` — black section headings;
- `.readings li` and `.signal` — response rows;
- `.sky` and `.sky pre` — constellation frame and character size;
- `footer` and `.catalogue` — final metadata.

The bundled Departure Mono typeface is loaded from `src/pdv_escpos/templates/intelligences/assets/DepartureMono.ttf`, as declared in `template.yaml`. Keep that file and the matching `font` manifest block in place to preserve the old-style pixel receipt appearance.

After every manual change, render a preview before printing:

```shell
uv run pdv-escpos intelligences render \
  --response 72 \
  --response 41 \
  --response 88 \
  --seed "LAYOUT-CHECK" \
  --output output/intelligences-layout-check.png
```

No rebuild or application restart is required: HTML and CSS files are read again for every command. Once the PNG looks correct, replace the `render` command with `print`, remove `--output` and its path, and keep `--no-cut` unless cutter support has been verified. `print` does not create a PNG or binary output file.

## Testing

Run the test suite with:

```shell
uv run pytest
```

The tests render a real Chromium screenshot and build a raw ESC/POS job with the Dummy printer. They never open the physical USB printer.
