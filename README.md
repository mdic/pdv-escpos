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

`template.yaml` is required. HTML, stylesheet and generator filenames are declared by the manifest. The generator is optional: a declarative module passes parsed option values directly to Jinja2, while a generated module uses `generator.py` to derive a richer template context. The repository includes `src/pdv_escpos/template-module-v1.schema.json`; add `# yaml-language-server: $schema=../../template-module-v1.schema.json` as the first manifest line to enable editor validation from a standard module directory.

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

A module is portrait by default. To render along the paper axis and rotate into a printer-ready bitmap, declare a fixed landscape length:

```yaml
render:
  orientation: landscape
  canvas_length: 1200
```

A generator can instead control paper length by returning an integer context value:

```yaml
render:
  orientation: landscape
  canvas_length: 1200
  canvas_length_from: canvas_length
```

`canvas_length` is the fallback. When the generator returns `canvas_length`, that value is used for the current job. A landscape template must make `#receipt` exactly `receipt_width` pixels high and use `canvas_width` for its width.

Declare one or more local fonts with `fonts`:

```yaml
fonts:
  - file: assets/Regular.otf
    family: ReceiptText
  - file: assets/Bold.woff2
    family: ReceiptText
    weight: 700
```

The format is inferred from `.ttf`, `.otf`, `.woff` or `.woff2`. An explicit `format` is only needed for an unknown extension. `family` defaults to the filename stem; `weight` defaults to `400` and `style` to `normal`. The legacy singular `font` block remains supported. Every declared font is embedded as a data URL, so rendering remains offline.

The root printable element must have `id="receipt"`. Playwright captures that element at a device scale factor of 1, so one CSS pixel corresponds to one printer dot. The renderer also injects `receipt_width` and `stylesheet` into the Jinja2 context.

Remote HTTP and HTTPS requests are blocked during rendering. Keep fonts, images and other assets inside the module. Because `generator.py` is imported and executed as local Python code, only use trusted local modules.

The bundled `demo` module is declarative and receives `title`, `subtitle`, `message`, `status`, `reference`, `footer` and repeatable `items` directly from its manifest options.

### Practical guide: create a new module

#### 1. Generate the skeleton

Choose a lowercase name containing letters, numbers and hyphens, then run:

```shell
uv run pdv-escpos new event-note \
  --description "Print a short note for a local event."
```

The command creates:

```text
src/pdv_escpos/templates/event-note/
├── README.md
├── template.yaml
├── template.html.j2
├── style.css
└── assets/
    └── README.md
```

It never overwrites an existing directory. `new`, `templates` and `usb-info` are reserved module names.

The new module is discovered on the next CLI invocation. Confirm it with:

```shell
uv run pdv-escpos templates
uv run pdv-escpos event-note render --help
```

The generated skeleton already accepts `--message` and can be rendered immediately:

```shell
uv run pdv-escpos event-note render \
  --message "First local template" \
  --output output/event-note.png
```

#### 2. Configure content options in `template.yaml`

Edit `src/pdv_escpos/templates/event-note/template.yaml`. For example, replace or extend the generated `options` list:

```yaml
options:
  - name: participant
    flags: [--participant, -p]
    type: string
    required: true
    help: Name or identifier printed on the receipt.

  - name: score
    flags: [--score]
    type: integer
    minimum: 0
    maximum: 100
    default: 50
    help: Numeric score from 0 to 100.

  - name: tag
    flags: [--tag]
    type: string
    repeatable: true
    help: Optional tag. Repeat for multiple tags.
```

The most useful option fields are:

| Field                 | Purpose                                     | Example                                          |
| --------------------- | ------------------------------------------- | ------------------------------------------------ |
| `name`                | Python/Jinja2 variable name in `snake_case` | `participant_id`                                 |
| `flags`               | CLI spellings                               | `[--participant, -p]`                            |
| `type`                | Parsed value type                           | `string`, `integer`, `number`, `boolean`, `path` |
| `help`                | Text shown by `--help`                      | `Participant identifier.`                        |
| `default`             | Value used when omitted                     | `50`                                             |
| `required`            | Reject the command when omitted             | `true`                                           |
| `repeatable`          | Allow the flag more than once               | `true`                                           |
| `minimum` / `maximum` | Numeric bounds                              | `0` / `100`                                      |
| `choices`             | Restrict accepted values                    | `[low, medium, high]`                            |

