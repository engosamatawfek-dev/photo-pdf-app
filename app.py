"""
Photo PDF Maker — Streamlit UI

Upload photos from your phone, pick a layout, preview, and download as a PDF.

Evidence: Streamlit 1.58.0 API
Source: https://docs.streamlit.io/develop/api-reference
Verified: 2026-06-12
"""

from datetime import datetime

import streamlit as st
from PIL import Image

from image_processor import create_preview, load_and_validate, resize_to_max
from layout_calculator import MAX_PHOTOS, PRESET_NAMES, resolve_layout
from pdf_engine import generate_pdf

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Photo PDF Maker",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("📄 Photo PDF Maker")
st.caption("Upload photos → choose layout → download PDF")

# ── Session state defaults ────────────────────────────────────────────────────
if "images" not in st.session_state:
    st.session_state.images: list[Image.Image] = []
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes: bytes | None = None
if "preview_img" not in st.session_state:
    st.session_state.preview_img: Image.Image | None = None


def _reset_output() -> None:
    st.session_state.pdf_bytes = None
    st.session_state.preview_img = None


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
        count = len(new_images)
        if count > MAX_PHOTOS:
            st.warning(
                f"You uploaded {count} photos. Only the first {MAX_PHOTOS} will be included in the PDF."
            )
        else:
            st.success(f"{count} photo{'s' if count != 1 else ''} ready.")

        # Show small thumbnails in a row
        thumb_cols = st.columns(min(count, 5))
        for i, img in enumerate(new_images[:5]):
            with thumb_cols[i]:
                st.image(img, use_container_width=True)
        if count > 5:
            st.caption(f"… and {count - 5} more")

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

    custom_cols, custom_rows = 2, 3
    if preset == "Custom":
        cc, cr = st.columns(2)
        with cc:
            custom_cols = st.number_input("Columns", min_value=1, max_value=5, value=2, on_change=_reset_output)
        with cr:
            custom_rows = st.number_input("Rows", min_value=1, max_value=6, value=3, on_change=_reset_output)

    image_count = len(st.session_state.images)
    layout = resolve_layout(preset, image_count, int(custom_cols), int(custom_rows))

    if image_count > layout.capacity:
        st.warning(
            f"This layout fits {layout.capacity} photos. "
            f"Your last {image_count - layout.capacity} photo(s) will not appear."
        )

# ── STEP 3 — Preview ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("3 · Preview")

    if st.session_state.preview_img is None:
        with st.spinner("Generating preview…"):
            st.session_state.preview_img = create_preview(
                st.session_state.images,
                layout,
                page_size,
                float(padding_mm),
            )

    st.image(
        st.session_state.preview_img,
        caption=f"{layout.name} · {page_size} · {padding_mm}mm padding",
        use_container_width=True,
    )

# ── STEP 4 — Generate & Download ─────────────────────────────────────────────
    st.divider()
    st.subheader("4 · Download PDF")

    if st.button("Generate PDF", type="primary", use_container_width=True):
        with st.spinner("Building PDF…"):
            st.session_state.pdf_bytes = generate_pdf(
                st.session_state.images,
                layout,
                page_size,
                float(padding_mm),
            )

    if st.session_state.pdf_bytes:
        filename = f"photos_{datetime.now():%Y-%m-%d_%H-%M-%S}.pdf"
        st.download_button(
            label="⬇ Download PDF",
            data=st.session_state.pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
        )
        size_kb = len(st.session_state.pdf_bytes) / 1024
        st.caption(f"PDF size: {size_kb:.0f} KB · {filename}")
