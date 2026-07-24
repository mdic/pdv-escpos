from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import pairwise

_METRICS = (
    "COGNITIVE DRIFT",
    "RELATIONAL DENSITY",
    "MEMORY PARALLAX",
    "AGENCY VECTOR",
    "EMPATHIC FLUX",
    "TEMPORAL RESIDUE",
    "COLLECTIVE GRAVITY",
    "UNKNOWN RESONANCE",
    "SEMANTIC PRESSURE",
    "INTELLIGENCE PHASE",
    "PERCEPTUAL ORBIT",
    "RECURSIVE DISTANCE",
)


@dataclass(frozen=True)
class Coordinates:
    ra: str
    dec: str
    depth: str
    origin: str


@dataclass(frozen=True)
class Reading:
    index: int
    metric: str
    value: float
    signal: str


@dataclass(frozen=True)
class Analysis:
    nodes: int
    mean_resonance: float
    coherence_index: float
    semantic_magnitude: float
    pattern: str


def _rng(seed: str) -> random.Random:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest, byteorder="big"))


def _parse_coordinates(value: str) -> tuple[str, str, str]:
    parts = tuple(part.strip() for part in value.split("/"))
    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError("coordinates must contain RA, DEC and depth separated by '/'")
    return parts


def _generated_coordinates(rng: random.Random) -> Coordinates:
    ra = (
        f"{rng.randrange(24):02d}H {rng.randrange(60):02d}M {rng.uniform(0, 60):04.1f}S"
    )
    sign = rng.choice(("+", "-"))
    dec = f"{sign}{rng.randrange(90):02d}D {rng.randrange(60):02d}M {rng.randrange(60):02d}S"
    depth = f"Z{rng.choice(('+', '-'))}{rng.uniform(0, 99):06.2f}"
    origin = (
        f"{rng.choice(('PSI', 'LAMBDA', 'TAU', 'OMEGA'))}-{rng.randrange(10, 100):02d}"
    )
    return Coordinates(ra=ra, dec=dec, depth=depth, origin=origin)


def _signal_for(value: float, rng: random.Random) -> str:
    if value >= 80:
        return rng.choice(("ASCENDING", "HIGH COHERENCE", "MULTIPLE SOURCES"))
    if value >= 60:
        return rng.choice(("COHERENT", "STABLE", "ENTANGLED"))
    if value >= 40:
        return rng.choice(("OSCILLATING", "DIFFUSE", "LOW VISIBILITY"))
    return rng.choice(("UNRESOLVED", "FRAGMENTED", "WEAK RETURN"))


