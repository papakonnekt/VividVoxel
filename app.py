"""
VividVoxel Streamlit web interface
==================================

Upload an image, set the dimensions and structural-frame parameters in the
sidebar, watch a live 2.5D depth-map preview update as you tweak the
sliders, then download a ZIP containing the aligned STLs ready to load
into Bambu Studio / PrusaSlicer / OrcaSlicer.

Run with:

    streamlit run app.py

The script auto-detects whether `streamlit` is installed and exits with
a clear error message if not.
"""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

# ---- Optional dependency check ----------------------------------------
try:
    import streamlit as st
except ImportError:                                      # pragma: no cover
    sys.stderr.write(
        "streamlit is required for the web UI.\n"
        "Install it with:  pip install streamlit\n"
    )
    sys.exit(1)

import numpy as np
from PIL import Image

from lithophane_cmy import (
    DEFAULT_BASE_THICKNESS_MM,
    DEFAULT_BORDER_WIDTH_MM,
    DEFAULT_FRAME_DEPTH_MM,
    DEFAULT_FRAME_ENABLED,
    DEFAULT_FRAME_WIDTH_MM,
    DEFAULT_LITHOTOP_MAX_MM,
    DEFAULT_LITHOTOP_MIN_MM,
    DEFAULT_MAX_CMY_THICKNESS_MM,
    STL_FILE_NAMES,
    make_demo_image,
    make_depth_preview,
    process_image,
    save_preview,
    save_stls,
    simplify_meshes,
)


# ---- Streamlit page config -------------------------------------------
st.set_page_config(
    page_title="VividVoxel \u2014 CMY Lithophane Maker",
    page_icon="\U0001F308",
    layout="centered",
    initial_sidebar_state="expanded",
)


# ---- UI helpers --------------------------------------------------------
def _numeric_with_slider(
    label: str,
    key: str,
    min_value: float,
    max_value: float,
    value: float,
    step: float,
    help: str = "",
    fmt: str = "%.1f",
):
    """Render a `st.number_input` + `st.slider` pair that share state.

    Streamlit's session_state always mirrors the most recently interacted
    widget, so the two controls stay in sync automatically.  We only
    seed the session-state key on first render; thereafter Streamlit owns
    it.
    """
    num_key = f"num_{key}"
    sld_key = f"sld_{key}"

    # First-render seeding only (avoids the "default + session_state"
    # warning).  Clip the slider value into range in case the caller
    # changed min/max between runs.
    if num_key not in st.session_state:
        st.session_state[num_key] = float(value)
    if sld_key not in st.session_state:
        st.session_state[sld_key] = float(np.clip(value, min_value, max_value))

    col1, col2 = st.columns([1, 2])
    with col1:
        num_val = st.number_input(
            label,
            min_value=float(min_value),
            max_value=float(max_value),
            step=float(step),
            format=fmt,
            key=num_key,
            help=help,
        )
    with col2:
        sld_val = st.slider(
            label,
            min_value=float(min_value),
            max_value=float(max_value),
            step=float(step),
            key=sld_key,
            help=help,
            label_visibility="collapsed",
        )

    # Whichever control the user touched most recently has the latest
    # value in session_state (Streamlit wrote it).  The other control
    # will catch up on the next render.  Return the numeric widget's
    # current value for downstream use.
    return float(num_val)


# ---- Cached resources -------------------------------------------------
@st.cache_data
def _read_demo_png() -> bytes:
    """Return PNG bytes for the built-in demo image."""
    buf = io.BytesIO()
    make_demo_image((640, 480)).save(buf, format="PNG")
    return buf.getvalue()


@st.cache_data(show_spinner=False)
def _depth_preview_png(
    image_bytes: bytes | None,
    use_demo: bool,
    width_mm: float,
    height_mm: float,
    lithotop_min_mm: float,
    lithotop_max_mm: float,
    border_width_mm: float,
) -> bytes:
    """Run the lightweight Pillow depth-preview and return PNG bytes.

    Cached so the preview re-renders instantly when a slider changes but
    does not re-compute when nothing changed.
    """
    if use_demo or not image_bytes:
        img = make_demo_image((640, 480))
    else:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    preview = make_depth_preview(
        img,
        width_mm=float(width_mm),
        height_mm=float(height_mm),
        lithotop_min_mm=float(lithotop_min_mm),
        lithotop_max_mm=float(lithotop_max_mm),
        border_width_mm=float(border_width_mm),
        px_per_mm=4.0,
    )
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return buf.getvalue()


