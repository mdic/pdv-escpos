from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import statistics
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

PLOT_HEIGHT = 220
MIN_CANVAS_LENGTH = 900
MAX_CANVAS_LENGTH = 5000
BASE_CANVAS_LENGTH = 700
PIXELS_PER_SAMPLE = 3
MAX_CHANNELS = 6
MAX_PLOTTED_SAMPLES = 2000


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _detect_format(raw: str, source: Path | None, requested: str) -> str:
    if requested != "auto":
        return requested
    if source is not None:
        extension = source.suffix.lower()
        if extension == ".csv":
            return "csv"
        if extension == ".json":
            return "json"
        if extension in {".txt", ".dat"}:
            return "text"
    stripped = raw.lstrip()
    if stripped.startswith(("[", "{")):
        return "json"
    first_data_line = next(
        (
            line
            for line in raw.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ),
        "",
    )
    return "csv" if "," in first_data_line or ";" in first_data_line else "text"


def _validate_channels(
    channels: Sequence[tuple[str, Sequence[float]]],
) -> list[tuple[str, list[float]]]:
    if not channels:
        raise ValueError("the data source does not contain numeric channels")
    if len(channels) > MAX_CHANNELS:
        raise ValueError(f"at most {MAX_CHANNELS} channels can be plotted")
    validated: list[tuple[str, list[float]]] = []
    for name, values in channels:
        numeric = [float(value) for value in values]
        if not numeric:
            raise ValueError(f"channel {name} is empty")
        if any(not math.isfinite(value) for value in numeric):
            raise ValueError(f"channel {name} contains a non-finite value")
        validated.append((name, numeric))
    return validated


def _csv_channels(
    raw: str, requested_columns: Sequence[str]
) -> list[tuple[str, list[float]]]:
    sample = raw[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(raw), dialect=dialect))
    rows = [row for row in rows if row and any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("CSV input is empty")
    try:
        has_header = csv.Sniffer().has_header(sample)
    except csv.Error:
        has_header = False
    header = [
        cell.strip() or f"COL-{index + 1:02d}" for index, cell in enumerate(rows[0])
    ]
    data_rows = rows[1:] if has_header else rows
    width = max(len(row) for row in data_rows)
    if not has_header:
        header = [f"CH-{index + 1:02d}" for index in range(width)]

    selected: list[int] = []
    if requested_columns:
        for column in requested_columns:
            if column.lstrip("+").isdigit():
                index = int(column)
            elif has_header and column in header:
                index = header.index(column)
            else:
                raise ValueError(f"CSV column not found: {column}")
            if not 0 <= index < width:
                raise ValueError(f"CSV column index out of range: {column}")
            selected.append(index)
    else:
        for index in range(width):
            candidate_values = [
                row[index].strip() for row in data_rows if index < len(row)
            ]
            if candidate_values and all(
                _is_float(value) for value in candidate_values if value
            ):
                selected.append(index)

    channels: list[tuple[str, list[float]]] = []
    for index in selected:
        values: list[float] = []
        for row_number, row in enumerate(data_rows, start=2 if has_header else 1):
            if index >= len(row) or not row[index].strip():
                continue
            try:
                values.append(float(row[index]))
            except ValueError as error:
                raise ValueError(
                    f"CSV row {row_number}, column {index} is not numeric"
                ) from error
        channels.append((header[index], values))
    return _validate_channels(channels)


def _is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _json_channels(raw: str) -> tuple[list[tuple[str, list[float]]], str | None]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON input: {error.msg}") from error
    layout_hint: str | None = None

    if isinstance(data, dict) and "layout" in data:
        candidate = data.get("layout")
        if candidate in {"separate", "overlay"}:
            layout_hint = cast(str, candidate)

    payload = (
        data.get("channels") if isinstance(data, dict) and "channels" in data else data
    )
    channels: list[tuple[str, list[float]]] = []
    if isinstance(payload, dict):
        for name, values in payload.items():
            if isinstance(values, list):
                channels.append(
                    (str(name), [_number(value, str(name)) for value in values])
                )
    elif isinstance(payload, list) and all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in payload
    ):
        channels.append(("CH-01", [_number(value, "JSON value") for value in payload]))
    elif isinstance(payload, list):
        for index, channel in enumerate(payload, start=1):
            if isinstance(channel, dict):
                name = str(channel.get("name", f"CH-{index:02d}"))
                values = channel.get("values")
                if not isinstance(values, list):
                    raise TypeError(f"JSON channel {name} must contain a values list")
                channels.append((name, [_number(value, name) for value in values]))
            elif isinstance(channel, list):
                channels.append(
                    (
                        f"CH-{index:02d}",
                        [_number(value, f"CH-{index:02d}") for value in channel],
                    )
                )
            else:
                raise TypeError("JSON channel entries must be lists or objects")
    else:
        raise TypeError(
            "JSON must contain a numeric list, channel lists or a channels object"
        )
    return _validate_channels(channels), layout_hint


