# Distant-Face Detection — Design

**Status:** implemented (2026-04-26).
**Branch:** `feat/local-compute-split`.
**Owner:** CJ Jutba.

## Problem

Back-row students (8-10 m from the camera in EB226 / EB227 wide-angle
classrooms) were **not being detected** by SCRFD on the on-prem
pipeline, even though the foreground student in the same frame was
detected and recognised reliably (see screenshot in conversation
history dated 2026-04-26 ~11 am).

## Root cause

The pipeline downscaled the camera's pixels twice before SCRFD ever
saw them:

| Stage | Linear loss | Notes |
|---|---|---|
| Reolink sensor → cam-relay (`-c copy`) | 1.0× | no transcode |
| `frame_grabber.py:359` ffmpeg `-vf scale=1280:720` | **0.555×** | gateway-side decode |
| SCRFD letterbox to `det_size=960` | **0.75×** | inside the model |

A 46 px face on the sensor (a head-on student at 6 m) reached SCRFD
as 19 px — below the buffalo_l reliable-detection floor (~25-30 px).
At 8 m the same trace produced 14 px; at 10 m, 12 px.

Optical-floor sanity check: at the Reolink's 4 mm focal length on a
1/2.7" sensor, capturing 2304×1296, **at 6 m a head-on face is ~46 px
wide (88 PPF)**, which is just past the IPVM 80 PPF Recognition floor.
At 10 m it drops to ~28 px (~53 PPF) — below the recognition floor
even at full sensor resolution. Beyond ~10 m is a hardware-only
solution (cropped sub-stream, second tighter-FOV camera).

## Solution — four phases

Each phase is feature-flagged and rolls forward / back independently.

### Phase 1 — Stop throwing pixels away

- Bump `FRAME_GRABBER_WIDTH/HEIGHT` 1280×720 → 1920×1080.
- Bump `INSIGHTFACE_DET_SIZE` 960 → 1280.
- Drop `PROCESSING_FPS` 20 → 10 to absorb the ~1.78× SCRFD cost.
- `INSIGHTFACE_DET_SIZE` change re-runs the static-shape ONNX export
  via `entrypoint.sh` (gateway side) and a new
  `scripts/export-static-models.sh` (host side, called by
  `start-ml-sidecar.sh`).

Effect: a 46 px sensor face arrives at SCRFD as ~35 px instead of 19
px. Cheap, big single jump. 3 file changes.

### Phase 2 — Cropped back-row streams

- `scripts/iams-cam-relay.sh` extended with a `CROPPED_STREAMS` array;
  each entry runs a parallel `ffmpeg -vf crop=...` re-encode targeting
  a new mediamtx path (`eb226-back`, `eb227-back`).
- `deploy/mediamtx.onprem.yml` adds a `~^.+-back$` matcher that keeps
  these streams local (no VPS push).
- New module `app/services/backrow_streams.py` parses
  `BACKROW_CROP_STREAMS` env var into structured entries.
- `app/main.py` lifespan boots a secondary FrameGrabber per
  configured back-row path, registered under
  `app.state.backrow_frame_grabbers[stream_key]`.
- `SessionPipeline` accepts a `backrow_grabber=` param and runs an
  auxiliary detection-only loop (~0.5 fps) feeding the **same**
  `TrackPresenceService`.
- A `_presence_lock` serialises presence-service access between the
  main and back-row loops.

Effect: ~2× pixel density on back-row faces (a 30 px face becomes ~55
px on the cropped 1280×720 view of the upper 60 % of the frame).
Identity dedup happens at user_id; the WS overlay broadcast remains
wide-stream-only (cropped detections feed presence + auto-CCTV-enrol
only).

### Phase 3 — Tiled inference

- New module `app/services/ml/tile_detection.py` providing pure-numpy
  tile geometry (`compute_tile_rects`), letterbox + remap
  (`letterbox_to_square`, `remap_detection`), IOS-NMM merge
  (`greedy_nmm_ios`), and motion-mask helpers
  (`compute_motion_mask`, `tile_intersects_mask`).
- ML sidecar gets a new `POST /detect_tiled` endpoint that takes a
  list of tile rectangles, runs SCRFD on each (each padded to the
  static-shape `det_size` square so CoreML still delegates to the
  ANE), remaps coords, and merges with IOS-NMM.
- `RemoteInsightFaceModel.detect_tiled()` proxies to the sidecar
  endpoint; `InsightFaceModel.detect_tiled()` mirrors the same
  algorithm in-process so both backends present identical APIs.
