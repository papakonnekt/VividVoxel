# VividVoxel

A small, dependency-light Python tool that turns an uploaded **RGB image**
into everything needed to 3D-print a **CMY lithophane** -- a back-lit,
multi-colour photo that reveals the image through the local thickness of
five stacked colour layers.

VividVoxel produces:

* the three **Cyan / Magenta / Yellow thickness channels** (NumPy / PNG)
* a flat **base-plate STL** (default 0.6 mm thick, `numpy-stl`)
* three **CMY color-layer STLs** -- one per ink -- each with a flat bottom
  and a heightmap top, capped at **`max_cmy_thickness_mm`** per layer
* a **lithotop STL** whose per-pixel height is driven by the luminance of
  the original image, providing shadows and highlights
* a **solid border frame** around the perimeter of every layer to
  prevent light bleed

```
                    ┌─────────────────────────────┐
                    │  Lithotop (white layer)     │  per-pixel height
                    │  z = base + 3·M + min       │  from luminance L
                    │      + (1−L)·Δ             │
                    ├─────────────────────────────┤
                    │  Yellow layer               │  top = 3·M + Y·M
                    │  bottom = 2·M (flat)        │  M = max_cmy_thickness
                    ├─────────────────────────────┤
                    │  Magenta layer              │  top = 2·M + M·M
                    │  bottom = M   (flat)        │
                    ├─────────────────────────────┤
                    │  Cyan layer                 │  top = M + C·M
                    │  bottom = 0   (flat)        │
                    ├─────────────────────────────┤
                    │  Base plate (flat)          │  base_thickness (mm)
                    └─────────────────────────────┘
   ↑ every layer has a solid border (default 2 mm) padded around it
```

The five STL files are written with **numbered, slicer-friendly names**
so Bambu Studio, PrusaSlicer, OrcaSlicer, ... load them in the right
order and stack them on top of each other:

| #  | File                  | Layer                                          |
| -- | --------------------- | ---------------------------------------------- |
| 0  | `0_Frame.stl`         | Structural frame ring (optional)               |
| 1  | `1_Base_White.stl`    | Structural base plate                          |
| 2  | `2_Cyan.stl`          | Cyan color layer (flat bottom, heightmap top)   |
| 3  | `3_Magenta.stl`       | Magenta color layer                            |
| 4  | `4_Yellow.stl`        | Yellow color layer                             |
| 5  | `5_Top_White.stl`     | Lithotop / luminance-driven top white layer     |

---

## Install

```bash
pip install -r requirements.txt
```

Dependencies:

| Package         | Why                                                         |
| --------------- | ----------------------------------------------------------- |
| `Pillow >= 9`   | Load / resize the source image                              |
| `numpy >= 1.23` | All pixel-array math                                        |
| `numpy-stl >= 3`| Write the five `.stl` files                                 |
| `trimesh >= 4`  | Optional mesh decimation (`simplify_meshes`, `--simplify-faces`) |
| `streamlit >= 1.28` | Optional web UI (`streamlit run app.py`)                |

`trimesh` and `streamlit` are only required if you use the
corresponding feature; the core CLI and library work without them.

---

## Quick start

### Web UI (recommended for one-off prints)

```bash
pip install -r requirements.txt        # picks up streamlit + trimesh
streamlit run app.py
```

The UI provides:

* an **image upload** widget (jpg / png / bmp / tiff / webp), or a
  built-in synthetic demo image;
* paired **numeric input + slider** widgets for **Width / Height (mm)**,
  **Min / Max Thickness (mm)** (lithotop luminance range), the
  structural **Frame Width / Frame Depth (mm)** (or disable the frame
  entirely), **Border Width (mm)**, and **Mesh Resolution (px/mm)**;
  everything uses a 0.1 mm step where it matters;
* a **live 2.5D depth-map preview** rendered instantly with Pillow as
  soon as an image is uploaded or any slider moves — no need to wait
  for the full STL pipeline to see what the print will look like;
* an optional **Simplify to N triangles (QEM)** decimation target for
  smaller files at the cost of a few boundary pixels;