def _text_channels(raw: str) -> list[tuple[str, list[float]]]:
    values: list[float] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        try:
            values.append(float(value))
        except ValueError as error:
            raise ValueError(
                f"text line {line_number} is not a decimal value"
            ) from error
    return _validate_channels([("CH-01", values)])


def _rng(seed: str) -> random.Random:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _scale(value: float, minimum: float, maximum: float) -> float:
    normalised = max(-1.0, min(1.0, value))
    return minimum + ((normalised + 1.0) / 2.0) * (maximum - minimum)


def _synthetic_channel(
    preset: str,
    count: int,
    minimum: float,
    maximum: float,
    channel_index: int,
    rng: random.Random,
) -> list[float]:
    phase_offset = rng.uniform(0, math.tau)
    values: list[float] = []
    noise_state = rng.uniform(-0.2, 0.2)
    event_centres = [rng.uniform(0.15, 0.35), rng.uniform(0.55, 0.82)]
    for index in range(count):
        position = index / max(1, count - 1)
        if preset == "noise":
            noise_state = noise_state * 0.7 + rng.uniform(-1, 1) * 0.3
            raw_value = noise_state
        elif preset == "eeg":
            raw_value = (
                0.48
                * math.sin(position * math.tau * (7 + channel_index) + phase_offset)
                + 0.27 * math.sin(position * math.tau * (13 + channel_index * 0.7))
                + 0.12 * math.sin(position * math.tau * 31)
                + rng.uniform(-0.16, 0.16)
            )
        elif preset == "ecg":
            beat = (position * (4 + channel_index * 0.15)) % 1.0
            raw_value = (
                0.12 * math.exp(-(((beat - 0.18) / 0.045) ** 2))
                - 0.18 * math.exp(-(((beat - 0.36) / 0.018) ** 2))
                + 1.0 * math.exp(-(((beat - 0.40) / 0.012) ** 2))
                - 0.32 * math.exp(-(((beat - 0.435) / 0.018) ** 2))
                + 0.28 * math.exp(-(((beat - 0.66) / 0.08) ** 2))
                + rng.uniform(-0.025, 0.025)
            )
        else:
            raw_value = rng.uniform(-0.05, 0.05)
            for centre in event_centres:
                distance = position - centre
                if distance >= 0:
                    raw_value += math.exp(-distance * (8 + channel_index)) * math.sin(
                        distance * math.tau * (28 + channel_index * 3)
                    )
        values.append(round(_scale(raw_value, minimum, maximum), 6))
    return values


def _synthetic_channels(
    preset: str,
    count: int,
    minimum: float,
    maximum: float,
    channel_count: int,
    seed: str,
) -> list[tuple[str, list[float]]]:
    rng = _rng(seed)
    return [
        (
            f"CH-{index + 1:02d}",
            _synthetic_channel(preset, count, minimum, maximum, index, rng),
        )
        for index in range(channel_count)
    ]


def _downsample(values: Sequence[float]) -> list[float]:
    if len(values) <= MAX_PLOTTED_SAMPLES:
        return list(values)
    return [
        values[round(index * (len(values) - 1) / (MAX_PLOTTED_SAMPLES - 1))]
        for index in range(MAX_PLOTTED_SAMPLES)
    ]


def _path(
    values: Sequence[float],
    y_min: float,
    y_max: float,
    top: float,
    height: float,
    plot_width: int,
) -> str:
    plotted = _downsample(values)
    span = y_max - y_min or 1.0
    points: list[str] = []
    for index, value in enumerate(plotted):
        x = index * plot_width / max(1, len(plotted) - 1)
        y = top + 4 + ((y_max - value) / span) * max(1, height - 8)
        command = "M" if index == 0 else "L"
        points.append(f"{command}{x:.1f},{y:.1f}")
    return " ".join(points)