- `RealtimeTracker._detect_tiled_dispatch()` runs the motion-gating
  step (lazy MOG2 BG model per camera), filters tiles to those
  intersecting motion blobs, and dispatches to the bound model.
  The wide-shot coarse pass is always included, so close-up faces
  never regress when motion-gating excludes their tile.

Algorithm details (SAHI paper arXiv:2202.06934):

- **Greedy NMM with IOS metric:** vanilla IoU-NMS *deletes* legitimate
  seam-clipped detections (two halves of one face have IoU ~0.3 and
  the lower-score half gets suppressed). IOS = Intersection-over-
  Smaller catches "this small box is mostly inside that big box" and
  merges instead of suppressing.
- **Static-shape ANE constraint:** each tile is letterboxed to the
  exact `det_size² ` square the model was exported for, so
  `CoreMLExecutionProvider` keeps delegating. Mixed shapes would fall
  back to CPU silently.
- **Motion gating:** cv2 MOG2 background subtractor at 320×180,
  dilated by 16 px in mask space. Tiles whose pixels intersect motion
  blobs run SCRFD; static tiles fall through. The coarse global pass
  remains active so seated, stationary students are never lost.

Defaults: 3 horizontal tiles × 1 row, 160 px overlap, IOS threshold
0.5, `RECOGNITION_TILE_INCLUDE_COARSE=true`, motion gating on.

### Phase 4 — Polish

- **4a / SCRFD-34G swap.** `scripts/export_static_models.py` extended
  with a `DETECTOR_ONNX_FILENAME` env var; when set to `scrfd_34g.onnx`,
  the script reads that file from the upstream pack and writes it out
  as `det_10g.onnx` in the static pack so the InsightFace loader picks
  it up transparently. Operator must drop the SCRFD-34G ONNX into
  `~/.insightface/models/buffalo_l/` first.
- **4b / Lens undistortion.** New `app/services/ml/lens_undistort.py`
  parses `LENS_UNDISTORTION_COEFFS` env (`stream_key:fx,fy,cx,cy,k1,k2,p1,p2,k3`)
  into per-camera intrinsics. `FrameGrabber` accepts a `stream_key`
  and pre-computes the cv2.remap maps once, applying `cv2.remap` per
  grab (~3-5 ms for 1080p on M5).
- **4c / INTER_CUBIC for tiny crops.** `embed_from_kps_batch` checks
  the kps spread; when the face is tiny (kps span < 0.6 ×
  `ARCFACE_TINY_CROP_PX`), the alignment uses `cv2.warpAffine` with
  `INTER_CUBIC` instead of the default `INTER_LINEAR`. Free quality
  bump on back-row recognitions.

## Throughput budget

Single-worker uvicorn ML sidecar, ANE-bound SCRFD on M5:

| Mode | Per-frame cost | 2-camera utilisation |
|---|---|---|
| Phase 0 (today, 720p / det_size 960 / 20 fps) | ~19 ms | 76 % |
| Phase 1 (1080p / det_size 1280 / 10 fps) | ~34 ms | 68 % |
| Phase 1 + Phase 2 (+0.5 fps back-row pass) | ~34 ms × 10 + ~34 ms × 0.5 | ~71 % |
| Phase 3 — tiled w/ motion gating, 3 tiles + coarse | ~15-50 ms (gated) | ~30-90 % |
| Phase 3 — tiled NO gating (worst case) | ~76 ms (4× SCRFD passes) | 152 % saturated |

The motion-gated Phase 3 is the only sustainable steady-state config.
Without gating, 3 horizontal tiles × 2 cameras saturates the sidecar.
The MOG2 BG model converges within ~10 frames; during convergence,
all tiles are treated as active (fail-open), so the first ~10 frames
of any new session are heavier — this resolves itself within ~1 s.

## File map

| Phase | File(s) |
|---|---|
| 1 | `backend/.env.onprem`, `backend/.env.onprem.example`, `scripts/export-static-models.sh` (new), `scripts/start-ml-sidecar.sh` |
| 2a | `scripts/iams-cam-relay.sh`, `deploy/mediamtx.onprem.yml` |
| 2b | `backend/app/config.py`, `backend/app/services/backrow_streams.py` (new), `backend/app/services/realtime_pipeline.py`, `backend/app/main.py` |
| 3a | `backend/app/services/ml/tile_detection.py` (new), `backend/ml-sidecar/main.py` |
| 3b | `backend/app/services/ml/insightface_model.py`, `backend/app/services/ml/remote_insightface_model.py` |
| 3c | `backend/app/config.py`, `backend/app/services/realtime_tracker.py` |
| 4a | `backend/scripts/export_static_models.py`, `backend/entrypoint.sh`, `scripts/export-static-models.sh` |
| 4b | `backend/app/services/ml/lens_undistort.py` (new), `backend/app/services/frame_grabber.py`, `backend/app/main.py` |
| 4c | `backend/app/services/ml/insightface_model.py` |
| Tests | `backend/tests/unit/test_tile_detection.py` (new) |

