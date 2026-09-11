from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree

from openpyxl.styles.colors import COLOR_INDEX

from metaphor_agreement_studio.domain.imports import CellSnapshot


@dataclass(frozen=True, slots=True)
class ResolvedColor:
    rgb: tuple[int, int, int] | None
    source: str
    tint: float = 0.0
    descriptor: str | None = None


def _rgb_from_hex(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    raw = value.strip().lstrip("#")
    if len(raw) == 8:
        raw = raw[-6:]
    if len(raw) != 6:
        return None
    try:
        return tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def _theme_colors(theme: str | bytes | None) -> tuple[tuple[int, int, int] | None, ...]:
    if not theme:
        return ()
    try:
        root = ElementTree.fromstring(theme)
    except (ElementTree.ParseError, TypeError):
        return ()
    namespace = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    scheme = root.find(f".//{namespace}clrScheme")
    if scheme is None:
        return ()
    colors: list[tuple[int, int, int] | None] = []
    for entry in list(scheme):
        child = next(iter(entry), None)
        if child is None:
            colors.append(None)
            continue
        value = child.attrib.get("val") or child.attrib.get("lastClr")
        colors.append(_rgb_from_hex(value))
    return tuple(colors)


def _apply_tint(rgb: tuple[int, int, int], tint: float) -> tuple[int, int, int]:
    if tint == 0:
        return rgb
    output: list[int] = []
    for channel in rgb:
        if tint < 0:
            value = channel * (1.0 + tint)
        else:
            value = channel * (1.0 - tint) + 255.0 * tint
        output.append(max(0, min(255, round(value))))
    return tuple(output)  # type: ignore[return-value]


def resolve_fill_color(cell: CellSnapshot, workbook_theme: str | bytes | None) -> ResolvedColor:
    fill = cell.fill
    tint = fill.fg_tint
    if fill.fill_type is None:
        return ResolvedColor(None, "none", tint, "no-fill")
    if fill.fg_type == "rgb":
        rgb = _rgb_from_hex(fill.fg_rgb)
        return ResolvedColor(_apply_tint(rgb, tint) if rgb else None, "rgb", tint, fill.fg_rgb)
    if fill.fg_type == "theme" and fill.fg_theme is not None:
        palette = _theme_colors(workbook_theme)
        rgb = palette[fill.fg_theme] if 0 <= fill.fg_theme < len(palette) else None
        descriptor = f"theme:{fill.fg_theme}"
        return ResolvedColor(_apply_tint(rgb, tint) if rgb else None, "theme", tint, descriptor)
    if fill.fg_type == "indexed" and fill.fg_indexed is not None:
        index = fill.fg_indexed
        value = COLOR_INDEX[index] if 0 <= index < len(COLOR_INDEX) else None
        rgb = _rgb_from_hex(value)
        return ResolvedColor(_apply_tint(rgb, tint) if rgb else None, "indexed", tint, f"indexed:{index}")
    return ResolvedColor(None, fill.fg_type or "unknown", tint, None)


def color_family(rgb: tuple[int, int, int] | None) -> str:
    if rgb is None:
        return "unknown"
    red, green, blue = rgb
    if green >= red + 5 and green >= blue + 5:
        return "green"
    if red >= green + 10 and red >= blue + 10:
        return "red"
    return "neutral"


def color_hex(rgb: tuple[int, int, int] | None) -> str:
    if rgb is None:
        return "unknown"
    return "#" + "".join(f"{channel:02X}" for channel in rgb)
