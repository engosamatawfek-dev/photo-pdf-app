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
    cover_crop_box,
)


def generate_pdf(
    images: list[Image.Image],
    layout: GridLayout,
    page_size: str = "A4",
    padding_mm: float = 5.0,
) -> bytes:
    """
    Generate a single-page PDF with images arranged in the given grid.
    Each image is center-cropped to fill its cell completely (cover fit, no white space).
    Images beyond layout.capacity are silently ignored.
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

        # Center-crop image to match cell aspect ratio (cover fit — no white space)
        crop_box = cover_crop_box(img.width, img.height, cell)
        cropped = img.crop(crop_box)

        buf = io.BytesIO()
        cropped.save(buf, format="JPEG", quality=90)
        buf.seek(0)

        pdf.image(buf, x=cell.x_mm, y=cell.y_mm, w=cell.w_mm, h=cell.h_mm)

    return bytes(pdf.output())