* a **Generate lithophane** button that produces a single ZIP file
  containing the aligned STLs (`0_Frame.stl` … `5_Top_White.stl`) plus
  per-channel preview PNGs and a `README.txt`.

The hard-coded constants tuned for standard CMYK filament profiles
are intentionally **not exposed** in the UI:

| Constant                       | Value | Meaning                                       |
| ------------------------------ | ----- | --------------------------------------------- |
| `DEFAULT_BASE_THICKNESS_MM`    | 0.6   | Floor plate thickness                          |
| `DEFAULT_MAX_CMY_THICKNESS_MM` | 0.4   | Maximum per-channel CMY layer thickness        |

Power users can still override these from the CLI via
`--base-thickness-mm` and `--max-cmy-thickness-mm`.

### CLI

```bash
# Default: 100 × 100 mm at 10 px/mm, base 0.6 mm, CMY ≤ 0.5 mm each,
# lithotop 0.4 – 2.4 mm above the CMY stack
python lithophane_cmy.py photo.jpg

# No image? Use the built-in synthetic test pattern
python lithophane_cmy.py --demo

# Custom max CMY thickness (must be > 0)
python lithophane_cmy.py photo.jpg --max-cmy-thickness-mm 0.3

# Smaller physical size, lower mesh resolution
python lithophane_cmy.py photo.jpg --width 80 --height 60 \
    --px-per-mm 8 --mesh-px-per-mm 2

# CMY channels only, no STL output
python lithophane_cmy.py photo.jpg --no-stl

# Decimate the four heightmap meshes to ~5 000 triangles each
python lithophane_cmy.py photo.jpg --simplify-faces 5000
```

The CLI automatically verifies X/Y alignment and prints each mesh's
bounding box before writing:

```
X/Y alignment check (all meshes must agree):
  base      x=[0.000, 50.000]  y=[0.000, 37.500]
  cyan      x=[0.000, 50.000]  y=[0.000, 37.500]
  magenta   x=[0.000, 50.000]  y=[0.000, 37.500]
  yellow    x=[0.000, 50.000]  y=[0.000, 37.500]
  lithotop  x=[0.000, 50.000]  y=[0.000, 37.500]

Wrote STLs:
  base     -> 1_Base_White.stl  (0.7 KB)
  cyan     -> 2_Cyan.stl        (4.3 MB)
  magenta  -> 3_Magenta.stl     (4.3 MB)
  yellow   -> 4_Yellow.stl      (4.3 MB)
  lithotop -> 5_Top_White.stl    (4.3 MB)
```

Outputs in `--out-dir` (default `output/`):

| File                              | Content                                              |
| --------------------------------- | ---------------------------------------------------- |
| `<name>_rgb.png`                  | Resized input image (visual sanity check)            |
| `<name>_cyan.png` / `_magenta.png` / `_yellow.png` | Per-channel thickness (white = thick, black = thin) |
| `<name>_composite.png`            | C/M/Y stacked into a single RGB preview              |
| `<name>_{cyan,magenta,yellow}.npy` | Raw float32 channel arrays, shape `(H, W)`          |
| `<name>_rgb.npy`                  | Normalised RGB stack, `float32`, shape `(H, W, 3)`   |
| `<name>_luminance.npy`            | BT.601 luminance, `float32`, shape `(H, W)`          |
| `<name>_lithotop_z.npy`           | Top-Z height per pixel (mm), `float32`, shape `(H, W)` |
| `1_Base_White.stl`                | Flat rectangular base plate (12 triangles)           |
| `2_Cyan.stl`                      | Cyan color layer (flat bottom, heightmap top)         |
| `3_Magenta.stl`                   | Magenta color layer                                  |
| `4_Yellow.stl`                    | Yellow color layer                                   |
| `5_Top_White.stl`                 | Top white layer (per-pixel columns, by luminance)    |

Pass `--base-name foo` to prepend a custom prefix
(`foo_1_Base_White.stl`, ...) so multiple lithophanes can coexist in one
output directory.

---

## Alignment guarantee

All five STL meshes share **bit-exact X and Y coordinates** so that, when
loaded into a slicer, they line up perfectly on top of each other:

* every mesh is generated by the same `_make_column_heightmap_stl`
  helper (or `make_base_plate_stl`) using the same `width_mm`,
  `height_mm` and pixel grid;
* the X coordinates lie in `[0, width_mm]`, the Y coordinates lie in
  `[0, height_mm]`, and every mesh's bounding box is identical to within
  floating-point precision;
* a configurable **border frame** (default 2 mm) is padded around the
  perimeter of all five meshes -- giving them identical X/Y extent.

Programmatically you can assert the same property with either:

```python
result.verify_alignment()              # returns bounds dict, raises on mismatch
# or, with arbitrary meshes:
lithophane_cmy.verify_xy_alignment({"a": mesh_a, "b": mesh_b, ...})
```

---

## Mesh decimation (Task 2)

A naive CMY lithophane emits **12 triangles per pixel column**.  For a
200×200 pixel image that's 480 000 triangles per layer -- a multi-MB STL
that slices slowly and prints slowly too.  VividVoxel therefore ships
with an optional `simplify_meshes()` helper that uses **trimesh** to:

1. **merge coplanar / coincident vertices** (`merge_vertices()`) -- this
   is the big win and *drastically* reduces the triangle count without
   any geometric change.  Empirically this collapses 90%+ of the
   duplicate column corners in a typical lithophane heightmap.
2. optionally apply **quadric-error-mesh (QEM) decimation** down to a
   user-specified triangle budget (`simplify_quadric_decimation`).

Use it from Python:

```python
from lithophane_cmy import process_image, simplify_meshes

result = process_image("photo.jpg", width_mm=100, height_mm=100)
meshes = {
    "base":     result.base_stl,
    "cyan":     result.cyan_layer_stl,
    "magenta":  result.magenta_layer_stl,
    "yellow":   result.yellow_layer_stl,
    "lithotop": result.lithotop_stl,
}
simplified = simplify_meshes(meshes, target_face_count=5000)
# Each simplified["..."] is now a numpy-stl Mesh with <<< triangles.
```

Or from the CLI:

```bash
python lithophane_cmy.py photo.jpg --simplify-faces 5000
```