def _constellation(
    readings: Sequence[Reading], width: int = 39, height: int = 10
) -> list[str]:
    field = [[" " for _ in range(width)] for _ in range(height)]
    points: list[tuple[int, int]] = []
    occupied: set[tuple[int, int]] = set()
    for reading in readings:
        base_x = round((reading.value / 100) * (width - 1))
        base_y = (reading.index * 3 + round(reading.value)) % height
        point = (base_x, base_y)
        for offset in range(width * height):
            candidate = (
                (base_x + offset // height) % width,
                (base_y + offset) % height,
            )
            if candidate not in occupied:
                point = candidate
                break
        points.append(point)
        occupied.add(point)

    for point_index, (x, y) in enumerate(points):
        field[y][x] = "+" if point_index == len(points) - 1 else "*"

    for (x1, y1), (x2, y2) in pairwise(points):
        steps = max(abs(x2 - x1), abs(y2 - y1))
        if steps < 2:
            continue
        for step in range(1, steps):
            x = round(x1 + (x2 - x1) * step / steps)
            y = round(y1 + (y2 - y1) * step / steps)
            if field[y][x] == " ":
                field[y][x] = "."

    return ["".join(row).rstrip() for row in field]


def build_observation(
    *,
    questions: int | None = None,
    responses: Sequence[float] | None = None,
    seed: str | None = None,
    coordinates: str | None = None,
    ra: str | None = None,
    dec: str | None = None,
    depth: str | None = None,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    supplied_responses = list(responses or ())
    if questions is not None and not 1 <= questions <= 99:
        raise ValueError("questions must be between 1 and 99")
    if (
        supplied_responses
        and questions is not None
        and len(supplied_responses) != questions
    ):
        raise ValueError("questions must match the number of responses")
    if any(
        not math.isfinite(value) or not 0 <= value <= 100
        for value in supplied_responses
    ):
        raise ValueError("responses must be finite values between 0 and 100")
    if coordinates and any(value is not None for value in (ra, dec, depth)):
        raise ValueError(
            "coordinates cannot be combined with ra, dec or depth overrides"
        )

    question_count = len(supplied_responses) if supplied_responses else questions or 5
    timestamp = observed_at or datetime.now().astimezone()
    effective_seed = seed or timestamp.isoformat(timespec="microseconds")
    rng = _rng(effective_seed)
    generated_coordinates = _generated_coordinates(rng)

    if coordinates:
        coordinate_ra, coordinate_dec, coordinate_depth = _parse_coordinates(
            coordinates
        )
    else:
        coordinate_ra = ra or generated_coordinates.ra
        coordinate_dec = dec or generated_coordinates.dec
        coordinate_depth = depth or generated_coordinates.depth
    observation_coordinates = Coordinates(
        ra=coordinate_ra,
        dec=coordinate_dec,
        depth=coordinate_depth,
        origin=generated_coordinates.origin,
    )

    values = supplied_responses or [
        round(rng.uniform(18, 94), 1) for _ in range(question_count)
    ]
    metrics = list(_METRICS)
    rng.shuffle(metrics)
    readings = [
        Reading(
            index=index,
            metric=metrics[(index - 1) % len(metrics)],
            value=round(value, 1),
            signal=_signal_for(value, rng),
        )
        for index, value in enumerate(values, start=1)
    ]

    mean = statistics.fmean(reading.value for reading in readings)
    deviation = statistics.pstdev(reading.value for reading in readings)
    coherence = max(0.0, min(0.99, 1 - deviation / 50))
    if coherence >= 0.82:
        pattern = "DENSE CLUSTER"
    elif coherence >= 0.62:
        pattern = "PARTIAL CLUSTER"
    elif coherence >= 0.42:
        pattern = "DISPERSED CHAIN"
    else:
        pattern = "UNBOUND FIELD"
    analysis = Analysis(
        nodes=question_count,
        mean_resonance=round(mean, 1),
        coherence_index=round(coherence, 2),
        semantic_magnitude=round((mean - 50) / 10, 1),
        pattern=pattern,
    )

    digest = hashlib.sha256(effective_seed.encode("utf-8")).hexdigest().upper()
    observation_id = f"{int(digest[:12], 16) % 1_000_000:06d}"
    catalogue_id = f"INT-{observation_id}-{observation_coordinates.origin}"
    return {
        "observation_id": observation_id,
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "question_count": question_count,
        "coordinates": asdict(observation_coordinates),
        "readings": [asdict(reading) for reading in readings],
        "analysis": asdict(analysis),
        "constellation": _constellation(readings),
        "catalogue_id": catalogue_id,
        "seed": effective_seed,
    }


def build_context(options: Mapping[str, object]) -> dict[str, object]:
    """Build the Jinja2 context from values parsed from template.yaml."""
    return build_observation(
        questions=options.get("questions"),  # type: ignore[arg-type]
        responses=options.get("response"),  # type: ignore[arg-type]
        seed=options.get("seed"),  # type: ignore[arg-type]
        coordinates=options.get("coordinates"),  # type: ignore[arg-type]
        ra=options.get("ra"),  # type: ignore[arg-type]
        dec=options.get("dec"),  # type: ignore[arg-type]
        depth=options.get("depth"),  # type: ignore[arg-type]
    )
