"""
PDF generation using fpdf2.

Evidence: fpdf2 image API — pdf.image() accepts file path, BytesIO, or PIL Image.
Source: https://py-pdf.github.io/fpdf2/Images.html
Verified: 2026-06-12
"""

import io

from fpdf import FPDF
from PIL import Image

from layout_calculator import (
    GridLayout,
    PAGE_SIZES,
    calculate_cell_rect,
    fit_image_in_cell,
)


def generate_pdf(
    images: list[Image.Image],
    layout: GridLayout,
    page_size: str = "A4",
    padding_mm: float = 5.0,
) -> bytes:
    """
    Generate a single-page PDF with images arranged in the given grid.

    Images beyond layout.capacity are silently ignored —
    the caller is responsible for showing the user a warning via st.warning().

    Returns raw PDF bytes ready for st.download_button(data=...).
    """
    page_w_mm, page_h_mm = PAGE_SIZES[page_size]

    pdf = FPDF(orientation="P", unit="mm", format=page_size)
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    photos_to_draw = images[: layout.capacity]

    for idx, img in enumerate(photos_to_draw):
        col = idx % layout.cols
        row = idx // layout.cols

        cell = calculate_cell_rect(
            page_w_mm, page_h_mm,
            layout.cols, layout.rows,
            padding_mm, col, row,
        )
        draw = fit_image_in_cell(img.width, img.height, cell)

        # Save PIL Image to in-memory JPEG buffer — fpdf2 accepts BytesIO directly
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)

        pdf.image(buf, x=draw.x_mm, y=draw.y_mm, w=draw.w_mm, h=draw.h_mm)

    return bytes(pdf.output())
