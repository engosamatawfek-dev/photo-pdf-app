"""
Photo PDF Maker — Streamlit UI

Upload photos from your phone, rotate if needed, and download as a PDF.
Layout is always Auto (grid chosen based on photo count). Page: A4, padding: 5mm.

Evidence: Streamlit 1.58.0 API
Source: https://docs.streamlit.io/develop/api-reference
Verified: 2026-06-12
"""

from datetime import datetime

import streamlit as st
from PIL import Image

from image_processor import create_preview, load_and_validate, resize_to_max
from layout_calculator import MAX_PHOTOS, resolve_layout
from pdf_engine import generate_pdf

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PicPDF",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("📄 PicPDF")
st.caption("Upload photos → rotate if needed → download PDF")

# Larger, coloured rotate buttons (only targets buttons inside column cells)
st.markdown("""
<style>
[data-testid="column"] [data-testid="stBaseButton-primary"] p {
    font-size: 1.6rem !important;
    line-height: 1.1 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
PAGE_SIZE = "A4"
PADDING_MM = 5.0

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
    type=["jpg", "jpeg", "png", "webp"],
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
            st.session_state.rotations = [0] * len(new_images)
            st.session_state.file_sig = current_sig
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

# ── STEP 2 — Preview ─────────────────────────────────────────────────────────
if st.session_state.images:
    image_count = len(st.session_state.images)
    layout = resolve_layout("Auto", image_count)

    st.divider()
    st.subheader("2 · Preview")

    if st.session_state.preview_img is None:
        with st.spinner("Generating preview…"):
            st.session_state.preview_img = create_preview(
                _rotated_images(),
                layout,
                PAGE_SIZE,
                PADDING_MM,
            )

    st.image(
        st.session_state.preview_img,
        caption=f"{layout.name} · {PAGE_SIZE}",
        width="stretch",
    )

# ── STEP 3 — Generate & Download ─────────────────────────────────────────────
    st.divider()
    st.subheader("3 · Download PDF")

    if st.button("Generate PDF", type="primary", width="stretch"):
        with st.spinner("Building PDF…"):
            st.session_state.pdf_bytes = generate_pdf(
                _rotated_images(),
                layout,
                PAGE_SIZE,
                PADDING_MM,
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
