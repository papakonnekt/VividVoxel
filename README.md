# VividVoxel

A small, dependency-light Python tool that turns an uploaded **RGB image**
into everything needed to 3D-print a **CMY lithophane** -- a back-lit,
multi-colour photo that reveals the image through the local thickness of
five stacked colour layers.

VividVoxel produces:

* the three **Cyan / Magenta / Yellow thickness channels** (NumPy / PNG)
* a flat **base-plate STL** (default 0.6 mm thick, `numpy-stl`)
* three **CMY color-layer STLs** -- one per ink -- each with a flat bottom
  and a heightmap top, capped at **0.5 mm** of thickness per layer
* a **lithotop STL** whose per-pixel height is driven by the luminance of
  the original image, providing shadows and highlights

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
```

The five STL files are written with **numbered, slicer-friendly names**
so Bambu Studio, PrusaSlicer, OrcaSlicer, ... load them in the right
order and stack them on top of each other:

| #  | File                  | Layer                                          |
| -- | --------------------- | ---------------------------------------------- |
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

Dependencies: **Pillow ≥ 9**, **NumPy ≥ 1.23**, **numpy-stl ≥ 3**.

---

## Quick start

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
| `2_Cyan.stl`                      | Cyan color layer (flat bottom, heightmap top, ≤ 0.5 mm) |
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
  floating-point precision.

Programmatically you can assert the same property with either:

```python
result.verify_alignment()              # returns bounds dict, raises on mismatch
# or, with arbitrary meshes:
vividvoxel.verify_xy_alignment({"a": mesh_a, "b": mesh_b, ...})
```

(The current module is published under its original name `lithophane_cmy`
for backward compatibility -- the public functions are
`lithophane_cmy.verify_xy_alignment` and
`lithophane_cmy.LithophaneResult.verify_alignment`.)

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
    base_thickness_mm=0.6,         # flat base plate thickness
    max_cmy_thickness_mm=0.5,      # CAP on per-layer CMY thickness
    lithotop_min_mm=0.4,
    lithotop_max_mm=2.4,
    preserve_aspect=True,
)

# Verify alignment BEFORE saving -- raises if meshes disagree.
result.verify_alignment()

C, M, Y = result.channels         # each: numpy.ndarray (H, W), float32 in [0, 1]
L       = result.luminance        # (H, W) float32 in [0, 1]
z_top   = result.lithotop_z       # (H, W) float32 in mm

result.base_stl                    # numpy-stl Mesh, 12 triangles
result.cyan_layer_stl              # numpy-stl Mesh, heightmap on top of base
result.magenta_layer_stl           # numpy-stl Mesh, heightmap on top of cyan
result.yellow_layer_stl            # numpy-stl Mesh, heightmap on top of magenta
result.lithotop_stl                # numpy-stl Mesh, heightmap on top of yellow

save_preview(result, "output", base_name="my_lithophane")
save_stls(result, "output")        # writes 1_Base_White.stl ... 5_Top_White.stl
```

`LithophaneResult` exposes:

* `result.cyan`, `result.magenta`, `result.yellow` — `(H, W)` `float32`
  in `[0, 1]`
* `result.rgb_normalized` — `(H, W, 3)` `float32` in `[0, 1]`
* `result.luminance` — `(H, W)` `float32` in `[0, 1]`
* `result.lithotop_z` — `(H, W)` `float32`, top-Z in **mm**
* `result.base_stl`, `result.cyan_layer_stl`, `result.magenta_layer_stl`,
  `result.yellow_layer_stl`, `result.lithotop_stl` — `numpy-stl` `Mesh` objects
* `result.cmy_layers` — dict with the three CMY layer STLs
* `result.verify_alignment()` — assert that all 5 STLs share X/Y origin
* `result.width_mm`, `result.height_mm`, `result.base_thickness_mm`,
  `result.max_cmy_thickness_mm`, `result.lithotop_min_mm`,
  `result.lithotop_max_mm`, `result.px_per_mm`, `result.mesh_px_per_mm`
* `result.summary()` — human-readable multi-line summary

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
Per-pixel thickness is **capped at `max_cmy_thickness_mm`** (default
**0.5 mm**):

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
                         [--demo]
                         [image]
```

When `--base-name` is **not** given, the STLs are written with the
slicer-friendly numbered names (`1_Base_White.stl`, `2_Cyan.stl`, ...).
Pass `--base-name foo` to prepend a prefix (e.g. `foo_1_Base_White.stl`)
so multiple lithophanes can coexist in one output directory.

---

## License

MIT — see the source headers.  Pull requests welcome.