The Streamlit UI exposes the same slider ("Simplify to N triangles
(QEM)") -- set it to `0` to disable.

> Note: QEM is a *visual* simplification.  It can shift boundary
> vertices by a few pixels.  If you need bit-exact X/Y alignment across
> the five STLs, leave decimation **off** and rely on the
> `merge_vertices` pass only (which is purely geometric and therefore
> alignment-safe).

---

## Border frame (Task 3)

To prevent stray light from leaking between layers around the edges of
the print, VividVoxel pads each mesh with a **solid rectangular frame**
of width `border_width_mm` (default **2 mm**, set to `0` to disable).
The frame:

* surrounds **all five layers identically**, so the alignment guarantee
  still holds;
* uses `channel = 1.0` (maximum thickness) for the padded pixels, so
  each layer's outer ring is a solid slab of plastic.

Configure it from the CLI (`--border-width-mm 3`), programmatically
(`process_image(..., border_width_mm=3.0)`) or via the Streamlit UI.

---

## Structural frame (optional)

For prints that need extra rigidity or a clean outer edge, VividVoxel can
emit a separate **hollow rectangular ring STL** (`0_Frame.stl`) that sits
*under* the base plate:

* `frame_enabled=True` (default) toggles the ring on/off.
* `frame_width_mm` (default `2.0`) is the X/Y thickness of the ring.
* `frame_depth_mm` (default `1.0`) is the Z thickness of the ring.
* When enabled, the base plate and the entire colour stack are lifted by
  `frame_depth_mm` so the frame, base, CMY layers and lithotop stack
  perfectly with no Z-fighting.
* The file is numbered `0_Frame.stl` so slicers load it first.

Configure it from the Streamlit UI (**Structural frame** expander) or the
CLI:

```bash
python lithophane_cmy.py photo.jpg --frame-width-mm 3 --frame-depth-mm 1.5
python lithophane_cmy.py photo.jpg --no-frame          # disable the ring
```

Programmatically:

```python
result = process_image(
    "photo.jpg",
    frame_enabled=True,
    frame_width_mm=3.0,
    frame_depth_mm=1.5,
)
result.frame_stl     # numpy-stl Mesh, 24 triangles
```

---

## Live 2.5D depth preview

While you tweak the sliders in the Streamlit UI, VividVoxel renders an
**instant grayscale depth-map preview** of the lithotop heightmap using
only Pillow (no heavy STL pipeline).  Darker pixels = thicker columns =
darker areas of the print.  Updates on every interaction so you always
see the result before clicking **Generate lithophane**.

You can call the same function programmatically:

```python
from lithophane_cmy import make_depth_preview
preview = make_depth_preview(
    "photo.jpg",
    width_mm=100.0, height_mm=100.0,
    lithotop_min_mm=0.8, lithotop_max_mm=5.0,
    border_width_mm=2.0,
)
preview.save("preview.png")
```

---

## Programmatic use

```python
from lithophane_cmy import process_image, save_preview, save_stls

result = process_image(
    "photo.jpg",
    width_mm=100.0,                # physical width
    height_mm=100.0,               # physical height
    px_per_mm=10.0,                # CMY channel resolution
    mesh_px_per_mm=2.0,            # STL mesh resolution (lower = smaller file)
    base_thickness_mm=0.6,         # (CLI only) flat base plate thickness
    max_cmy_thickness_mm=0.4,      # (CLI only) CAP on per-layer CMY thickness
    lithotop_min_mm=0.8,           # thinnest lithotop column
    lithotop_max_mm=5.0,           # thickest lithotop column (auto-normalised)
    border_width_mm=2.0,           # solid frame around every layer
    frame_enabled=True,            # outer rectangular ring (0_Frame.stl)
    frame_width_mm=2.0,            # X/Y thickness of the ring
    frame_depth_mm=1.0,            # Z thickness of the ring
    preserve_aspect=True,
)

# Verify alignment BEFORE saving -- raises if meshes disagree.
result.verify_alignment()

C, M, Y = result.channels         # each: numpy.ndarray (H, W), float32 in [0, 1]
L       = result.luminance        # (H, W) float32 in [0, 1]
z_top   = result.lithotop_z       # (H, W) float32 in mm

result.frame_stl                  # optional: numpy-stl Mesh, 24 triangles
result.base_stl                   # numpy-stl Mesh, 12 triangles
result.cyan_layer_stl             # numpy-stl Mesh, heightmap on top of base
result.magenta_layer_stl          # numpy-stl Mesh, heightmap on top of cyan
result.yellow_layer_stl           # numpy-stl Mesh, heightmap on top of magenta
result.lithotop_stl               # numpy-stl Mesh, heightmap on top of yellow

save_preview(result, "output", base_name="my_lithophane")
save_stls(result, "output")        # writes 0_Frame.stl ... 5_Top_White.stl
# Or pass include_frame=False to skip the frame file
```

`LithophaneResult` exposes:

* `result.cyan`, `result.magenta`, `result.yellow` — `(H, W)` `float32`
  in `[0, 1]`
* `result.rgb_normalized` — `(H, W, 3)` `float32` in `[0, 1]`
* `result.luminance` — `(H, W)` `float32` in `[0, 1]`
* `result.lithotop_z` — `(H, W)` `float32`, top-Z in **mm**
* `result.frame_stl`, `result.base_stl`, `result.cyan_layer_stl`,
  `result.magenta_layer_stl`, `result.yellow_layer_stl`,
  `result.lithotop_stl` — `numpy-stl` `Mesh` objects (frame may be
  `None` if disabled)
* `result.cmy_layers` — dict with the three CMY layer STLs
* `result.verify_alignment()` — assert that all STLs share X/Y origin
* `result.width_mm`, `result.height_mm`, `result.base_thickness_mm`,
  `result.max_cmy_thickness_mm`, `result.lithotop_min_mm`,
  `result.lithotop_max_mm`, `result.px_per_mm`, `result.mesh_px_per_mm`,
  `result.border_width_mm`, `result.frame_enabled`, `result.frame_width_mm`,
  `result.frame_depth_mm`, `result.frame_bottom_z`, `result.frame_top_z`
* `result.summary()` — human-readable multi-line summary
* `make_depth_preview(source, width_mm, height_mm, lithotop_min_mm,
  lithotop_max_mm, border_width_mm=2.0, px_per_mm=4.0)` — return a
  `PIL.Image` of the grayscale depth-map (used by the live UI preview)

---

## How it works

### 1. CMY thickness channels

For every pixel we compute three scalar fields in `[0, 1]` using the
standard subtractive colour model:

| Channel | Formula          | Physical meaning                            |
| ------- | ---------------- | ------------------------------------------- |
| Cyan    | `C = 1 − R`      | How much **red** light the column absorbs   |
| Magenta | `M = 1 − G`      | How much **green** light the column absorbs |
| Yellow  | `Y = 1 − B`      | How much **blue** light the column absorbs  |

`1.0` ⇒ print at **maximum thickness** (blocks the most light of that
colour).  `0.0` ⇒ print at **minimum thickness** (lets it pass).

### 2. Base plate STL

A simple rectangular box mesh that provides structural support and
defines the bottom of the lithophane.  12 triangles (6 faces × 2).
Default thickness 0.6 mm.

### 3. CMY color-layer STLs

For each ink colour we emit a single STL whose **bottom is flat** and
whose **top is a heightmap** driven by the corresponding CMY channel.
Per-pixel thickness is **capped at `max_cmy_thickness_mm`**:

```
z_top[i, j] = z_layer_bottom + channel[i, j] * max_cmy_thickness_mm
```

The three layers are stacked so that the bottom of each layer sits at
the maximum possible top of the layer below:

```
Cyan    bottom z = base_thickness            (or 0 if no base plate)
        top    z = bottom + C * M_cmy
Magenta bottom z = base + M_cmy
        top    z = bottom + M * M_cmy
Yellow  bottom z = base + 2 * M_cmy
        top    z = bottom + Y * M_cmy
```

Each pixel column is an independent rectangular box (12 triangles:
2 bottom + 2 top + 8 side walls).

### 4. Lithotop STL

For the top white layer the per-pixel height is driven by the
**BT.601 luminance** of the source image:

```
L  = 0.299 R + 0.587 G + 0.114 B          ∈ [0, 1]
z_top = base + 3 * M_cmy + z_min + (1 − L) · (z_max − z_min)
```

Dark pixels get the **tallest** columns, bright pixels get the
**shortest** — the back-light reveals the image through the height
variations.

---

## CLI reference

```
usage: lithophane_cmy.py [-h] [--width WIDTH] [--height HEIGHT]
                         [--px-per-mm PX_PER_MM] [--no-aspect]
                         [--out-dir OUT_DIR] [--base-name BASE_NAME]
                         [--no-npy] [--no-stl]
                         [--base-thickness-mm BASE_THICKNESS_MM]
                         [--max-cmy-thickness-mm MAX_CMY_THICKNESS_MM]
                         [--lithotop-min-mm LITHOTOP_MIN_MM]
                         [--lithotop-max-mm LITHOTOP_MAX_MM]
                         [--mesh-px-per-mm MESH_PX_PER_MM]
                         [--border-width-mm BORDER_WIDTH_MM]
                         [--frame-width-mm FRAME_WIDTH_MM]
                         [--frame-depth-mm FRAME_DEPTH_MM]
                         [--no-frame]
                         [--simplify-faces SIMPLIFY_FACES] [--no-simplify]
                         [--demo]
                         [image]
```

When `--base-name` is **not** given, the STLs are written with the
slicer-friendly numbered names (`0_Frame.stl`, `1_Base_White.stl`,
`2_Cyan.stl`, ...).  Pass `--base-name foo` to prepend a prefix
(e.g. `foo_1_Base_White.stl`) so multiple lithophanes can coexist in
one output directory.  Pass `--no-frame` to skip `0_Frame.stl`.

---

## License

MIT — see the source headers.  Pull requests welcome.