def _render_channels(
    channels: Sequence[tuple[str, list[float]]],
    layout: str,
    units: str,
    plot_width: int,
) -> tuple[list[dict[str, object]], list[float]]:
    all_values = [value for _, values in channels for value in values]
    global_min = min(all_values)
    global_max = max(all_values)
    panel_height = PLOT_HEIGHT / len(channels) if layout == "separate" else PLOT_HEIGHT
    rendered: list[dict[str, object]] = []
    separators: list[float] = []
    for index, (name, values) in enumerate(channels):
        top = index * panel_height if layout == "separate" else 0.0
        if layout == "separate":
            y_min, y_max = min(values), max(values)
            if index:
                separators.append(top)
        else:
            y_min, y_max = global_min, global_max
        mean = statistics.fmean(values)
        rms = math.sqrt(statistics.fmean(value * value for value in values))
        rendered.append(
            {
                "index": index,
                "name": name,
                "path": _path(values, y_min, y_max, top, panel_height, plot_width),
                "label_y": round(top + 14, 1),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "mean": round(mean, 4),
                "rms": round(rms, 4),
                "samples": len(values),
                "units": units,
            }
        )
    return rendered, separators


def build_context(options: Mapping[str, object]) -> dict[str, object]:
    source_value = options.get("source")
    source = source_value if isinstance(source_value, Path) else None
    use_stdin = bool(options.get("stdin"))
    if source is not None and use_stdin:
        raise ValueError("source and stdin cannot be used together")

    requested_format = str(options.get("format") or "auto")
    requested_columns = [
        str(value) for value in cast(Sequence[object], options.get("column") or [])
    ]
    timestamp = datetime.now().astimezone()
    seed = str(options.get("seed") or timestamp.isoformat(timespec="microseconds"))
    layout_option = str(options.get("layout") or "auto")
    units = str(options.get("units") or "a.u.")
    layout_hint: str | None = None

    if source is not None or use_stdin:
        try:
            raw = (
                source.read_text(encoding="utf-8")
                if source is not None
                else sys.stdin.read()
            )
        except OSError as error:
            raise ValueError(f"cannot read data source: {error}") from error
        if not raw.strip():
            raise ValueError("data source is empty")
        data_format = _detect_format(raw, source, requested_format)
        if data_format == "csv":
            channels = _csv_channels(raw, requested_columns)
        elif data_format == "json":
            channels, layout_hint = _json_channels(raw)
        else:
            channels = _text_channels(raw)
        source_label = str(source) if source is not None else "STDIN"
        mode = "EXTERNAL"
    else:
        minimum = _number(options.get("minimum"), "minimum")
        maximum = _number(options.get("maximum"), "maximum")
        if minimum >= maximum:
            raise ValueError("minimum must be lower than maximum")
        count = int(_number(options.get("count"), "count"))
        channel_count = int(_number(options.get("channels"), "channels"))
        preset = str(options.get("preset") or "eeg")
        channels = _synthetic_channels(
            preset, count, minimum, maximum, channel_count, seed
        )
        data_format = "generated"
        source_label = f"SYNTH/{preset.upper()}"
        mode = "SYNTHETIC"

    resolved_layout = layout_option
    if resolved_layout == "auto":
        resolved_layout = layout_hint or (
            "separate" if len(channels) > 1 else "overlay"
        )
    sample_rate = _number(options.get("sample_rate"), "sample_rate")
    sample_count = max(len(values) for _, values in channels)
    canvas_length = max(
        MIN_CANVAS_LENGTH,
        min(MAX_CANVAS_LENGTH, BASE_CANVAS_LENGTH + sample_count * PIXELS_PER_SAMPLE),
    )
    plot_width = canvas_length - 80
    rendered_channels, separators = _render_channels(
        channels, resolved_layout, units, plot_width
    )
    all_values = [value for _, values in channels for value in values]
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
    reference = str(options.get("reference") or f"SIG-{digest[:8]}")

    return {
        "title": str(options.get("title") or "MULTI-CHANNEL SIGNAL ARRAY"),
        "reference": reference,
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S %z"),
        "mode": mode,
        "source": source_label,
        "data_format": data_format.upper(),
        "layout": resolved_layout.upper(),
        "sample_rate": round(sample_rate, 3),
        "sample_count": sample_count,
        "channel_count": len(channels),
        "duration": round((sample_count - 1) / sample_rate, 3),
        "global_min": round(min(all_values), 4),
        "global_max": round(max(all_values), 4),
        "global_mean": round(statistics.fmean(all_values), 4),
        "units": units,
        "channels": rendered_channels,
        "separators": separators,
        "canvas_length": canvas_length,
        "plot_width": plot_width,
        "plot_height": PLOT_HEIGHT,
        "grid_x": [round(plot_width * index / 10) for index in range(11)],
        "seed": seed,
    }