After saving the manifest, inspect the generated interface rather than guessing its options:

```shell
uv run pdv-escpos event-note render --help
```

#### 3. Use the options in HTML

A declarative module passes each parsed option directly to Jinja2. In `template.html.j2`, use the option names as variables:

```jinja2
<h1>{{ participant }}</h1>
<p>SCORE: {{ score }}</p>

{% if tag %}
<ul>
  {% for value in tag %}
  <li>{{ value }}</li>
  {% endfor %}
</ul>
{% endif %}
```

Keep exactly one printable root element:

```html
<article id="receipt" class="receipt">
  ...
</article>
```

Keep `<style>{{ stylesheet | safe }}</style>` in the document head. The renderer supplies `receipt_width` automatically, so it can also be used in the viewport declaration or template body.

#### 4. Edit the appearance

Use `style.css` for typography, spacing, borders and receipt layout. The printable width is fixed by the render configuration, normally `384` dots for the current printer. Prefer monochrome, high-contrast styling and avoid large solid black areas.

Put local images, fonts and their licence files in `assets/`. To use a font, add a manifest block matching its actual format:

```yaml
fonts:
  - file: assets/MyFont.otf
    family: ReceiptPixel
```

Then reference the declared family in CSS:

```css
body {
  font-family: "ReceiptPixel", monospace;
}
```

The format is detected automatically from the extension. The renderer embeds every declared font; no network request is made.

#### 5. Add a generator when YAML and Jinja2 are not enough

Create a generated skeleton with:

```shell
uv run pdv-escpos new survey-result \
  --description "Generate a derived survey receipt." \
  --with-generator
```

This adds `generator.py` and declares it in the manifest:

```yaml
generator: generator.py
```

The generated hook receives all module options after Click has parsed their basic types and ranges:

```python
def build_context(options):
    return {
        "display_value": options["input_value"],
        "derived_value": "calculate it here",
    }
```

The returned keys, not the original option names, become the Jinja2 variables. Use a generator for derived values, random or seeded content, cross-option validation, lookups and structures such as lists of rows. Raise `ValueError` with a clear message for invalid option combinations; the CLI will display it as a normal command error.

A generator is optional. Do not add one when the template only needs to print values exactly as supplied by the operator.

#### 6. Preview, build and print

Always start with a PNG preview:

```shell
uv run pdv-escpos event-note render \
  --participant "P-0042" \
  --score 72 \
  --tag alpha \
  --tag archive \
  --output output/event-note.png
```

Build raw ESC/POS bytes without opening the printer:

```shell
uv run pdv-escpos event-note build \
  --participant "P-0042" \
  --score 72 \
  --output output/event-note.bin
```

Print only after the preview is correct:

```shell
uv run pdv-escpos event-note print \
  --participant "P-0042" \
  --score 72 \
  --no-cut
```

`--output` belongs only to `render` and `build`; remove it when changing an example to `print`.

#### Manual creation without the bootstrap command

You can create a module manually by adding a directory containing at least:

```text
template.yaml
style.css
template.html.j2
```

Copy the YAML language-server comment from another module, ensure `schema_version: 1` is present, and run `uv run pdv-escpos templates`. If discovery fails, check that all files declared in the manifest exist and that module and option names do not conflict with reserved core names.

### Bundled template documentation

Each bundled module keeps its operating instructions beside its manifest, generator and assets:

- [`demo`](src/pdv_escpos/templates/demo/README.md)
- [`facsimile-receipt`](src/pdv_escpos/templates/facsimile-receipt/README.md)
- [`intelligences`](src/pdv_escpos/templates/intelligences/README.md)
- [`signal-readout`](src/pdv_escpos/templates/signal-readout/README.md)
- [`testing`](src/pdv_escpos/templates/testing/README.md)

Keep module-specific commands, input formats and editing notes in that module README rather than in this general project README.

## Testing

Run the test suite with:

```shell
uv run pytest
```

The tests render a real Chromium screenshot and build a raw ESC/POS job with the Dummy printer. They never open the physical USB printer.
