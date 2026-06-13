"""
Photo PDF Maker — Streamlit UI

Upload photos from your phone, rotate if needed, choose a layout, and download as a PDF.

Evidence: Streamlit 1.58.0 API
Source: https://docs.streamlit.io/develop/api-reference
Verified: 2026-06-12
"""

from datetime import datetime

import streamlit as st
from PIL import Image

from image_processor import create_preview, load_and_validate, resize_to_max
from layout_calculator import (
    MAX_PHOTOS,
    PRESET_NAMES,
    resolve_layout,
)
from pdf_engine import generate_pdf

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PicPDF",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("📄 PicPDF")
st.caption("Upload photos → rotate if needed → choose layout → download PDF")

# Larger, coloured rotate buttons (only targets buttons inside column cells)
st.markdown("""
<style>
[data-testid="column"] [data-testid="stBaseButton-primary"] p {
    font-size: 1.6rem !important;
    line-height: 1.1 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
if "images" not in st.session_state:
    st.session_state.images: list[Image.Image] = []
if "rotations" not in st.session_state:
    st.session_state.rotations: list[int] = []
if "file_sig" not in st.session_state:
    st.session_state.file_sig: list = []
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes: bytes | None = None
if "preview_img" not in st.session_state:
    st.session_state.preview_img: Image.Image | None = None
if "photo_scales" not in st.session_state:
    st.session_state.photo_scales: list[float] = []


def _reset_output() -> None:
    st.session_state.pdf_bytes = None
    st.session_state.preview_img = None


def _rotated_images() -> list[Image.Image]:
    """Return images with their current rotation applied (expand=True preserves aspect ratio)."""
    return [
        img.rotate(angle, expand=True) if angle != 0 else img
        for img, angle in zip(st.session_state.images, st.session_state.rotations)
    ]


# ── STEP 1 — Upload ───────────────────────────────────────────────────────────
st.subheader("1 · Upload Photos")

uploaded_files = st.file_uploader(
    "Select photos from your gallery",
    type=["jpg", "jpeg", "png", "webp", "heic", "heif", "bmp", "tiff", "tif", "gif"],
    accept_multiple_files=True,
    help="Tap to open your phone gallery. You can select multiple photos at once.",
    on_change=_reset_output,
)

if uploaded_files:
    # Only re-process when the file selection actually changes, not on every rerun
    # (rotation button clicks also cause reruns — we must not reset rotations then)
    current_sig = [(f.name, f.size) for f in uploaded_files]
    if current_sig != st.session_state.file_sig:
        new_images: list[Image.Image] = []
        errors: list[str] = []
        for f in uploaded_files:
            try:
                img = load_and_validate(f.read(), f.name)
                img = resize_to_max(img)
                new_images.append(img)
            except ValueError as e:
                errors.append(str(e))
        if errors:
            for err in errors:
                st.error(err)
        if new_images:
            st.session_state.images = new_images
            # Keep original orientation — EXIF already applied during load
            st.session_state.rotations = [0] * len(new_images)
            st.session_state.file_sig = current_sig
            st.session_state.photo_scales = [1.0] * len(new_images)
            _reset_output()

    if st.session_state.images:
        count = len(st.session_state.images)
        if count > MAX_PHOTOS:
            st.warning(
                f"You uploaded {count} photos. Only the first {MAX_PHOTOS} will be included in the PDF."
            )
        else:
            st.success(f"{count} photo{'s' if count != 1 else ''} ready.")

        # Thumbnails with rotate buttons — show all photos, 5 per row
        st.caption("Tap ↻ under a photo to rotate it 90° clockwise.")
        num_cols = min(count, 5)
        for row_start in range(0, count, num_cols):
            row_indices = list(range(row_start, min(row_start + num_cols, count)))
            cols = st.columns(num_cols)
            for col_pos, img_idx in enumerate(row_indices):
                with cols[col_pos]:
                    angle = st.session_state.rotations[img_idx]
                    display = (
                        st.session_state.images[img_idx].rotate(angle, expand=True)
                        if angle != 0
                        else st.session_state.images[img_idx]
                    )
                    st.image(display, width="stretch")
                    if st.button("↻", key=f"rotate_{img_idx}", type="primary", width="stretch"):
                        st.session_state.rotations[img_idx] = (angle + 90) % 360
                        _reset_output()
                        st.rerun()

# ── STEP 2 — Layout ───────────────────────────────────────────────────────────
if st.session_state.images:
    st.divider()
    st.subheader("2 · Choose Layout")

    col_layout, col_options = st.columns([2, 1])

    with col_layout:
        preset = st.radio(
            "Layout preset",
            options=PRESET_NAMES,
            index=0,
            horizontal=False,
            on_change=_reset_output,
        )

    with col_options:
        page_size = st.selectbox(
            "Page size",
            options=["A4", "Letter"],
            index=0,
            on_change=_reset_output,
        )
        padding_mm = st.slider(
            "Padding (mm)",
            min_value=0,
            max_value=20,
            value=5,
            step=1,
            on_change=_reset_output,
        )
        # Global photo size slider — hidden for MANUAL (each photo has its own slider)
        if preset != "MANUAL":
            photo_scale = st.slider(
                "Photo size (%)",
                min_value=50,
                max_value=100,
                value=100,
                step=5,
                on_change=_reset_output,
            ) / 100
        else:
            photo_scale = 1.0

    custom_cols, custom_rows = 2, 3
    if preset == "Custom":
        cc, cr = st.columns(2)
        with cc:
            custom_cols = st.number_input("Columns", min_value=1, max_value=5, value=2, on_change=_reset_output)
        with cr:
            custom_rows = st.number_input("Rows", min_value=1, max_value=6, value=3, on_change=_reset_output)

    image_count = min(len(st.session_state.images), MAX_PHOTOS)
    layout = resolve_layout(preset, image_count, int(custom_cols), int(custom_rows))

    if len(st.session_state.images) > layout.capacity:
        st.warning(
            f"This layout fits {layout.capacity} photos. "
            f"Your last {len(st.session_state.images) - layout.capacity} photo(s) will not appear."
        )

    # SMART preset: cover-fit fills gaps automatically (no extra UI needed)
    if preset == "SMART":
        st.caption("SMART: photos automatically fill their slots — gaps are minimised by cropping to fit.")

    # MANUAL preset: per-photo scale sliders
    if preset == "MANUAL":
        st.caption("MANUAL: adjust how much each photo fills its slot. 100% = fills slot completely.")
        # Ensure photo_scales list is long enough
        while len(st.session_state.photo_scales) < image_count:
            st.session_state.photo_scales.append(1.0)
        for i in range(image_count):
            st.session_state.photo_scales[i] = st.slider(
                f"Photo {i + 1} size (%)",
                min_value=50,
                max_value=100,
                value=int(st.session_state.photo_scales[i] * 100),
                step=5,
                key=f"pscale_{i}",
                on_change=_reset_output,
            ) / 100

    # Determine rendering mode
    cover_fit = preset in ("SMART", "MANUAL")
    photo_scales_for_engines = (
        st.session_state.photo_scales[:image_count] if preset == "MANUAL" else None
    )

# ── STEP 3 — Preview ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("3 · Preview")

    if st.session_state.preview_img is None:
        with st.spinner("Generating preview…"):
            st.session_state.preview_img = create_preview(
                _rotated_images(),
                layout,
                page_size,
                float(padding_mm),
                photo_scale,
                cover_fit=cover_fit,
                photo_scales=photo_scales_for_engines,
            )

    st.image(
        st.session_state.preview_img,
        caption=f"{layout.name} · {page_size} · {padding_mm}mm padding",
        width="stretch",
    )

# ── STEP 4 — Generate & Download ─────────────────────────────────────────────
    st.divider()
    st.subheader("4 · Download PDF")

    if st.button("Generate PDF", type="primary", width="stretch"):
        with st.spinner("Building PDF…"):
            st.session_state.pdf_bytes = generate_pdf(
                _rotated_images(),
                layout,
                page_size,
                float(padding_mm),
                photo_scale,
                cover_fit=cover_fit,
                photo_scales=photo_scales_for_engines,
            )

    if st.session_state.pdf_bytes:
        filename = f"photos_{datetime.now():%Y-%m-%d_%H-%M-%S}.pdf"
        st.download_button(
            label="⬇ Download PDF",
            data=st.session_state.pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            width="stretch",
        )
        size_kb = len(st.session_state.pdf_bytes) / 1024
        st.caption(f"PDF size: {size_kb:.0f} KB · {filename}")
