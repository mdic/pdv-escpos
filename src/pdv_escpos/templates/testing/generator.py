from __future__ import annotations

from collections.abc import Mapping


def build_context(options: Mapping[str, object]) -> dict[str, object]:
    return {"message": str(options.get("message") or "")}