@st.cache_data
def _build_zip(
    image_bytes: bytes,
    width_mm: float,
    height_mm: float,
    lithotop_min_mm: float,
    lithotop_max_mm: float,
    border_width_mm: float,
    mesh_px_per_mm: float,
    simplify_faces: int,
    frame_enabled: bool,
    frame_width_mm: float,
    frame_depth_mm: float,
    use_demo: bool,
) -> bytes:
    """Run the full pipeline and return the output ZIP as bytes."""
    # 1. Load image
    if use_demo:
        img = make_demo_image()
    else:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()

    # 2. Run the pipeline (base thickness / max CMY are hard-coded in the
    #    backend for standard CMYK filament profiles)
    result = process_image(
        img,
        width_mm=width_mm,
        height_mm=height_mm,
        px_per_mm=10.0,                     # CMY channel resolution
        mesh_px_per_mm=mesh_px_per_mm,
        preserve_aspect=True,
        base_thickness_mm=DEFAULT_BASE_THICKNESS_MM,
        max_cmy_thickness_mm=DEFAULT_MAX_CMY_THICKNESS_MM,
        lithotop_min_mm=lithotop_min_mm,
        lithotop_max_mm=lithotop_max_mm,
        border_width_mm=border_width_mm,
        frame_enabled=frame_enabled,
        frame_width_mm=frame_width_mm,
        frame_depth_mm=frame_depth_mm,
    )

    # 3. Optional QEM decimation
    if simplify_faces and simplify_faces > 0:
        meshes = {
            "base":     result.base_stl,
            "cyan":     result.cyan_layer_stl,
            "magenta":  result.magenta_layer_stl,
            "yellow":   result.yellow_layer_stl,
            "lithotop": result.lithotop_stl,
        }
        if result.frame_stl is not None:
            meshes["frame"] = result.frame_stl
        simplified = simplify_meshes(meshes, target_face_count=simplify_faces)
        result.base_stl         = simplified["base"]
        result.cyan_layer_stl   = simplified["cyan"]
        result.magenta_layer_stl= simplified["magenta"]
        result.yellow_layer_stl = simplified["yellow"]
        result.lithotop_stl     = simplified["lithotop"]
        if "frame" in simplified:
            result.frame_stl    = simplified["frame"]

    # 4. Pack everything into a ZIP in memory
    out_buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        save_preview(result, out_dir, base_name="lithophane")
        save_stls(result, out_dir, base_name=None)
        # README with provenance
        readme = (
            "VividVoxel output\n"
            "=================\n\n"
            f"Physical size       : {width_mm} x {height_mm} mm\n"
            f"Min / Max thickness : {lithotop_min_mm} \u2013 {lithotop_max_mm} mm\n"
            f"Border width        : {border_width_mm} mm\n"
            f"Mesh resolution     : {mesh_px_per_mm} px/mm\n"
            f"Structural frame    : "
            f"{'on' if frame_enabled else 'off'}"
            + (
                f"  (width={frame_width_mm} mm, depth={frame_depth_mm} mm)"
                if frame_enabled else ""
            )
            + "\n"
            f"Simplification      : "
            f"{'QEM target=' + str(simplify_faces) if simplify_faces else 'none'}\n\n"
            "STL files:\n"
        )
        for k, v in STL_FILE_NAMES.items():
            readme += f"  - {v}\n"
        (out_dir / "README.txt").write_text(readme)
        # Zip it all up
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(out_dir.iterdir()):
                zf.write(f, f.name)
    out_buf.seek(0)
    return out_buf.getvalue()


