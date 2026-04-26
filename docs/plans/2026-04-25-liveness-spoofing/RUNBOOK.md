# 2026-04-25 — Liveness / Anti-Spoofing RUNBOOK

Operator setup + verification for the MiniFASNet passive liveness layer.
Catches the "show a phone screen / printed photo to the camera" attack
that ArcFace alone cannot distinguish from a real face — the original
problem you observed on EB227 where a phone displaying Febtwel Adriana's
selfie was getting recognised at session-time.

## What the layer does

For every face that's about to be embedded by ArcFace, the realtime
tracker also runs **MiniFASNet** (MiniVision Technologies, Apache-2.0)
in the ML sidecar. MiniFASNet is the published-state-of-the-art passive
liveness CNN — small (~2 MB per submodel, 80×80 input), CoreML-friendly
on the M5, and trained on the largest public spoof dataset.

Two submodels (V2 at scale 2.7 + V1SE at scale 4.0) get fused: each
sees a different framing of the same face, and the average of their
"real" softmax probabilities is the verdict. A track that produces a
fused real-prob below the threshold for `LIVENESS_SPOOF_CONSECUTIVE`
consecutive frames flips to `liveness_suppressed=True` — recognition
is withheld, attendance is not credited, and the admin overlay renders
a red "Spoof detected" badge.

A suppressed track gets re-checked on every subsequent embed batch.
After `LIVENESS_REAL_RECOVERY_FRAMES` consecutive "real" verdicts the
suppression clears automatically — a real student briefly misclassified
(e.g. by a glare frame) recovers without operator action.

## Architecture

```
Docker container (Linux, in-process CPU only)
┌─────────────────────────────────────────────┐
│ iams-api-gateway-onprem                     │
│  ├─ FrameGrabber (RTSP)                     │
│  ├─ ByteTrack                               │
│  ├─ FAISS index                             │
│  ├─ RealtimeTracker                         │
│  │    1. SCRFD detect    (sidecar)          │
│  │    2. ArcFace embed   (sidecar batch)    │
│  │    3. MiniFASNet      (sidecar batch) ◀── NEW
│  │    4. FAISS search    (in-process)       │
│  │    5. Liveness gate   (in-process)       │
│  └─ WebSocket broadcast                     │
└─────────────────────────────────────────────┘
                          │ host.docker.internal:8001
                          ▼
Mac host (native macOS, CoreML / ANE)
┌─────────────────────────────────────────────┐
│ ml-sidecar                                  │
│  ├─ /detect    (SCRFD)                      │
│  ├─ /embed     (ArcFace)                    │
│  └─ /liveness  (MiniFASNet fused) ◀── NEW   │
└─────────────────────────────────────────────┘
```

Files added or modified:

| File | Role |
|---|---|
| [backend/scripts/export_liveness_models.py](../../../backend/scripts/export_liveness_models.py) | One-time ONNX exporter. Clones upstream repo, loads `.pth` checkpoints, exports static-shape `[1,3,80,80]` ONNX into `~/.insightface/models/minifasnet/`. |
| [backend/app/services/ml/liveness_model.py](../../../backend/app/services/ml/liveness_model.py) | Sidecar-side `LivenessModel`. Loads both ONNX submodels, exposes `predict_batch(frame, bboxes)`. Replicates upstream's bbox-scaling crop logic. |
| [backend/ml-sidecar/main.py](../../../backend/ml-sidecar/main.py) | Adds `/liveness` POST endpoint and `liveness:` block in `/health`. |
| [backend/app/services/ml/remote_liveness_model.py](../../../backend/app/services/ml/remote_liveness_model.py) | Gateway-side HTTP proxy. Same `predict_batch` signature as the in-process model. |
| [backend/app/services/ml/inference.py](../../../backend/app/services/ml/inference.py) | Adds `set_liveness_model` / `get_liveness_model` selectors. |
| [backend/app/services/realtime_tracker.py](../../../backend/app/services/realtime_tracker.py) | Liveness fields on `TrackIdentity` + `TrackResult`; `_run_liveness_batch` runs after the embed batch; recognition gate at the `pending_recognitions.append` site. |
| [backend/app/services/realtime_pipeline.py](../../../backend/app/services/realtime_pipeline.py) | Threads `liveness_state` + `liveness_score` into the WS broadcast; passes the bound liveness model into `RealtimeTracker`. |
| [backend/app/main.py](../../../backend/app/main.py) | Lifespan binds `RemoteLivenessModel` after the realtime sidecar binding succeeds + `liveness.loaded == True`. |
| [backend/app/config.py](../../../backend/app/config.py) | `LIVENESS_*` settings (enabled flag, threshold, debounce counters, recheck cadence, per-frame cap). |
| [backend/.env.onprem](../../../backend/.env.onprem) | Defaults — `LIVENESS_ENABLED=false` until operator opts in. |
| [admin/src/hooks/use-attendance-ws.ts](../../../admin/src/hooks/use-attendance-ws.ts) | `liveness_state` + `liveness_score` on `TrackInfo`. |
| [admin/src/components/live-feed/DetectionOverlay.tsx](../../../admin/src/components/live-feed/DetectionOverlay.tsx) | `OverlayState='spoof'` with red rendering + "Spoof detected" label. |
| [scripts/start-ml-sidecar.sh](../../../scripts/start-ml-sidecar.sh) | Prints `Liveness:` block in startup output so operator sees pack status. |