## Feature flags

| Flag | Default | Phase | Purpose |
|---|---|---|---|
| `INSIGHTFACE_DET_SIZE` | 1280 (was 960) | 1 | SCRFD input square size |
| `FRAME_GRABBER_WIDTH/HEIGHT` | 1920×1080 (was 1280×720) | 1 | Grabber-side decode size |
| `PROCESSING_FPS` | 10 (was 20) | 1 | ML loop rate |
| `BACKROW_CROP_STREAMS` | `""` | 2 | Comma-separated `primary=>backrow` map |
| `RECOGNITION_TILED_DETECTION_ENABLED` | `False` | 3 | Master switch |
| `RECOGNITION_TILE_COLS / ROWS` | 3 / 1 | 3 | Tile grid |
| `RECOGNITION_TILE_OVERLAP_PX` | 160 | 3 | Tile overlap |
| `RECOGNITION_TILE_INCLUDE_COARSE` | `True` | 3 | Always run global pass too |
| `RECOGNITION_TILE_NMM_IOS_THRESH` | 0.5 | 3 | IOS-NMM merge threshold |
| `RECOGNITION_TILE_MOTION_GATING_ENABLED` | `True` | 3 | MOG2 tile filter |
| `RECOGNITION_TILE_MOTION_DOWNSCALE` | 320 | 3 | MOG2 input long-edge px |
| `RECOGNITION_TILE_MOTION_DILATION_PX` | 16 | 3 | Mask dilation kernel radius |
| `DETECTOR_ONNX_FILENAME` | `det_10g.onnx` | 4a | Source ONNX inside `buffalo_l/` |
| `LENS_UNDISTORTION_COEFFS` | `""` | 4b | Newline-or-comma per-camera coeffs |
| `ARCFACE_CUBIC_UPSAMPLE_ENABLED` | `True` | 4c | INTER_CUBIC for tiny faces |
| `ARCFACE_TINY_CROP_PX` | 64 | 4c | Tiny-face threshold |

## Test coverage

`backend/tests/unit/test_tile_detection.py` — 29 tests covering:

- Tile geometry (1×1 fallback, 2×1 / 3×1 / 3×2 grids, edge anchoring,
  invalid-input rejection).
- Letterbox + remap (aspect preservation, bbox round-trip, kps round-
  trip, invalid-scale rejection).
- IOS-NMM merge (empty input, disjoint, fully-contained, seam-clipped
  halves, threshold validation).
- Tile / motion intersection (empty mask fail-open, outside-mask
  rejection, intersecting case, sub-threshold noise rejection).
- Back-row config parser (empty input, single entry, multi-entry,
  whitespace tolerance, dedup, malformed-entry rejection).
- Lens undistortion config parser (empty, single, multi-line, wrong
  coefficient count, non-numeric, camera matrix shape).

End-to-end behaviour (sidecar HTTP path, MOG2 frame loop) is tested
via integration smoke runs — see `RUNBOOK.md`.

## Lessons

- **The model can't recover pixels you never gave it.** Three weeks of
  threshold tuning, swap-gates, and frame-mutex hardening masked a
  pre-processing pixel-loss problem that one config bump fixes. Always
  validate the *physical pixel pipeline* (sensor → grabber → model
  input) before tuning the model.
- **Static-shape ANE export is brittle.** Bumping `det_size` requires
  re-running the export AND restarting the sidecar, AND the host's
  `~/.insightface/models/` must be writable from both the sidecar's
  venv and the gateway's bind-mount. Future work: surface a sidecar
  `/health` warning when its loaded `det_size` doesn't match the env
  var, so a stale pack doesn't silently degrade.
- **Cropped sub-streams are a free physics win.** For an attendance
  use case where the back rows matter as much as the front, an
  ffmpeg-side `crop` filter is more impactful per dollar than any ML
  trick. Keep it in the toolbox for future room geometries.
- **IOS not IoU when merging tiled detections.** This isn't a tunable
  — it's algorithmically what makes tiled inference work. Vanilla IoU
  NMS is wrong by construction here.
- **Motion-gating fails open.** Empty mask, MOG2 not converged, no
  tiles flagged → the system passes ALL tiles instead of NONE. This
  preserves recall during model warmup at the cost of a few seconds
  of higher CPU after a session start. Right call given that the
  coarse pass is always running anyway.
