# pdv-escpos

A Python prototype that renders receipt templates from HTML and CSS with Playwright, converts them to thermal-print bitmaps with Pillow, and sends them to a USB ESC/POS printer with `python-escpos`.

The project is managed entirely by [`uv`](https://docs.astral.sh/uv/). Use `uv add` to change dependencies; do not use `uv pip`.

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

### Render a PNG preview

```shell
uv run pdv-escpos render \
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
uv run pdv-escpos build \
  --title "Continuity breach" \
  --item "Enter through service lock C" \
  --output output/dispatch.bin
```

This uses the `python-escpos` Dummy printer and does not open the USB device.

### Print over USB

```shell
uv run pdv-escpos print \
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
uv run pdv-escpos print --vendor-id 0x28e9 --product-id 0x0289
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

## Templates

Templates live inside `src/pdv_escpos/templates/`. Each template directory contains:

```text
template.html.j2
style.css
```

The root printable element must have `id="receipt"`. Playwright captures that element at a device scale factor of 1, so one CSS pixel corresponds to one printer dot.

Template variables are escaped by Jinja2. The bundled demo template receives:

- `title`;
- `subtitle`;
- `message`;
- `status`;
- `reference`;
- `footer`;
- repeatable `items`;
- `receipt_width`.

Remote HTTP and HTTPS requests are blocked during rendering. Keep fonts, images and other assets local or embed them as data URLs.

### `intelligences`: synthetic constellation readout

The `intelligences` template was created for the art installation _Tracciare Costellazioni di Significato: INTELLIGENZE_. It renders participant responses as a fictional deep-space scientific readout. Its coordinates and measurements are synthetic and must not be interpreted as astronomical data.

The template prints:

- an observation and catalogue identifier;
- a timestamp and question count;
- synthetic interpretative coordinates;
- exactly one response-spectrum row per question;
- derived resonance, coherence and semantic-magnitude values;
- a generated ASCII constellation plot.

Generate five fictional readings and a PNG preview:

```shell
uv run pdv-escpos render \
  --template intelligences \
  --questions 5 \
  --seed "SESSION-004271" \
  --output output/intelligences-004271.png
```

Without `--response`, the generator creates one value for each question. If `--questions` is omitted as well, it defaults to five readings. The seed determines the observation ID, coordinates, metrics, values and constellation, making those generated data reproducible; the printed timestamp records the current rendering time.

Pass actual response values by repeating `--response`:

```shell
uv run pdv-escpos render \
  --template intelligences \
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
uv run pdv-escpos render \
  --template intelligences \
  --questions 5 \
  --coordinates "17H 42M 11.8S / +28D 09M 44S / Z+017.62" \
  --output output/intelligences-coordinates.png
```

Alternatively, override individual fields:

```shell
uv run pdv-escpos render \
  --template intelligences \
  --questions 5 \
  --ra "17H 42M 11.8S" \
  --dec "+28D 09M 44S" \
  --depth "Z+017.62"
```

Do not combine `--coordinates` with `--ra`, `--dec` or `--depth`. The synthetic signal origin remains generator-controlled so that the catalogue ID stays linked to the observation seed.

Build an offline ESC/POS job without opening the USB device:

```shell
uv run pdv-escpos build \
  --template intelligences \
  --questions 5 \
  --seed "SESSION-004271" \
  --output output/intelligences-004271.bin
```

Print directly to the configured USB printer, with the cutter explicitly disabled:

```shell
uv run pdv-escpos print \
  --template intelligences \
  --response 72 \
  --response 41 \
  --response 88 \
  --response 63 \
  --response 29 \
  --seed "SESSION-004271" \
  --no-cut
```

The content generator is implemented separately from the Jinja2 template in `src/pdv_escpos/intelligences.py`. This keeps response processing and deterministic data generation independent from the printable HTML/CSS presentation.

## Testing

Run the test suite with:

```shell
uv run pytest
```

The tests render a real Chromium screenshot and build a raw ESC/POS job with the Dummy printer. They never open the physical USB printer.
