# Distant-Face Detection — Runbook

How to roll forward / verify / roll back each phase of the distant-face
plan dated 2026-04-26.

> **Critical:** the live on-prem stack on the Mac currently has working
> face registrations and may have an active session. Read each step
> before running it. None of these procedures touch the database — but
> some restart the sidecar / api-gateway, which interrupts active live
> overlays for ~30-60 s.

---

## Pre-flight

```bash
cd ~/Projects/iams
git status            # confirm you're on the expected branch
git log --oneline -5  # last few commits visible
```

The phases below assume a running on-prem stack (`docker ps` shows the
`iams-*-onprem` containers, `lsof -i :8001` shows the sidecar). If
anything is offline, bring it back with the standard
`./scripts/onprem-up.sh` first.

---

## Phase 1 — Bigger detector input + grabber resolution

**What changes:** SCRFD now sees ~35 px back-row faces instead of ~19 px.

### Roll forward

```bash
# 1. The .env.onprem already has the new values committed:
grep -E "FRAME_GRABBER_(WIDTH|HEIGHT|FPS)|PROCESSING_FPS|INSIGHTFACE_DET_SIZE" backend/.env.onprem
# expect:
#   FRAME_GRABBER_WIDTH=1920
#   FRAME_GRABBER_HEIGHT=1080
#   FRAME_GRABBER_FPS=10
#   PROCESSING_FPS=10
#   INSIGHTFACE_DET_SIZE=1280

# 2. Re-export the static-shape ONNX pack on the host. Idempotent —
#    if the existing pack already matches det_size=1280 this is a
#    near-instant no-op.
./scripts/export-static-models.sh

# 3. Restart the ML sidecar so it picks up the new pack. start-ml-sidecar.sh
#    runs export-static-models.sh internally too (belt + braces).
./scripts/stop-ml-sidecar.sh
./scripts/start-ml-sidecar.sh
# Expected: "Provider report:" lines all show CoreMLExecutionProvider.

# 4. Restart the api-gateway to pick up the new env values. The shutdown
#    cleanly stops all FrameGrabbers + Pipelines first.
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

### Verify

```bash
# Sidecar reports the new det_size in its /health body.
curl -s http://127.0.0.1:8001/health | python3 -m json.tool | grep det_size
# expect: "det_size": [1280, 1280]

# Open the admin live page on a class with active recognition. Walk to
# the back wall (8-10 m). The previously-missed face should now appear
# in the overlay within a few frames.

# Watch the sidecar timing logs:
tail -f ~/Library/Logs/iams-ml-sidecar.log | grep -i 'det'
# Per-frame det_ms should still be < 50 ms.

# Watch the gateway timing logs:
docker logs --tail 100 -f iams-api-gateway-onprem | grep 'tracker timing'
# Per-frame total should be < 100 ms; tracks count > 0 with backrow
# students.
```

### Roll back

```bash
git checkout backend/.env.onprem
./scripts/export-static-models.sh   # regenerates the smaller pack
./scripts/stop-ml-sidecar.sh && ./scripts/start-ml-sidecar.sh
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

---

## Phase 2 — Cropped back-row streams

**What changes:** A second mediamtx stream per camera (`eb226-back`,
`eb227-back`) is published at ~2× pixel density on the back rows. A
parallel detection-only loop in the SessionPipeline feeds presence
data from both views.

### Roll forward

```bash
# 1. Confirm the cam-relay supervisor knows about the cropped streams:
grep -A5 "^CROPPED_STREAMS=" scripts/iams-cam-relay.sh
# expect entries for eb226 / eb227.

# 2. Reload the cam-relay so it spawns the crop-encoder subprocesses.
./scripts/stop-cam-relay.sh
./scripts/start-cam-relay.sh

# 3. Verify the cropped streams are live in mediamtx (after ~5-10s):
docker exec iams-mediamtx-onprem wget -qO- http://localhost:9997/v3/paths/list \
  | python3 -m json.tool | grep -E '"name"|ready' | head -20
# expect "eb226" + "eb226-back" + "eb227" + "eb227-back" all ready=true

# 4. Set BACKROW_CROP_STREAMS in .env.onprem (default is empty = phase 2 OFF).
#    Append this line:
echo 'BACKROW_CROP_STREAMS=eb226=>eb226-back,eb227=>eb227-back' \
  >> backend/.env.onprem

# 5. Restart api-gateway to wire up the secondary FrameGrabbers.
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

### Verify

```bash
# api-gateway logs should show:
docker logs --tail 200 iams-api-gateway-onprem | grep -i 'back-row'
# expect:
#   "Back-row FrameGrabber preloaded for eb226 -> rtsp://mediamtx:8554/eb226-back"
#   "SessionPipeline ... back-row tracker attached (camera_id=eb226-back)"