---

## 0. Preflight (one-time on a fresh clone)

```bash
# PyTorch is required for the ONE-TIME ONNX export only. The runtime
# (sidecar + gateway) doesn't need it. ~700 MB into the macOS host venv.
backend/venv/bin/pip install torch torchvision
```

If `torch` is already installed, `export_liveness_models.py` will detect
it and proceed; if not, it exits with a clear pip-install instruction.

---

## 1. Generate the ONNX pack

```bash
cd ~/Projects/iams
backend/venv/bin/python -m scripts.export_liveness_models
```

Expected output (last lines):

```
============================================================
  Liveness ONNX pack ready: /Users/<you>/.insightface/models/minifasnet
============================================================

Next steps:
  1. Set LIVENESS_ENABLED=true in backend/.env.onprem
  2. ./scripts/stop-ml-sidecar.sh && ./scripts/start-ml-sidecar.sh
  3. ./scripts/onprem-up.sh
  4. Verify health:
       curl -s http://127.0.0.1:8001/health | jq '.liveness'
```

What it does internally:

1. `git clone --depth 1 https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git` to a temp dir.
2. Imports upstream's `MiniFASNetV2` + `MiniFASNetV1SE` classes (so the
   model architecture comes from the source of truth, not from
   re-implemented Python in our repo — eliminates the "I rebuilt the
   network from memory and it doesn't load the .pth" failure mode).
3. Loads each `.pth` and exports to ONNX with input shape `[1, 3, 80, 80]`.
4. Round-trip verifies in ONNX Runtime — fails fast if either export
   produced a corrupt graph.
5. Writes `manifest.json` so the sidecar can self-describe pack
   contents at `/health`.
6. Cleans up the temp clone.

Idempotent: rerunning is a no-op when the ONNX files already exist.
Pass `--force` to re-export (e.g. after a torch version change).

If the host can't reach GitHub, set `LIVENESS_UPSTREAM_DIR=/path/to/local/clone`
and the script will use that instead of cloning.

---

## 2. Flip the operator switch

Edit [backend/.env.onprem](../../../backend/.env.onprem):

```diff
-LIVENESS_ENABLED=false
+LIVENESS_ENABLED=true
```

The other `LIVENESS_*` defaults are pre-tuned for the EB226/EB227
classroom setup:

```
LIVENESS_REAL_THRESHOLD=0.5             # Fused real-prob below this = spoof verdict
LIVENESS_SPOOF_CONSECUTIVE=2            # Frames of spoof before suppression flips on
LIVENESS_REAL_RECOVERY_FRAMES=3         # Frames of real before suppression flips off
LIVENESS_RECHECK_INTERVAL_S=5.0         # Re-check cadence on already-bound tracks
LIVENESS_MAX_PER_FRAME=10               # Per-frame budget cap
```

Tweak after observation in §4 if needed.

---

## 3. Restart the stack

