# `signal-readout` template

A sci-fi landscape waveform readout for synthetic EEG-, ECG-, seismic- and noise-like traces, or complete samples loaded from CSV, JSON, plain text and standard input. Synthetic presets are visual data only and are not medical or scientific measurements.

The HTML is rendered along the paper axis and rotated by 90 degrees. The final bitmap always matches the printer width; turn the receipt sideways to read it.

## Dynamic paper length

The generator calculates the canvas length from the largest channel sample count:

```text
700 px base + 3 px per sample
minimum 900 px
maximum 5000 px
```

For example, 80 points produce a `384×940` bitmap, while 400 points produce `384×1900`. The generated `canvas_length` is selected by `render.canvas_length_from` in `template.yaml`.

## Preview synthetic data

```shell
uv run pdv-escpos signal-readout render \
  --preset ecg \
  --count 320 \
  --minimum=-2.0 \
  --maximum=3.0 \
  --channels 2 \
  --layout separate \
  --sample-rate 250 \
  --seed "ECG-DEMO-001" \
  --units mV \
  --output output/signal-ecg.png
```

Presets:

- `noise` — smoothed random noise;
- `eeg` — mixed oscillations and noise;
- `ecg` — repeating synthetic P/QRS/T-like pulses;
- `seismic` — decaying events over background noise.

`--count`, `--minimum`, `--maximum`, `--channels` and `--preset` apply only when no external source is supplied.

## CSV

CSV files may use commas, semicolons, tabs or pipes. Select columns by header or zero-based index:

```shell
uv run pdv-escpos signal-readout render \
  --source samples.csv \
  --format csv \
  --column lead_i \
  --column lead_ii \
  --sample-rate 250 \
  --units mV \
  --output output/signal-csv.png
```

`--column` is repeatable. Its short form is uppercase `-C`; lowercase `-c` belongs to the common `--config` option. Without `--column`, consistently numeric columns are selected automatically. Up to six channels are accepted.

## JSON

A single channel can be a numeric list:

```json
[0.1, 0.4, -0.2, 0.8]
```

Named channels and an optional layout hint can be represented as:

```json
{
  "layout": "overlay",
  "channels": {
    "north": [0.1, 0.4, -0.2, 0.8],
    "south": [0.8, 0.2, 0.5, -0.1]
  }
}
```

`channels` may also be a list of objects containing `name` and `values`.

## Plain text and STDIN

Text input accepts one decimal value per line. Empty lines and lines beginning with `#` are ignored:

```shell
uv run pdv-escpos signal-readout render \
  --source samples.txt \
  --format text \
  --output output/signal-text.png

cat samples.txt | uv run pdv-escpos signal-readout render \
  --stdin \
  --format text \
  --output output/signal-stdin.png
```

`--source` and `--stdin` cannot be combined. STDIN is read until EOF; continuous acquisition is not implemented.

## Layout and metadata

- `separate` gives every channel an independent band and range;
- `overlay` uses shared axes and distinguishes channels with line weight and dashes;
- `auto` separates multiple channels unless JSON requests overlay.

The readout includes source, format, timestamp, channels, samples, sample rate, duration, global range and mean, plus per-channel minimum, maximum, mean and RMS.

## Font

The module declares `assets/DepartureMono-Regular.otf` in `template.yaml`. Its OpenType format is inferred from the extension and it is embedded under the CSS family `ReceiptPixel`.

## Build and print

```shell
uv run pdv-escpos signal-readout build \
  --preset seismic \
  --count 400 \
  --output output/signal-seismic.bin

uv run pdv-escpos signal-readout print \
  --preset seismic \
  --count 400 \
  --no-cut
```

Always inspect the rotated PNG before sending a long trace to the printer.
