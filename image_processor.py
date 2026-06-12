"""
Image loading, validation, resizing, and preview generation.

Evidence: Pillow Image API
Source: https://pillow.readthedocs.io/en/stable/reference/Image.html
Verified: 2026-06-12

Pillow >= 12.2.0 required — patches CVE-2026-25990, CVE-2026-40192, CVE-2026-42308.
"""

import io

from PIL import Image

from layout_calculator import (
    CellRect,
    GridLayout,
    PAGE_SIZES,
    calculate_cell_rect,
    fit_image_in_cell,
)

ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_DIMENSION_PX = 1920


def load_and_validate(file_bytes: bytes, filename: str) -> Image.Image:
    """
    Load image from bytes, validate format, convert to RGB.
    Alpha channel is dropped (PDF background is white — transparent areas become white).
    Raises ValueError with a user-friendly message on bad input.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # Detect truncated/corrupt files early
    except Exception:
        raise ValueError(f"'{filename}' could not be read. Is it a valid image file?")

    # Re-open after verify() (verify() leaves file unusable)
    img = Image.open(io.BytesIO(file_bytes))

    fmt = img.format or ""
    if fmt.upper() not in ACCEPTED_FORMATS:
        raise ValueError(
            f"'{filename}' has unsupported format '{fmt}'. "
            f"Please use JPEG, PNG, or WEBP."
        )

    if img.mode != "RGB":
        # Paste onto white background to handle transparency
        rgb = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA"):
            rgb.paste(img, mask=img.split()[-1])
        else:
            rgb.paste(img.convert("RGB"))
        return rgb

    return img


def resize_to_max(img: Image.Image, max_px: int = MAX_DIMENSION_PX) -> Image.Image:
    """
    Resize so the longest dimension <= max_px using LANCZOS resampling.
    Returns the original object if already within limit (no copy made).
    """
    w, h = img.size
    if max(w, h) <= max_px:
        return img
    scale = max_px / max(w, h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return img.resize((new_w, new_h), Image.LANCZOS)


def create_preview(
    images: list[Image.Image],
    layout: GridLayout,
    page_size: str,
    padding_mm: float,
    preview_width_px: int = 640,
) -> Image.Image:
    """
    Render a low-resolution composite image of the PDF layout for st.image() preview.
    Scale factor maps mm → pixels: scale = preview_width_px / page_w_mm.
    Returns a white RGB PIL Image.
    """
    page_w_mm, page_h_mm = PAGE_SIZES[page_size]
    scale = preview_width_px / page_w_mm
    canvas_w = int(page_w_mm * scale)
    canvas_h = int(page_h_mm * scale)

    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

    photos_to_draw = images[: layout.capacity]

    for idx, img in enumerate(photos_to_draw):
        col = idx % layout.cols
        row = idx // layout.cols

        cell: CellRect = calculate_cell_rect(
            page_w_mm, page_h_mm,
            layout.cols, layout.rows,
            padding_mm, col, row,
        )
        draw = fit_image_in_cell(img.width, img.height, cell)

        # Convert mm coords to pixels
        px_x = int(draw.x_mm * scale)
        px_y = int(draw.y_mm * scale)
        px_w = max(1, int(draw.w_mm * scale))
        px_h = max(1, int(draw.h_mm * scale))

        resized = img.resize((px_w, px_h), Image.LANCZOS)
        canvas.paste(resized, (px_x, px_y))

    return canvas