```bash
cd ~/Projects/iams
./scripts/stop-ml-sidecar.sh
./scripts/start-ml-sidecar.sh   # picks up the new ONNX pack
./scripts/onprem-down.sh
./scripts/onprem-up.sh          # rebuilds gateway with the new tracker code
```

`start-ml-sidecar.sh` now prints the liveness pack status as part of its
final summary. Look for:

```
Liveness:
    loaded ✓  submodels=MiniFASNetV2, MiniFASNetV1SE
      MiniFASNetV2 → CoreMLExecutionProvider, CPUExecutionProvider
      MiniFASNetV1SE → CoreMLExecutionProvider, CPUExecutionProvider
```

If you instead see `NOT loaded — run: backend/venv/bin/python -m scripts.export_liveness_models`,
re-do step 1.

---

## 4. Verify end-to-end

### 4a. Sidecar advertises liveness ready

```bash
curl -s http://127.0.0.1:8001/health | python3 -m json.tool
```

Expect:

```json
{
  "status": "ready",
  "model_loaded": true,
  "providers": [...],
  "liveness": {
    "loaded": true,
    "load_seconds": 0.85,
    "pack_dir": "/Users/<you>/.insightface/models/minifasnet",
    "submodels": [
      {"name": "MiniFASNetV2", "scale": 2.7, "providers": ["CoreMLExecutionProvider", ...]},
      {"name": "MiniFASNetV1SE", "scale": 4.0, "providers": ["CoreMLExecutionProvider", ...]}
    ]
  }
}
```

### 4b. Gateway bound the proxy

```bash
docker logs --tail 50 iams-api-gateway-onprem | grep -i liveness
```

Expect:

```
Liveness backend bound — pack=/Users/<you>/.insightface/models/minifasnet, submodels=['MiniFASNetV2', 'MiniFASNetV1SE']
```

If you see "LIVENESS_ENABLED=true but sidecar reports liveness_loaded=false",
the sidecar booted before the pack was generated — restart the sidecar.

### 4c. Live attack test (the actual reason this exists)

In the admin portal, open `/schedules/<a-test-schedule>/live`:

1. **Real face control** — sit in front of the camera. Expected:
   green box, your name. The HUD's per-track liveness (visible only in
   debug mode for now — also surfaced as `liveness_state` on the WS
   payload) reads `real` with score >0.9.
2. **Phone-on-screen attack** — hold up a phone displaying the same
   student's selfie. Expected within 2-3 frames (≈1 second at the
   default `LIVENESS_SPOOF_CONSECUTIVE=2`):
   - Box flips from green to red.
   - Label changes to `Spoof detected NN%` (NN = fused real-prob).
   - Identity recognition is withheld; attendance does NOT credit.
3. **Printed photo attack** — same as 2.
4. **Recovery** — show your real face after the spoof attempt. Expected
   within ≈3 frames after the phone leaves frame: box returns to
   green and identity rebinds.

If the spoof is consistently passing as `real`:
- Check `curl /health | jq '.liveness'` — submodels really loaded?
- Bump `LIVENESS_REAL_THRESHOLD` from `0.5` toward `0.55-0.60`
  (be aware: this can increase false positives on real but
  poorly-lit faces — see "Tuning" below).
- Drop `LIVENESS_SPOOF_CONSECUTIVE` from `2` to `1` for a more
  aggressive (but less debounced) gate.

If real students are being rejected as spoof:
- Drop `LIVENESS_REAL_THRESHOLD` toward `0.4`.
- Bump `LIVENESS_REAL_RECOVERY_FRAMES` so they recover faster (set to 1
  to clear suppression on the first real verdict).
- Confirm the room lighting isn't producing extreme glare patches —
  MiniFASNet was trained mostly on indoor evenly-lit faces.

---

## 5. Operational notes

### Cost / latency

Per-face liveness inference on the M5 + CoreML is ~5-8 ms (two submodel
forward passes + softmax). At the production cadence of ~5 fps with up
to 10 simultaneous tracks, the additional sidecar load is roughly
50-80 ms/sec → 5-8 % extra utilisation on top of the SCRFD + ArcFace
baseline. Well within the M5's headroom; no cap revisit needed.

