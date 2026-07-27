# thermal-font
Scalable TrueType conversions of Thermal Sans Mono, plus a double-width variant inspired by thermal receipt printer modes.

## Included fonts

- `ThermalTicket.ttf` — normal-width scalable conversion
- `ThermalTicketWide.ttf` — 2× horizontally expanded double-width variant

## Conversion

The fonts are derived from [Thermal Sans Mono]([url](https://github.com/mike42/thermal-sans-mono))’s 9×17 and 12×24 BDF bitmap
sources. They were converted into scalable TrueType outlines using `mkttf`.

`ThermalTicketWide.ttf` was created by horizontally scaling every glyph and
advance width by 2× to recreate thermal printer double-width text.