# Periodic back-row tracker activity:
docker logs --tail 200 iams-api-gateway-onprem | grep 'back-row:'
# expect "back-row: NN frames, 0/1 tracks this frame, ~30ms processing"
```

### Roll back

```bash
# Remove BACKROW_CROP_STREAMS from .env.onprem.
sed -i.bak '/^BACKROW_CROP_STREAMS=/d' backend/.env.onprem
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway

# Optionally stop the crop ffmpegs (purely cosmetic — they don't use
# significant resources when nobody reads them):
./scripts/stop-cam-relay.sh && ./scripts/start-cam-relay.sh
# (the new cam-relay still publishes eb226-back unless you also revert
#  the CROPPED_STREAMS array in scripts/iams-cam-relay.sh)
```

---

## Phase 3 — Tiled inference

**What changes:** SCRFD runs on N tiles per frame instead of one global
frame, gated by motion. The IOS-NMM merge layer dedupes seam-clipped
detections.

### Roll forward

```bash
# 1. Flip the flag in .env.onprem:
echo 'RECOGNITION_TILED_DETECTION_ENABLED=true' >> backend/.env.onprem

# 2. (Optional) tune the tile geometry. Defaults are 3×1 horizontal with
#    160 px overlap, IOS threshold 0.5, motion-gating on. Change in
#    .env.onprem only if you have a reason — the defaults match the
#    SAHI paper's classroom-geometry sweet spot.

# 3. Restart api-gateway. (The sidecar already supports /detect_tiled —
#    no sidecar restart needed.)
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

### Verify

```bash
# Look for the tile-layout log emitted on first frame of an active
# session:
docker logs --tail 500 iams-api-gateway-onprem | grep -i 'tile layout'
# expect: "Tile layout (re)computed for 1920x1080: 3 tiles, overlap=160px"

# Sidecar log should show /detect_tiled hits with timing breakdown:
tail -f ~/Library/Logs/iams-ml-sidecar.log | grep -E 'detect_tiled|tile_count'

# Per-frame det_ms in the gateway timing log should be ~3× the
# pre-Phase-3 value during motion events, ~1× during fully-static
# scenes (motion-gating leaves only the coarse pass running).

# Crucially: walk to the back of the room. New tracks should appear
# that didn't exist before — this is the recall lift.
```

### Roll back

```bash
sed -i.bak 's/^RECOGNITION_TILED_DETECTION_ENABLED=true/RECOGNITION_TILED_DETECTION_ENABLED=false/' backend/.env.onprem
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

The flag-off case routes through plain `detect()` like Phases 1+2 alone.

---

## Phase 4a — SCRFD-34G swap (optional)

**Use only if Phases 1-3 still leave a back-row recall gap.**

### Roll forward

```bash
# 1. Download SCRFD-34G ONNX from the InsightFace model zoo:
#    https://github.com/deepinsight/insightface/tree/master/detection/scrfd
#    The file is named scrfd_34g.onnx (or scrfd_34g_bnkps.onnx — use
#    the variant with bnkps in the filename for 5-pt landmarks). Drop
#    it into:
ls -la ~/.insightface/models/buffalo_l/scrfd_34g.onnx

# 2. Set the env var:
echo 'DETECTOR_ONNX_FILENAME=scrfd_34g.onnx' >> backend/.env.onprem

# 3. Re-export. The static export script will read scrfd_34g.onnx and
#    write it out as det_10g.onnx in the static pack so the InsightFace
#    loader picks it up transparently.
./scripts/export-static-models.sh

# 4. Restart sidecar + gateway:
./scripts/stop-ml-sidecar.sh && ./scripts/start-ml-sidecar.sh
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

### Verify

```bash
# /health response includes the model name (loosely identifying which
# variant is bound):
curl -s http://127.0.0.1:8001/health | python3 -m json.tool | grep -i name

# Per-frame det_ms should roughly double (10G → 34G is ~2× FLOPs on
# Apple Silicon). Recognition recall on Hard / small faces should
# improve by ~2 AP points (WIDER FACE Hard 83.05 → 85.29).
```

### Roll back

