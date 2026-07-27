from __future__ import annotations

import base64
import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import cast

MONEY = Decimal("0.01")
MAX_ITEMS = 60
DEFAULT_ITEMS = (
    ("SYNTHETIC COFFEE", "2", "1.40", "10"),
    ("ORBITAL NOTEBOOK", "1", "6.90", "22"),
    ("SIGNAL ADAPTER", "1", "12.50", "22"),
)
CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF"}


def _decimal(value: object, field: str, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field} must be a decimal number") from error
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    if positive and result <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return result


def _money(value: Decimal, currency: str) -> str:
    amount = value.quantize(MONEY, rounding=ROUND_HALF_UP)
    raw = f"{amount:,.2f}"
    localised = raw.replace(",", "_").replace(".", ",").replace("_", ".")
    symbol = CURRENCY_SYMBOLS[currency]
    return (
        f"{localised} {symbol}"
        if currency in {"EUR", "CHF"}
        else f"{symbol}{localised}"
    )


def _parse_item(parts: Sequence[object], source: str) -> dict[str, object]:
    if len(parts) not in {3, 4}:
        raise ValueError(
            f"{source} must contain description, quantity, unit price and optional tax rate"
        )
    description = str(parts[0]).strip()
    if not description:
        raise ValueError(f"{source} description cannot be empty")
    quantity = _decimal(parts[1], f"{source} quantity", positive=True)
    unit_price = _decimal(parts[2], f"{source} unit price")
    if unit_price < 0:
        raise ValueError(f"{source} unit price cannot be negative")
    tax_rate = _decimal(parts[3] if len(parts) == 4 else 22, f"{source} tax rate")
    if not 0 <= tax_rate <= 100:
        raise ValueError(f"{source} tax rate must be between 0 and 100")
    line_total = (quantity * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
    divisor = Decimal(1) + tax_rate / Decimal(100)
    taxable = (line_total / divisor).quantize(MONEY, rounding=ROUND_HALF_UP)
    tax = line_total - taxable
    return {
        "description": description.upper(),
        "quantity": quantity,
        "unit_price": unit_price,
        "tax_rate": tax_rate,
        "line_total": line_total,
        "taxable": taxable,
        "tax": tax,
    }


def _inline_items(values: Sequence[object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index, value in enumerate(values, start=1):
        parts = [part.strip() for part in str(value).split("|")]
        items.append(_parse_item(parts, f"item {index}"))
    return items


def _file_items(path: Path) -> list[dict[str, object]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"cannot read items file: {error}") from error
    extension = path.suffix.lower()
    if extension == ".json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid items JSON: {error.msg}") from error
        if isinstance(payload, dict):
            payload = payload.get("items")
        if not isinstance(payload, list):
            raise ValueError("items JSON must be a list or an object containing items")
        items: list[dict[str, object]] = []
        for index, entry in enumerate(payload, start=1):
            if not isinstance(entry, dict):
                raise TypeError(f"JSON item {index} must be an object")
            parts = (
                entry.get("description"),
                entry.get("quantity", 1),
                entry.get("unit_price"),
                entry.get("tax_rate", 22),
            )
            items.append(_parse_item(parts, f"JSON item {index}"))
        return items
    if extension != ".csv":
        raise ValueError("items file must use .csv or .json")
    reader = csv.DictReader(raw.splitlines())
    required = {"description", "quantity", "unit_price"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError(
            "items CSV requires description, quantity and unit_price columns"
        )
    items = []
    for index, row in enumerate(reader, start=2):
        parts = (
            row.get("description"),
            row.get("quantity"),
            row.get("unit_price"),
            row.get("tax_rate") or 22,
        )
        items.append(_parse_item(parts, f"CSV row {index}"))
    return items


def _logo_data(path_value: object) -> tuple[str, str]:
    if isinstance(path_value, Path):
        path = path_value
    else:
        path = Path(__file__).parent / "assets" / "default-logo.svg"
    suffix = path.suffix.lower()
    mime = {".svg": "image/svg+xml", ".png": "image/png"}.get(suffix)
    if mime is None:
        raise ValueError("logo must be an SVG or PNG file")
    try:
        content = path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read logo: {error}") from error
    if not content:
        raise ValueError("logo file is empty")
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{encoded}", path.name


def _issued_at(value: object) -> datetime:
    if value is None:
        return datetime.now().astimezone()
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError("issued-at must be an ISO date or date/time") from error
    return parsed.astimezone()


def build_context(options: Mapping[str, object]) -> dict[str, object]:
    inline_values = cast(Sequence[object], options.get("item") or [])
    items = _inline_items(inline_values)
    file_value = options.get("items_file")
    if isinstance(file_value, Path):
        items.extend(_file_items(file_value))
    if not items:
        items = [
            _parse_item(parts, f"demo item {index}")
            for index, parts in enumerate(DEFAULT_ITEMS, start=1)
        ]
    if len(items) > MAX_ITEMS:
        raise ValueError(f"at most {MAX_ITEMS} items can be printed")

    currency = str(options.get("currency") or "EUR")
    total = sum((cast(Decimal, item["line_total"]) for item in items), Decimal(0))
    taxable_total = sum((cast(Decimal, item["taxable"]) for item in items), Decimal(0))
    tax_total = sum((cast(Decimal, item["tax"]) for item in items), Decimal(0))
    paid_value = options.get("paid")
    paid = total if paid_value is None else _decimal(paid_value, "paid")
    change = max(Decimal(0), paid - total)
    balance = max(Decimal(0), total - paid)

    tax_groups: dict[Decimal, dict[str, Decimal]] = defaultdict(
        lambda: {"taxable": Decimal(0), "tax": Decimal(0)}
    )
    for item in items:
        rate = cast(Decimal, item["tax_rate"])
        tax_groups[rate]["taxable"] += cast(Decimal, item["taxable"])
        tax_groups[rate]["tax"] += cast(Decimal, item["tax"])

    rendered_items = [
        {
            "index": index,
            "description": item["description"],
            "quantity": f"{cast(Decimal, item['quantity']):g}",
            "unit_price": _money(cast(Decimal, item["unit_price"]), currency),
            "tax_rate": f"{cast(Decimal, item['tax_rate']):g}%",
            "line_total": _money(cast(Decimal, item["line_total"]), currency),
        }
        for index, item in enumerate(items, start=1)
    ]
    rendered_taxes = [
        {
            "rate": f"{rate:g}%",
            "taxable": _money(values["taxable"], currency),
            "tax": _money(values["tax"], currency),
        }
        for rate, values in sorted(tax_groups.items())
    ]

    timestamp = _issued_at(options.get("issued_at"))
    effective_seed = str(
        options.get("seed") or timestamp.isoformat(timespec="microseconds")
    )
    digest = hashlib.sha256(effective_seed.encode("utf-8")).hexdigest().upper()
    receipt_number = str(
        options.get("receipt_number") or f"F-{digest[:4]}-{digest[4:10]}"
    )
    logo_data, logo_name = _logo_data(options.get("logo"))
    company_lines = [
        str(value)
        for value in cast(Sequence[object], options.get("company_line") or [])
    ]
    if not company_lines:
        company_lines = [
            "VIA DELLE ORBITE 42 · 00100 CITTÀ DEMO",
            "TEL. +00 000 000000 · INFO@EXAMPLE.INVALID",
        ]
    footer_lines = [
        str(value) for value in cast(Sequence[object], options.get("footer_line") or [])
    ]
    if not footer_lines:
        footer_lines = [
            "GRAZIE PER LA VISITA",
        ]
    bars = [1 + int(character, 16) % 3 for character in digest[:48]]

    return {
        "company_name": str(options.get("company_name") or "NEBULA SUPPLY CO."),
        "company_lines": company_lines,
        "vat_id": str(options.get("vat_id") or "DEMO-00000000000"),
        "logo_data": logo_data,
        "logo_name": logo_name,
        "items": rendered_items,
        "item_count": len(items),
        "taxes": rendered_taxes,
        "currency": currency,
        "taxable_total": _money(taxable_total, currency),
        "tax_total": _money(tax_total, currency),
        "total": _money(total, currency),
        "paid": _money(paid, currency),
        "change": _money(change, currency),
        "balance": _money(balance, currency),
        "has_change": change > 0,
        "has_balance": balance > 0,
        "payment_method": str(options.get("payment_method") or "card").upper(),
        "receipt_number": receipt_number,
        "register_id": str(options.get("register_id") or "RT-DEMO-01"),
        "operator": str(options.get("operator") or "OP-01"),
        "issued_date": timestamp.strftime("%d/%m/%Y"),
        "issued_time": timestamp.strftime("%H:%M:%S"),
        "customer_code": str(options.get("customer_code") or ""),
        "footer_lines": footer_lines,
        "bars": bars,
        "verification_code": digest[:24],
    }