The recheck-interval gate (`LIVENESS_RECHECK_INTERVAL_S=5.0`) further
trims the work on stable tracks: a recognised student sitting still
gets one liveness check every 5 s instead of every reverify, so the
peak budget impact is at session-start (when many faces enter together)
and during occlusion-recovery (when a track briefly loses its binding).

### What the layer does NOT catch

- **3D mask attacks** (silicone, printed 3D heads). MiniFASNet's
  third class (`spoof_3D`) does fire on these in upstream's published
  benchmarks, but it requires angled views the CCTV may not see.
  Out of scope for an undergraduate thesis defence.
- **Replay video** (someone playing a recorded video of the student
  through a screen). Same as photo-on-screen for our purposes —
  MiniFASNet still flags it because the model attacks screen artefacts,
  not motion.
- **Twin / lookalike attacks**. This is an identity-resolution problem,
  not a liveness one — addressed by the 2026-04-25 swap-hardening
  RUNBOOK.

### Failure modes + degraded behaviour

| Failure | Behaviour | Operator signal |
|---|---|---|
| Liveness pack missing | Sidecar starts; `/liveness` returns 503; gateway logs `liveness_loaded=false`; tracker treats every track as `liveness_state="unknown"` (no gating). | `start-ml-sidecar.sh` final block prints "NOT loaded". |
| Sidecar crashes mid-session | Existing `RemoteLivenessModel` calls raise `RuntimeError`; tracker's `try/except` swallows; recognition continues normally without liveness gating. | `Liveness batch failed` debug-level log per failed call. |
| MiniFASNet inference slower than expected | Per-track liveness check still completes but eats into the per-frame budget. Eventually the existing `MAX_FIRST_RECOGNITIONS_PER_FRAME` cap fires upstream. | HUD `embed_ms` + `other_ms` jump in the live page footer. |

In short: **a missing or crashed liveness layer never blocks recognition.**
Spoof gating is opt-in protection on top of the existing pipeline; its
failure mode is "no protection" (= today's behaviour), not "no recognition".

### Rolling back

If you need to disable the layer in production without rebuilding:

```bash
# Quick toggle — survives until next .env.onprem change:
docker exec iams-api-gateway-onprem sh -c 'export LIVENESS_ENABLED=false'   # informational only

# Real toggle — flip the env then restart the gateway:
sed -i.bak 's/^LIVENESS_ENABLED=true/LIVENESS_ENABLED=false/' backend/.env.onprem
./scripts/onprem-down.sh && ./scripts/onprem-up.sh
```

The sidecar can stay up; with `LIVENESS_ENABLED=false`, the gateway
binds `set_liveness_model(None)` and the tracker's
`if self._liveness is not None and settings.LIVENESS_ENABLED` guard
short-circuits. No sidecar load is wasted (it just isn't called).

---

## Lessons

- **Vendor the model architecture from upstream at export time, not in
  our codebase.** The first design called for inlining MiniFASNet's
  ~500 lines of PyTorch model definitions. That couples our repo to
  upstream's exact module layout, makes us responsible for any bug fixes
  they ship, and risks a subtle divergence between "what we wrote" and
  "what the .pth was trained against" silently degrading the model.
  The git-clone-at-export-time approach keeps upstream as the source of
  truth and we ship only the resulting ONNX.
- **Pre-pay model JIT before serving traffic.** Both submodels JIT on
  first inference (~1-2 s each on CoreML). Without `LivenessModel.warmup()`
  the first session pipeline that opens after sidecar boot saw a
  multi-second visible delay before any liveness verdict landed —
  same lesson as the SCRFD warmup pass added in the 2026-04-25
  live-feed plan.
- **Keep the broadcast field optional + defaulted on the client side.**
  Older mobile builds that don't know about `liveness_state` will
  silently ignore the field and continue rendering on
  `recognition_state` alone. Future-compatible by default.
- **Make liveness orthogonal to recognition state, not a fourth value
  in `recognition_state`.** The first overlay design tried to overload
  `recognition_state="spoof"` and broke older clients that hard-coded
  the three valid values. Splitting it into `liveness_state` (separate
  field) means the spoof signal can be added or removed without
  touching the recognition state machine. The overlay's `deriveOverlayState`
  composes them — spoof wins, otherwise fall through to recognition.
