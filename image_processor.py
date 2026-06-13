"""
Image loading, validation, resizing, and preview generation.

Evidence: Pillow Image API
Source: https://pillow.readthedocs.io/en/stable/reference/Image.html
Verified: 2026-06-12

Pillow >= 12.2.0 required — patches CVE-2026-25990, CVE-2026-40192, CVE-2026-42308.
pillow-heif registered at import time to add HEIC/HEIF (iPhone) support.
"""

import io

from PIL import Image, ImageOps

# Register HEIC/HEIF support if pillow-heif is installed
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

from layout_calculator import (
    CellRect,
    GridLayout,
    PAGE_SIZES,
    calculate_cell_rect,
    cover_crop_box,
    fit_image_in_cell,
)

MAX_DIMENSION_PX = 1920


def load_and_validate(file_bytes: bytes, filename: str) -> Image.Image:
    """
    Load image from bytes, convert to RGB.
    Accepts any format Pillow can open (JPEG, PNG, WEBP, HEIC, BMP, GIF, TIFF, …).
    Alpha channel is dropped — transparent areas become white (PDF background).
    Raises ValueError with a user-friendly message on bad input.
    """
    try:
        buf = io.BytesIO(file_bytes)
        img = Image.open(buf)
        img.load()  # Force-decode to catch truncated/corrupt files
    except Exception:
        raise ValueError(f"'{filename}' could not be read. Is it a valid image file?")

    # Apply EXIF orientation so phone photos (which store rotation in metadata) appear correctly
    img = ImageOps.exif_transpose(img)

    if img.mode != "RGB":
        # Paste onto white background to handle transparency (RGBA, LA, P modes)
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
    photo_scale: float = 1.0,
    preview_width_px: int = 640,
    cover_fit: bool = False,
    photo_scales: list[float] | None = None,
) -> Image.Image:
    """
    Render a composite image of the PDF layout for st.image() preview.

    cover_fit=False: contain fit — white space may appear at cell edges.
    cover_fit=True: cover fit — image fills cell completely, center-cropped.
    photo_scale: global scale (0.5–1.0) when photo_scales is None.
    photo_scales: per-photo scale list (MANUAL preset); overrides photo_scale.
    Returns a white RGB PIL Image.
    """
    page_w_mm, page_h_mm = PAGE_SIZES[page_size]
    scale = preview_width_px / page_w_mm
    canvas_w = int(page_w_mm * scale)
    canvas_h = int(page_h_mm * scale)

    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

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
            px_x = int(cell.x_mm * scale)
            px_y = int(cell.y_mm * scale)
            px_w = max(1, int(cell.w_mm * scale))
            px_h = max(1, int(cell.h_mm * scale))
            resized = cropped.resize((px_w, px_h), Image.LANCZOS)
            canvas.paste(resized, (px_x, px_y))
        else:
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
            px_x = int(draw.x_mm * scale)
            px_y = int(draw.y_mm * scale)
            px_w = max(1, int(draw.w_mm * scale))
            px_h = max(1, int(draw.h_mm * scale))
            resized = img.resize((px_w, px_h), Image.LANCZOS)
            canvas.paste(resized, (px_x, px_y))

    return canvas
