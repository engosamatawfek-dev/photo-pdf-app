"""
PDF generation using fpdf2.

Evidence: fpdf2 image API — pdf.image() accepts file path, BytesIO, or PIL Image.
Source: https://py-pdf.github.io/fpdf2/Images.html
Verified: 2026-06-13
"""

import io

from fpdf import FPDF
from PIL import Image

from layout_calculator import (
    GridLayout,
    PAGE_SIZES,
    calculate_cell_rect_weighted,
    fit_image_in_cell,
)


def generate_pdf(
    images: list[Image.Image],
    layout: GridLayout,
    page_size: str = "A4",
    padding_mm: float = 5.0,
    col_weights: list[float] | None = None,
    row_weights: list[float] | None = None,
) -> bytes:
    """
    Generate a single-page PDF with images arranged in the given grid.

    Images are never cropped — contain fit scales each photo to fill its
    cell as much as possible while preserving the full image.

    col_weights / row_weights: relative sizes of each column / row.
    None defaults to equal weights (uniform grid).
    """
    page_w_mm, page_h_mm = PAGE_SIZES[page_size]

    cw = col_weights if col_weights else [1.0] * layout.cols
    rw = row_weights if row_weights else [1.0] * layout.rows

    pdf = FPDF(orientation="P", unit="mm", format=page_size)
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    photos_to_draw = images[: layout.capacity]

    for idx, img in enumerate(photos_to_draw):
        col = idx % layout.cols
        row = idx // layout.cols

        cell = calculate_cell_rect_weighted(
            page_w_mm, page_h_mm, cw, rw, padding_mm, col, row
        )
        draw = fit_image_in_cell(img.width, img.height, cell)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        pdf.image(buf, x=draw.x_mm, y=draw.y_mm, w=draw.w_mm, h=draw.h_mm)

    return bytes(pdf.output())