# ---- Sidebar: sliders -------------------------------------------------
with st.sidebar:
    st.header("Parameters")

    use_demo = st.checkbox(
        "Use the built-in demo image (no upload needed)",
        value=False,
        help="Generates a colourful gradient so you can try the UI "
             "without uploading anything.",
    )

    physical = st.expander("Physical size", expanded=True)
    with physical:
        width_mm = _numeric_with_slider(
            "Width (mm)", key="width_mm",
            min_value=20.0, max_value=300.0, value=100.0, step=5.0,
            help="Target physical width of the lithophane.",
        )
        height_mm = _numeric_with_slider(
            "Height (mm)", key="height_mm",
            min_value=20.0, max_value=300.0, value=100.0, step=5.0,
            help="Target physical height. Aspect-ratio preserving when "
                 "the source image is non-square.",
        )

    thickness = st.expander("Thickness", expanded=True)
    with thickness:
        lithotop_min_mm = _numeric_with_slider(
            "Min Thickness (mm)", key="min_thickness",
            min_value=0.1, max_value=5.0,
            value=DEFAULT_LITHOTOP_MIN_MM, step=0.1,
            help="Minimum lithotop (top white) layer thickness in mm. "
                 "The image's brightest pixels print at this thickness.",
        )
        # Max thickness must always be >= min + 0.1
        max_min = float(lithotop_min_mm) + 0.1
        default_max = max(float(DEFAULT_LITHOTOP_MAX_MM), max_min)
        lithotop_max_mm = _numeric_with_slider(
            "Max Thickness (mm)", key="max_thickness",
            min_value=max_min, max_value=10.0,
            value=default_max, step=0.1,
            help="Maximum lithotop thickness in mm. The image's darkest "
                 "pixels print at this thickness. Always >= Min + 0.1 mm.",
        )

    frame = st.expander("Structural frame", expanded=False)
    with frame:
        frame_enabled = st.checkbox(
            "Enable structural frame",
            value=bool(DEFAULT_FRAME_ENABLED),
            help="Add a solid rectangular ring around the perimeter of "
                 "every layer.  Sits under the base plate, so it adds "
                 "structural rigidity without affecting the colour stacks.",
        )
        frame_width_mm = _numeric_with_slider(
            "Frame Width (mm)", key="frame_width",
            min_value=0.0, max_value=15.0,
            value=float(DEFAULT_FRAME_WIDTH_MM), step=0.5,
            help="X/Y thickness of the frame ring.  Set 0 to disable.",
        )
        frame_depth_mm = _numeric_with_slider(
            "Frame Depth (mm)", key="frame_depth",
            min_value=0.0, max_value=5.0,
            value=float(DEFAULT_FRAME_DEPTH_MM), step=0.1,
            help="Z thickness of the frame ring.  Set 0 to disable.",
        )

    border = st.expander("Border & mesh", expanded=False)
    with border:
        border_width_mm = _numeric_with_slider(
            "Border Width (mm)", key="border_width",
            min_value=0.0, max_value=15.0,
            value=float(DEFAULT_BORDER_WIDTH_MM), step=0.5,
            help="Border added around the perimeter of every layer to "
                 "prevent light bleed.  0 disables it.",
        )
        mesh_px_per_mm = _numeric_with_slider(
            "Mesh Resolution (px/mm)", key="mesh_res",
            min_value=0.5, max_value=10.0, value=2.0, step=0.5,
            help="STL mesh resolution.  Lower values produce smaller "
                 "files at the cost of detail.  Default 2 px/mm is a "
                 "good compromise for FDM printers.",
        )
        simplify_faces = st.slider(
            "Simplify to N triangles (QEM)",
            min_value=0, max_value=20000, value=0, step=500,
            help="Optional: trimesh quadric-error decimation target. "
                 "0 disables decimation (alignment is bit-exact).  When "
                 "set, QEM may shift boundary vertices by a few pixels.",
        )

    st.markdown("---")
    st.markdown(
        "**VividVoxel** &mdash; a CMY lithophane maker.  "
        "[GitHub](https://github.com/papakonnekt/VividVoxel)"
    )


