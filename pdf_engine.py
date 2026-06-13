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
    CellRect,
    GridLayout,
    PAGE_SIZES,
    calculate_cell_rect,
    cover_crop_box,
    fit_image_in_cell,
)


def generate_pdf(
    images: list[Image.Image],
    layout: GridLayout,
    page_size: str = "A4",
    padding_mm: float = 5.0,
    photo_scale: float = 1.0,
    cover_fit: bool = False,
    photo_scales: list[float] | None = None,
) -> bytes:
    """
    Generate a single-page PDF with images arranged in the given grid.

    cover_fit=False (default): contain fit — photo scaled to fit inside cell,
        white space may appear when aspect ratios differ.
    cover_fit=True (SMART/MANUAL): cover fit — photo scaled to fill cell
        completely, center-cropped to remove overflow.
    photo_scale: global scale applied when photo_scales is None; <1.0 adds
        a uniform white border around every photo.
    photo_scales: per-photo scale list (MANUAL preset); overrides photo_scale.
    """
    page_w_mm, page_h_mm = PAGE_SIZES[page_size]

    pdf = FPDF(orientation="P", unit="mm", format=page_size)
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    photos_to_draw = images[: layout.capacity]
    leftover = len(photos_to_draw) % layout.cols

    for idx, img in enumerate(photos_to_draw):
        col = idx % layout.cols
        row = idx // layout.cols

        # Span the last photo across the full row when it would otherwise sit alone
        col_span = (
            layout.cols
            if (idx == len(photos_to_draw) - 1 and leftover == 1 and layout.cols > 1)
            else 1
        )

        cell = calculate_cell_rect(
            page_w_mm, page_h_mm,
            layout.cols, layout.rows,
            padding_mm, col, row,
            col_span,
        )

        # Effective scale: per-photo (MANUAL) or global
        s = photo_scales[idx] if photo_scales else photo_scale

        if cover_fit:
            # Apply scale as inset, then cover-crop to fill the (possibly smaller) cell
            if s < 1.0:
                inset_w = cell.w_mm * (1 - s) / 2
                inset_h = cell.h_mm * (1 - s) / 2
                cell = CellRect(
                    x_mm=cell.x_mm + inset_w,
                    y_mm=cell.y_mm + inset_h,
                    w_mm=cell.w_mm * s,
                    h_mm=cell.h_mm * s,
                )
            crop_box = cover_crop_box(img.width, img.height, cell)
            cropped = img.crop(crop_box)
            buf = io.BytesIO()
            cropped.save(buf, format="JPEG", quality=90)
            buf.seek(0)
            pdf.image(buf, x=cell.x_mm, y=cell.y_mm, w=cell.w_mm, h=cell.h_mm)
        else:
            # Contain fit: shrink cell inward then fit image (white space fills remainder)
            if s < 1.0:
                inset_w = cell.w_mm * (1 - s) / 2
                inset_h = cell.h_mm * (1 - s) / 2
                cell = CellRect(
                    x_mm=cell.x_mm + inset_w,
                    y_mm=cell.y_mm + inset_h,
                    w_mm=cell.w_mm * s,
                    h_mm=cell.h_mm * s,
                )
            draw = fit_image_in_cell(img.width, img.height, cell)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            buf.seek(0)
            pdf.image(buf, x=draw.x_mm, y=draw.y_mm, w=draw.w_mm, h=draw.h_mm)

    return bytes(pdf.output())
