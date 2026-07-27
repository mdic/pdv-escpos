# `facsimile-receipt` template

A realistic receipt-style layout for props, installations, demonstrations and fictional scenarios. The output is permanently marked **FACSIMILE**, **NON FISCALE** and **PRIVO DI VALIDITÀ**; it must not be used or represented as a valid tax document.

It includes a logo, fictional company data, document metadata, purchased goods, VAT summary, totals, payment, change or outstanding balance, decorative barcode and footer.

## Quick preview

```shell
uv run pdv-escpos facsimile-receipt render \
  --company-name "NEBULA SUPPLY CO." \
  --company-line "Via delle Orbite 42 · Città Demo" \
  --company-line "info@example.invalid" \
  --vat-id "DEMO-00000000000" \
  --item "Synthetic coffee|2|1.40|10" \
  --item "Orbital notebook|1|6.90|22" \
  --item "Signal adapter|1|12.50|22" \
  --payment-method card \
  --seed "RECEIPT-DEMO-001" \
  --output output/facsimile-receipt.png
```

Without `--item` or `--items-file`, the generator uses a short fictional demo basket.

## Header logo

The bundled placeholder is used by default. Supply a local SVG or PNG with:

```shell
--logo artwork/company-mark.svg
```

The generator embeds the file as a data URL, so rendering remains offline. Other image formats are rejected. For thermal clarity, use monochrome artwork with simple shapes and no fine grey detail.

## Company data

- `--company-name` sets the fictional business name;
- repeat `--company-line` for address, contact and other header lines;
- `--vat-id` prints a fictional identifier explicitly labelled as a facsimile;
- `--register-id` and `--operator` set fictional terminal metadata;
- `--customer-code` adds an optional fictional customer identifier.

## Items from the CLI

Repeat `--item` using this pipe-separated format:

```text
description|quantity|unit_price|tax_rate
```

Examples:

```shell
--item "Coffee|2|1.40|10"
--item "Notebook|1|6.90|22"
```

The tax rate is optional and defaults to `22`. Unit prices are treated as tax-inclusive consumer prices. Quantity and price use decimal points on the CLI; printed money uses receipt-style local formatting.

## Items from CSV

```csv
description,quantity,unit_price,tax_rate
Coffee,2,1.40,10
Notebook,1,6.90,22
```

```shell
uv run pdv-escpos facsimile-receipt render \
  --items-file basket.csv \
  --output output/facsimile-csv.png
```

The required columns are `description`, `quantity` and `unit_price`; `tax_rate` is optional.

## Items from JSON

Use a list or an object containing `items`:

```json
{
  "items": [
    {
      "description": "Coffee",
      "quantity": 2,
      "unit_price": 1.40,
      "tax_rate": 10
    },
    {
      "description": "Notebook",
      "quantity": 1,
      "unit_price": 6.90,
      "tax_rate": 22
    }
  ]
}
```

CLI items and file items may be combined. At most 60 rows are accepted.

## Currency and payment

Currencies: `EUR`, `USD`, `GBP`, `CHF`.

Payment methods: `cash`, `card`, `transfer`, `voucher`.

`--paid` defaults to the calculated total. A higher amount prints change; a lower amount prints the outstanding balance.

```shell
uv run pdv-escpos facsimile-receipt render \
  --item "Demo object|1|12.50|22" \
  --payment-method cash \
  --paid 20 \
  --currency EUR \
  --output output/facsimile-cash.png
```

## Date, numbering and footer

- `--issued-at` accepts an ISO date or date/time;
- `--receipt-number` overrides the generated facsimile number;
- `--seed` reproduces the generated number and decorative verification code;
- repeat `--footer-line` for custom closing text.

## Font

`template.yaml` declares `assets/DepartureMono-Regular.otf` under `fonts`. The core infers OpenType from `.otf`, embeds it locally and exposes it as `ReceiptPixel` to `style.css`.

## Build and print

```shell
uv run pdv-escpos facsimile-receipt build \
  --items-file basket.json \
  --output output/facsimile-receipt.bin

uv run pdv-escpos facsimile-receipt print \
  --items-file basket.json \
  --no-cut
```

Always preview the PNG before physical printing.
