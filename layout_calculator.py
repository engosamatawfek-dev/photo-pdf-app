"""
Grid layout calculations for the photo PDF collage app.

Evidence: fpdf2 coordinate system uses mm from top-left origin.
Source: https://py-pdf.github.io/fpdf2/Tutorial.html
Verified: 2026-06-12
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

# Ordered for display in the UI radio widget
PRESET_NAMES: list[str] = [
    "Auto",
    "Smart",
    "Single (1×1)",
    "Side by Side (2×1)",
    "Portrait Pair (1×2)",
    "Quad (2×2)",
    "Six-up (2×3)",
    "Nine-up (3×3)",
    "Ten-up (2×5)",
    "Custom",
]

_PRESET_GRIDS: dict[str, tuple[int, int]] = {
    "Single (1×1)":       (1, 1),
    "Side by Side (2×1)": (2, 1),
    "Portrait Pair (1×2)":(1, 2),
    "Quad (2×2)":         (2, 2),
    "Six-up (2×3)":       (2, 3),
    "Nine-up (3×3)":      (3, 3),
    "Ten-up (2×5)":       (2, 5),
}

# Auto layout: maps image count → (cols, rows)
# Optimised for 5–10 photos (primary use case).
_AUTO_MAP: dict[int, tuple[int, int]] = {
    1:  (1, 1),
    2:  (2, 1),
    3:  (2, 2),
    4:  (2, 2),
    5:  (2, 3),
    6:  (2, 3),
    7:  (3, 3),
    8:  (3, 3),
    9:  (3, 3),
    10: (2, 5),
}
MAX_PHOTOS = 10


def resolve_layout(
    preset_name: str,
    image_count: int,
    custom_cols: int = 2,
    custom_rows: int = 3,
) -> GridLayout:
    """
    Return a GridLayout with concrete cols and rows.
    Auto selects grid based on image count.
    Custom uses caller-supplied values.
    """
    if preset_name == "Auto":
        capped = min(image_count, MAX_PHOTOS)
        cols, rows = _AUTO_MAP.get(capped, (2, 5))
        return GridLayout(f"Auto ({cols}×{rows})", cols, rows)

    if preset_name == "Smart":
        # Per-photo cells are computed separately; use a placeholder with capacity = image_count
        return GridLayout("Smart", cols=1, rows=image_count)

    if preset_name == "Custom":
        cols = max(1, custom_cols)
        rows = max(1, custom_rows)
        return GridLayout(f"Custom ({cols}×{rows})", cols, rows)

    cols, rows = _PRESET_GRIDS[preset_name]
    return GridLayout(preset_name, cols, rows)


def calculate_cell_rect(
    page_w_mm: float,
    page_h_mm: float,
    cols: int,
    rows: int,
    padding_mm: float,
    col: int,
    row: int,
    col_span: int = 1,
) -> CellRect:
    """
    Bounding box of one grid cell in mm.

    Padding is uniform: outer edges + between cells.
    cell_w = (page_w - (cols+1)*padding) / cols
    cell_h = (page_h - (rows+1)*padding) / rows
    cell_x = padding + col*(cell_w + padding)
    cell_y = padding + row*(cell_h + padding)
    col_span > 1: cell stretches across that many columns (padding between them absorbed).
    """
    cell_w = (page_w_mm - (cols + 1) * padding_mm) / cols
    cell_h = (page_h_mm - (rows + 1) * padding_mm) / rows
    cell_x = padding_mm + col * (cell_w + padding_mm)
    cell_y = padding_mm + row * (cell_h + padding_mm)
    actual_w = cell_w * col_span + padding_mm * (col_span - 1)
    return CellRect(x_mm=cell_x, y_mm=cell_y, w_mm=actual_w, h_mm=cell_h)


def fit_image_in_cell(
    img_w_px: int,
    img_h_px: int,
    cell: CellRect,
) -> DrawRect:
    """
    "Contain" fit: scale image to fill cell as much as possible without
    cropping, then centre it. White space fills the remainder.
    """
    img_ar = img_w_px / img_h_px
    cell_ar = cell.w_mm / cell.h_mm

    if img_ar >= cell_ar:
        # Image wider than cell — constrain by width
        draw_w = cell.w_mm
        draw_h = cell.w_mm / img_ar
        draw_x = cell.x_mm
        draw_y = cell.y_mm + (cell.h_mm - draw_h) / 2
    else:
        # Image taller than cell — constrain by height
        draw_h = cell.h_mm
        draw_w = cell.h_mm * img_ar
        draw_x = cell.x_mm + (cell.w_mm - draw_w) / 2
        draw_y = cell.y_mm

    return DrawRect(x_mm=draw_x, y_mm=draw_y, w_mm=draw_w, h_mm=draw_h)


def _group_photos_into_rows(
    aspect_ratios: list[float],
    target_row_ar: float = 1.4,
    max_per_row: int = 3,
) -> list[list[int]]:
    """
    Greedy grouping: add photos to the current row until the cumulative
    aspect-ratio sum exceeds target_row_ar or max_per_row is reached.
    Preserves upload order.
    """
    rows: list[list[int]] = []
    current: list[int] = []
    current_sum = 0.0

    for i, ar in enumerate(aspect_ratios):
        if current and (current_sum + ar > target_row_ar or len(current) >= max_per_row):
            rows.append(current)
            current, current_sum = [i], ar
        else:
            current.append(i)
            current_sum += ar

    if current:
        rows.append(current)
    return rows


def calculate_orientation_aware_cells(
    aspect_ratios: list[float],
    page_w_mm: float,
    page_h_mm: float,
    padding_mm: float,
) -> list[CellRect]:
    """
    Smart layout: one CellRect per photo sized to match its aspect ratio.

    Photos are grouped into rows (landscape photos alone, portrait photos
    in pairs).  All rows share equal height.  Within each multi-photo row
    widths are proportional to each photo's aspect ratio — so cells exactly
    match their photo (no white space, no cropping needed).
    Single-photo rows get a naturally sized cell centred on the page.
    """
    rows = _group_photos_into_rows(aspect_ratios)
    n_rows = len(rows)
    row_h = (page_h_mm - (n_rows + 1) * padding_mm) / n_rows

    cells: list[CellRect | None] = [None] * len(aspect_ratios)

    for row_idx, row_indices in enumerate(rows):
        row_y = padding_mm + row_idx * (row_h + padding_mm)
        n = len(row_indices)
        avail_w = page_w_mm - (n + 1) * padding_mm

        if n == 1:
            # Single photo: natural width (ar × row_h), centred on page
            ar = aspect_ratios[row_indices[0]]
            w = min(ar * row_h, avail_w)
            x = (page_w_mm - w) / 2
            cells[row_indices[0]] = CellRect(x_mm=x, y_mm=row_y, w_mm=w, h_mm=row_h)
        else:
            # Multiple photos: widths proportional to aspect ratios
            total_ar = sum(aspect_ratios[i] for i in row_indices)
            x = padding_mm
            for photo_idx in row_indices:
                w = aspect_ratios[photo_idx] / total_ar * avail_w
                cells[photo_idx] = CellRect(x_mm=x, y_mm=row_y, w_mm=w, h_mm=row_h)
                x += w + padding_mm

    return cells  # type: ignore[return-value]


def cover_crop_box(img_w_px: int, img_h_px: int, cell: CellRect) -> tuple[int, int, int, int]:
    """
    Return a (left, top, right, bottom) pixel crop box that makes the image
    exactly match the cell aspect ratio — center crop, no white space (cover fit).
    """
    img_ar = img_w_px / img_h_px
    cell_ar = cell.w_mm / cell.h_mm

    if img_ar > cell_ar:
        # Image wider than cell — crop left and right
        target_w = int(img_h_px * cell_ar)
        left = (img_w_px - target_w) // 2
        return (left, 0, left + target_w, img_h_px)
    elif img_ar < cell_ar:
        # Image taller than cell — crop top and bottom
        target_h = int(img_w_px / cell_ar)
        top = (img_h_px - target_h) // 2
        return (0, top, img_w_px, top + target_h)
    else:
        return (0, 0, img_w_px, img_h_px)
