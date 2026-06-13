"""
Grid layout calculations for the photo PDF collage app.

Evidence: fpdf2 coordinate system uses mm from top-left origin.
Source: https://py-pdf.github.io/fpdf2/Tutorial.html
Verified: 2026-06-13
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GridLayout:
    name: str
    cols: int
    rows: int

    @property
    def capacity(self) -> int:
        return self.cols * self.rows


@dataclass(frozen=True)
class CellRect:
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


@dataclass(frozen=True)
class DrawRect:
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "Letter": (215.9, 279.4),
}

# Fixed grid presets — cols × rows
PRESET_NAMES: list[str] = [
    "1×1",
    "1×2",
    "2×1",
    "2×2",
    "2×3",
    "3×2",
    "3×3",
    "2×4",
    "4×2",
    "2×5",
    "5×2",
]

_PRESET_GRIDS: dict[str, tuple[int, int]] = {
    "1×1": (1, 1),
    "1×2": (1, 2),
    "2×1": (2, 1),
    "2×2": (2, 2),
    "2×3": (2, 3),
    "3×2": (3, 2),
    "3×3": (3, 3),
    "2×4": (2, 4),
    "4×2": (4, 2),
    "2×5": (2, 5),
    "5×2": (5, 2),
}


def resolve_layout(preset_name: str) -> GridLayout:
    """Return a GridLayout for the given preset name."""
    cols, rows = _PRESET_GRIDS[preset_name]
    return GridLayout(preset_name, cols, rows)


def calculate_cell_rect_weighted(
    page_w_mm: float,
    page_h_mm: float,
    col_weights: list[float],
    row_weights: list[float],
    padding_mm: float,
    col: int,
    row: int,
) -> CellRect:
    """
    Bounding box of one grid cell using proportional column/row weights.

    Available width/height is divided proportionally to the weights list.
    Padding is uniform: outer edges + between cells.
    A higher weight means a wider column or taller row; neighbors shrink
    automatically because the total space is fixed.
    """
    cols = len(col_weights)
    rows = len(row_weights)

    avail_w = page_w_mm - (cols + 1) * padding_mm
    avail_h = page_h_mm - (rows + 1) * padding_mm

    total_cw = sum(col_weights)
    total_rh = sum(row_weights)

    x = padding_mm
    for i in range(col):
        x += col_weights[i] / total_cw * avail_w + padding_mm
    w = col_weights[col] / total_cw * avail_w

    y = padding_mm
    for i in range(row):
        y += row_weights[i] / total_rh * avail_h + padding_mm
    h = row_weights[row] / total_rh * avail_h

    return CellRect(x_mm=x, y_mm=y, w_mm=w, h_mm=h)


def fit_image_in_cell(
    img_w_px: int,
    img_h_px: int,
    cell: CellRect,
) -> DrawRect:
    """
    Contain fit: scale image to fill cell as much as possible without
    cropping, then centre it. White space fills the remainder.
    """
    img_ar = img_w_px / img_h_px
    cell_ar = cell.w_mm / cell.h_mm

    if img_ar >= cell_ar:
        draw_w = cell.w_mm
        draw_h = cell.w_mm / img_ar
        draw_x = cell.x_mm
        draw_y = cell.y_mm + (cell.h_mm - draw_h) / 2
    else:
        draw_h = cell.h_mm
        draw_w = cell.h_mm * img_ar
        draw_x = cell.x_mm + (cell.w_mm - draw_w) / 2
        draw_y = cell.y_mm

    return DrawRect(x_mm=draw_x, y_mm=draw_y, w_mm=draw_w, h_mm=draw_h)
