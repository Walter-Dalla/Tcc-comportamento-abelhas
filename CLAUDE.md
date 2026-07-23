# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a TCC (Brazilian undergraduate thesis) research tool for analyzing insect (bee) behavior from
dual-camera video. Two synchronized video feeds — "top" and "side" — are combined to reconstruct an
insect's 3D position (x, y, z) over time inside a box. From that route it derives speed, time spent near
the box borders/glass, and exports the result as JSON, a 3D route plot, and a PDF report.

See `README.md` for the full goal list and roadmap (in Portuguese). Key point from it: the current
pipeline is a proof-of-concept validated against mockup (non-glass) footage — real-world perspective
distortion and glass interference are known unaddressed problems, and only a single insect is tracked at
a time.

## Running the app

```
python __init__.py
```

This opens a Tkinter desktop GUI (`src/Modules/InterfaceModule/mainUI.py`) — there is no CLI/headless mode.

There are no tests, linter, or CI configuration in this repo.

## Dependencies

`requirements.txt` is UTF-16 encoded (BOM) — a plain read/grep on it will show garbled bytes; decode as
UTF-16 or edit through a tool that respects the encoding. Its listed packages: `numpy`, `opencv-python`,
`pillow`, `setuptools`, `six`, `wheel`.

Note it is **incomplete**: the code also imports `pandas` and `matplotlib` (`ExportModule/plotRoute.py`)
and `xhtml2pdf` (`ExportModule/pdfFactory.py`), none of which are pinned in `requirements.txt`. Install
these manually if PDF export or route plotting is exercised.

## Architecture

### GUI shell: one root window, many swapped frames

`MainInterface` (`src/Modules/InterfaceModule/mainUI.py`) creates every screen as a `tk.Frame` under a
single `tk.Tk()` root at startup, then swaps between them with `show_frame()` (`src/utils/interfaceUtils.py`,
just `tkraise()` + `grid()`) instead of opening new windows. The frames are:

- `MainConfigurationInterface` — the hub screen: select/save named analysis profiles, pick video files,
  jump into perspective/border configuration, kick off processing, and export.
- `PerspectiveUi` (one instance per camera: top/side) — click 4 corners on the first video frame to define
  a homography for perspective-warping that camera's footage.
- `BorderUi` (one instance per camera) — drag a rectangle's corners to mark the "border/glass" region used
  later for border-dwell-time metrics.
- `RecordWebcamVideoUI` — drives synchronized dual-webcam recording (see below) instead of using
  pre-recorded files.

Screens that need to load a video when shown implement a `startUp(videoPath)` method; `MainInterface`
invokes it on a daemon background thread (`run_background_tasks`) so the Tkinter mainloop stays responsive.

Per-profile configuration (video paths, perspective points, border points, box dimensions in cm) is
persisted to `cache/configs.json` (gitignored) via `ExportModule/jsonUtils.py`.

### Dual-webcam recording

`ExportModule/recordVideo.py` (`start_webcams`) spawns one thread per camera (indices 0 and 1), synced via
a shared `threading.Event` and independently gated by `start_recording` events so both feeds begin writing
frames on the same tick. Live preview frames are pushed through `Queue`s and pulled by
`recordWebcamController.py` / `RecordWebcamVideoUI` for on-screen display. Output lands in `./records/`.

### Basic processing pipeline (per analysis run)

Entry point: `process_basic_modules` in `src/Modules/BasicModule/processVideoModule.py`, triggered from the
"Processar video" button in `MainConfigurationInterface`.

1. Top and side videos are each run through `process_video()` **in parallel** via
   `concurrent.futures.ThreadPoolExecutor`.
2. `perspectiveModule.process_perspective` warps every frame using the 4 points picked in `PerspectiveUi`,
   then converts to grayscale.
3. `backgroundRemoveModule.remove_background` builds a max-intensity background image from sampled frames,
   diffs each frame against it, thresholds, finds the largest contour, and takes its centroid as the
   insect's per-frame pixel position (returns `(-1, -1)` when nothing is detected).
4. `routeAnalizer.route_module` merges the two camera's positions frame-by-frame: `(x, y)` from the top
   camera, `z` from the side camera's second coordinate.
5. `BasicModule/utils/getData.py` computes a `pixel_to_cm_ratio` (median of three box-dimension-based
   estimates) and records box dimensions in both cm and px.
6. Result is written to `./cache/outputs/<profile_name>.json` (gitignored) via `jsonUtils`.

### Metadata module system (plugin-style, dynamically loaded)

`src/Modules/MetadataModule/modulesInvoker.py::execute_metadata_module_calls` loads the processed JSON for
a profile, then **dynamically imports every `.py` file in the top-level `./MetadataModule/` directory**
(not `src/Modules/MetadataModule/`) via `importlib`, and calls each module's `module_call(data)` if
present, threading the same `data` dict through all of them before re-saving it. This is how
`averageSpeed`/`speed`/`distanceTotal` (from `borderModule.py`'s `module_call`) and `time_border_x/y/z`
(from `speedModule.py`'s `module_call`) get added to the output JSON.

**Important quirk**: `src/Modules/MetadataModule/borderModule.py` and `speedModule.py` are near-duplicates
of the root-level `MetadataModule/borderModule.py` and `speedModule.py`, but only the root-level
`./MetadataModule/` directory is actually scanned at runtime. Adding a new metadata module means dropping a
file with a `module_call(data)` function into the root `MetadataModule/` folder, not the `src` one — treat
the `src` copies as legacy/dead unless you confirm otherwise before editing them.

### Export

- `ExportModule/plotRoute.py` — renders the merged 3D route with `matplotlib` (animated or static;
  `(-1,-1,-1)` points are treated as gaps and break the line into segments).
- `ExportModule/pdfFactory.py` — renders a fixed HTML summary table (frame count, box dimensions,
  pixel/cm ratio, fps, border dwell times) to PDF via `xhtml2pdf`.

## Directory map

- `__init__.py` — app entry point.
- `src/Modules/InterfaceModule/` — all Tkinter screens.
- `src/Modules/BasicModule/` — video → raw route pipeline (perspective, background removal, route merge).
- `src/Modules/ExportModule/` — I/O: JSON persistence, folder helpers, video open/record, plotting, PDF.
- `src/Modules/MetadataModule/modulesInvoker.py` — dynamic plugin loader (loads from root `MetadataModule/`, see above).
- `MetadataModule/` — the actual plugin directory scanned at runtime (currently `borderModule.py`, `speedModule.py`).
- `src/utils/` — small shared helpers (frame switching, legacy point/object conversion in `pointUtils.py`).
- `cache/`, `records/` — gitignored runtime output (per-profile JSON, exported videos); created on demand.