# ---- Main panel -------------------------------------------------------
st.title("VividVoxel \u2014 CMY Lithophane Maker")
st.markdown(
    "Upload an image, set the dimensions and structural-frame parameters "
    "in the sidebar, and download a ZIP containing the aligned STLs ready "
    "to load into Bambu Studio / PrusaSlicer / OrcaSlicer."
)

st.markdown(
    """
    | #  | File                | Layer |
    | -- | ------------------- | ----- |
    | 0  | `0_Frame.stl`        | Structural frame ring (optional) |
    | 1  | `1_Base_White.stl`  | Base plate |
    | 2  | `2_Cyan.stl`        | Cyan color layer |
    | 3  | `3_Magenta.stl`     | Magenta color layer |
    | 4  | `4_Yellow.stl`      | Yellow color layer |
    | 5  | `5_Top_White.stl`    | Top white (luminance) layer |
    """
)

# ---- Image input ------------------------------------------------------
if use_demo:
    img_bytes = _read_demo_png()
    img = Image.open(io.BytesIO(img_bytes))
    st.subheader("Source image")
    st.image(img, caption="Built-in demo image", width='stretch')
else:
    uploaded = st.file_uploader(
        "Upload an image (JPG / PNG)",
        type=["jpg", "jpeg", "png", "bmp", "tiff", "webp"],
        accept_multiple_files=False,
    )
    if uploaded is None:
        st.info(
            "Upload an image to get started, or tick \"Use the built-in "
            "demo image\" in the sidebar."
        )
        st.stop()
    img_bytes = uploaded.getvalue()
    img = Image.open(io.BytesIO(img_bytes))
    st.subheader("Source image")
    st.image(img, caption=f"Uploaded: {uploaded.name}", width='stretch')

# ---- Instant 2.5D depth preview --------------------------------------
st.subheader("Live 2.5D depth preview")
st.caption(
    "Darker pixels print thicker.  Updates instantly as you change any "
    "slider.  Click **Generate lithophane** below when you're happy."
)
preview_png = _depth_preview_png(
    image_bytes=None if use_demo else img_bytes,
    use_demo=use_demo,
    width_mm=width_mm,
    height_mm=height_mm,
    lithotop_min_mm=lithotop_min_mm,
    lithotop_max_mm=lithotop_max_mm,
    border_width_mm=border_width_mm,
)
st.image(
    Image.open(io.BytesIO(preview_png)),
    caption=(
        f"{width_mm:.1f} x {height_mm:.1f} mm  |  "
        f"thickness {lithotop_min_mm:.1f} \u2013 {lithotop_max_mm:.1f} mm  |  "
        f"border {border_width_mm:.1f} mm"
    ),
    width='stretch',
)

# ---- Generate + download ---------------------------------------------
st.markdown("---")
col1, col2 = st.columns([1, 2])
with col1:
    go = st.button(
        "Generate lithophane",
        type="primary",
        width='stretch',
    )

if go:
    with st.spinner("Building meshes \u2026"):
        try:
            zip_bytes = _build_zip(
                image_bytes=img_bytes,
                width_mm=width_mm,
                height_mm=height_mm,
                lithotop_min_mm=lithotop_min_mm,
                lithotop_max_mm=lithotop_max_mm,
                border_width_mm=float(border_width_mm),
                mesh_px_per_mm=float(mesh_px_per_mm),
                simplify_faces=int(simplify_faces),
                frame_enabled=bool(frame_enabled),
                frame_width_mm=float(frame_width_mm),
                frame_depth_mm=float(frame_depth_mm),
                use_demo=use_demo,
            )
            with col2:
                st.download_button(
                    "Download VividVoxel_output.zip",
                    data=zip_bytes,
                    file_name="VividVoxel_output.zip",
                    mime="application/zip",
                    width='stretch',
                )
            st.success(
                f"Generated {len(zip_bytes) / 1024:.1f} KB ZIP.  "
                "Click **Download VividVoxel_output.zip** to save it."
            )
        except Exception as exc:
            st.error(f"Generation failed: {exc}")
            raise
else:
    st.caption(
        "Click **Generate lithophane** above to produce the aligned STLs."
    )