```bash
sed -i.bak '/^DETECTOR_ONNX_FILENAME=/d' backend/.env.onprem
./scripts/export-static-models.sh
./scripts/stop-ml-sidecar.sh && ./scripts/start-ml-sidecar.sh
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

---

## Phase 4b — Lens undistortion (optional)

**Use only if students near the side walls are visibly stretched on
the live overlay.** Calibration is a one-time per-camera operation.

### Calibrate

```bash
# Print a 9×6 checkerboard pattern (e.g.
# https://markhedleyjones.com/projects/calibration-checkerboard-collection),
# tape it to a rigid backing, hold it up in front of each camera at
# ~10 different positions / angles. Capture ~20 frames per camera.
#
# Run the OpenCV calibration script — TBD; the app currently has no
# built-in calibrator. Use the standard recipe from
# https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html.
# Output is fx, fy, cx, cy, k1, k2, p1, p2, k3.
```

### Roll forward

```bash
# Add per-camera coefficients to .env.onprem. Format:
#   stream_key:fx,fy,cx,cy,k1,k2,p1,p2,k3
# One per line, OR comma-separated.
cat >> backend/.env.onprem <<'EOF'
LENS_UNDISTORTION_COEFFS=eb226:1500.0,1500.0,960.0,540.0,-0.30,0.10,0.0,0.0,0.0
EOF

# Restart api-gateway.
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

### Verify

```bash
# Gateway log should show the undistortion enabling line:
docker logs --tail 200 iams-api-gateway-onprem | grep 'undistortion enabled'
# expect: "FrameGrabber lens undistortion enabled for eb226 (fx=1500.0 ...)"

# The live overlay's source video will look subtly different — straight
# lines that bowed at the edges should now be straight. Per-frame grab
# cost goes up by ~3-5 ms for a 1080p frame.
```

### Roll back

```bash
sed -i.bak '/^LENS_UNDISTORTION_COEFFS=/d' backend/.env.onprem
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

---

## Phase 4c — INTER_CUBIC for tiny crops

**Already on by default** (`ARCFACE_CUBIC_UPSAMPLE_ENABLED=true`).
Tiny-face threshold is 64 px (`ARCFACE_TINY_CROP_PX`).

### Roll back

```bash
echo 'ARCFACE_CUBIC_UPSAMPLE_ENABLED=false' >> backend/.env.onprem
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway
```

---

## Full happy-path rollout (all phases at once)

If you trust each phase individually and just want to bring everything
up cleanly in one go:

```bash
cd ~/Projects/iams

# 1. Append the back-row config + tiled flag (.env.onprem already has
#    Phase 1 values committed).
cat >> backend/.env.onprem <<'EOF'
BACKROW_CROP_STREAMS=eb226=>eb226-back,eb227=>eb227-back
RECOGNITION_TILED_DETECTION_ENABLED=true
EOF

# 2. Reload cam-relay (publishes the new cropped streams).
./scripts/stop-cam-relay.sh
./scripts/start-cam-relay.sh

# 3. Re-export static-shape ONNX pack.
./scripts/export-static-models.sh

# 4. Restart sidecar.
./scripts/stop-ml-sidecar.sh
./scripts/start-ml-sidecar.sh

# 5. Restart api-gateway to pick up everything.
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway

# 6. Wait ~30 s for everything to settle, then open the admin live page.
```

### Sanity check after rollout

```bash
# All four critical processes alive:
docker ps --filter name=iams-onprem --format '{{.Names}} {{.Status}}'
ls "${HOME}/Library/Application Support/iams/ml-sidecar.pid" \
  && pgrep -F "${HOME}/Library/Application Support/iams/ml-sidecar.pid"
pgrep -f iams-cam-relay && echo "cam-relay alive"

# Sidecar reports CoreML providers:
curl -s http://127.0.0.1:8001/health | python3 -m json.tool | grep -A1 providers

# Mediamtx publishing all four expected streams:
docker exec iams-mediamtx-onprem wget -qO- http://localhost:9997/v3/paths/list \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for p in data.get('items', []):
    print(p.get('name'), '→ ready=', p.get('ready'))
"
# expect eb226 / eb227 / eb226-sub / eb227-sub / eb226-back / eb227-back, all ready=True

# Open http://localhost:5173/ and click into a Live page on an active
# schedule. Walk to the back of the room. Confirm:
#   - You appear in the overlay (Phase 1)
#   - The "back-row: NN frames" log line is appearing in dozzle (Phase 2)
#   - The "Tile layout" log line appeared once on session start (Phase 3)
```

If any of those checks fail, isolate by phase using the per-phase
verify steps above.
