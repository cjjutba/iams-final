# 2026-04-25 — Identity-Swap Hardening RUNBOOK

Operator-side checklist for the swap-flicker fix. Two pieces:

1. **Code change** — already merged on `feat/local-compute-split`.
   Tracker now has a vote-based swap gate, frame-level Hungarian mutual
   exclusion, and an oscillation suppressor. Restart to pick it up.

2. **Data change** — every enrolled student in EB226/EB227 needs real
   CCTV-side embeddings (`cctv_*` rows in `face_embeddings`). Without
   this, the new gates protect against label flicker but the underlying
   sims still sit in the 0.45-0.55 cross-domain noise band.

The data step is the bigger lever. The prior failure mode was that two
students both scored ~0.46 against a third student's vector cluster, and
the 0.05 swap margin let the binding flip every frame. The new gates
stop the visible flicker; CCTV enrolment moves the operating point up
to where the gates are uncontested.

## 0. Preflight

```bash
# Confirm both cameras are streaming.
docker exec iams-mediamtx-onprem wget -qO- http://localhost:9997/v3/paths/list \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(p['name'] for p in d['items']))"
# Expect: eb226, eb226-sub, eb227, eb227-sub
```

If a camera is missing, run `./scripts/start-cam-relay.sh` first — the
enrol script reads frames from the same RTSP path the live pipeline
uses, so a missing publisher means zero captures.

## 1. Restart the api-gateway to load the new tracker

```bash
cd ~/Projects/iams
./scripts/onprem-down.sh
./scripts/onprem-up.sh   # rebuilds the api-gateway image with the new code
```

After restart, verify the new settings are picked up:

```bash
docker exec iams-api-gateway-onprem python -c "
from app.config import settings
for attr in ('RECOGNITION_SWAP_MARGIN','RECOGNITION_SWAP_MIN_STREAK',
             'RECOGNITION_FRAME_MUTEX_ENABLED','OSCILLATION_WINDOW_SECONDS',
             'OSCILLATION_FLIPS_THRESHOLD','OSCILLATION_DISTINCT_USERS',
             'OSCILLATION_UNCERTAIN_HOLD_S'):
    print(f'{attr} = {getattr(settings, attr)!r}')"
```

Expected baseline (from `backend/.env.onprem`):

```
RECOGNITION_SWAP_MARGIN = 0.1
RECOGNITION_SWAP_MIN_STREAK = 3
RECOGNITION_FRAME_MUTEX_ENABLED = True
OSCILLATION_WINDOW_SECONDS = 8.0
OSCILLATION_FLIPS_THRESHOLD = 3
OSCILLATION_DISTINCT_USERS = 2
OSCILLATION_UNCERTAIN_HOLD_S = 3.0
```

## 2. Run CCTV enrolment for every enrolled student in each room

Below are the exact commands per (student × room) for the current
classroom. Re-run [`backend/scripts/print_cctv_enroll_plan.py`](../../../backend/scripts/print_cctv_enroll_plan.py) to refresh after enrolling
new students.

**Procedure for each student**:

1. Ask the student to stand alone in front of the named camera (no
   other faces in frame — the enrol script aborts on multi-face).
2. Run the command. The script captures 5 frames spaced 1.0 s apart.
3. Watch the output: `Sim to phone (mean/min/max): 0.4xx / 0.4xx / 0.5xx`
   means the captures landed in the same identity cluster as the
   student's phone enrolment. Mean below 0.40 → re-frame and try again.
4. Move on to the next student in the same room before switching cameras.

### EB226 (10 students)

```bash
# All 10 students, EB226 camera, 5 captures each:
docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 998973d9-1a08-495e-8c3f-96ee5cdcc225 --room EB226 --captures 5  # Christian Jutba

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 3316b97a-3541-49b8-98fe-47a3f14a109c --room EB226 --captures 5  # Desiree Gumla

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 0e77efac-e691-4ce4-9a2f-07b27d694b44 --room EB226 --captures 5  # Febtwel Adriana Baltazar

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 348c1665-460e-460f-b9ed-1b9407604ae7 --room EB226 --captures 5  # Ivy Leah Ruta

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 01c26269-9733-4b51-bcbc-58e0adc2081d --room EB226 --captures 5  # James Calunsag

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id c3d0a4b2-f839-4ec5-8870-1e5ab8d1c87a --room EB226 --captures 5  # Jana Crizzia Gagno

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 8cec0a9f-f7cd-41c7-886e-08216ca7b6f6 --room EB226 --captures 5  # Kieron Bernido

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id e10e9e1b-5dac-469d-be12-4bff61170583 --room EB226 --captures 5  # Ralph Wyndril Andilab

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 16485ed6-3dcf-4cef-8b79-56650275c97c --room EB226 --captures 5  # Sean Myk Daniel Jacinto

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id bb299145-ee40-4fee-8889-b64dcd2940b9 --room EB226 --captures 5  # Vincent Laluna
```

### EB227 (same 10 students — different lens, repeat the run)

```bash
docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 998973d9-1a08-495e-8c3f-96ee5cdcc225 --room EB227 --captures 5  # Christian Jutba

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 3316b97a-3541-49b8-98fe-47a3f14a109c --room EB227 --captures 5  # Desiree Gumla

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 0e77efac-e691-4ce4-9a2f-07b27d694b44 --room EB227 --captures 5  # Febtwel Adriana Baltazar

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 348c1665-460e-460f-b9ed-1b9407604ae7 --room EB227 --captures 5  # Ivy Leah Ruta

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 01c26269-9733-4b51-bcbc-58e0adc2081d --room EB227 --captures 5  # James Calunsag

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id c3d0a4b2-f839-4ec5-8870-1e5ab8d1c87a --room EB227 --captures 5  # Jana Crizzia Gagno

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 8cec0a9f-f7cd-41c7-886e-08216ca7b6f6 --room EB227 --captures 5  # Kieron Bernido

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id e10e9e1b-5dac-469d-be12-4bff61170583 --room EB227 --captures 5  # Ralph Wyndril Andilab

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id 16485ed6-3dcf-4cef-8b79-56650275c97c --room EB227 --captures 5  # Sean Myk Daniel Jacinto

docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    --user-id bb299145-ee40-4fee-8889-b64dcd2940b9 --room EB227 --captures 5  # Vincent Laluna
```

After all 20 runs (10 students × 2 rooms), each student should have 10
new `cctv_*` rows in `face_embeddings` and the FAISS index will have
grown by ~100 vectors. The api-gateway picks up the new vectors
immediately (FAISS adds are written to the live index and notified via
Redis pubsub).

## 3. Verify the gain

```bash
docker exec iams-api-gateway-onprem python -m scripts.calibrate_threshold \
    --rooms EB226,EB227 --frames 30 --csv /tmp/calib.csv
```

Expected outcome after enrolment:
- Per-user top-1 sim distribution shifts from 0.40-0.55 → 0.65-0.85.
- Recommended threshold + margin both stable at the current
  RECOGNITION_THRESHOLD=0.45 / RECOGNITION_MARGIN=0.10 baseline.
- The script's "ambiguous" rate (top-1 within margin of top-2) drops
  to near zero.

If a specific student still scores < 0.55 after enrolment, re-run
`cctv_enroll` for them with `--captures 10` and verify the per-capture
sim_to_phone numbers are above 0.40 — values below that mean the crops
are landing in the wrong cluster (face occluded, lighting off, wrong
student in frame).

## 4. Refresh the per-student plan after new students enroll

```bash
docker exec iams-api-gateway-onprem python -m scripts.print_cctv_enroll_plan
```

Outputs the same per-room / per-student command list but for the
current DB state. Re-generate this RUNBOOK by replacing the EB226/EB227
sections above with the script's output.

## What the new tracker layers do

1. **Vote-based swap gate** ([backend/app/services/realtime_tracker.py:1504-1656](../../../backend/app/services/realtime_tracker.py#L1504-L1656))
   replaces the previous single-frame `swap_margin = 0.05` with a
   strike-streak: a candidate must beat the bound user by
   `RECOGNITION_SWAP_MARGIN` on `RECOGNITION_SWAP_MIN_STREAK` consecutive
   re-verifies before the binding flips. Alternating Christian / James
   noise no longer flips the label.

2. **Frame-level mutual exclusion (Hungarian)** ([backend/app/services/realtime_tracker.py:1658-1808](../../../backend/app/services/realtime_tracker.py#L1658-L1808))
   resolves cross-track collisions before per-track update. Incumbents
   (already-recognised tracks re-confirming themselves) are locked off
   the auction; challengers compete on top-1 / top-2 candidates so a
   loser falls back to its second-best instead of being dropped from
   the broadcast entirely.

3. **Oscillation suppressor** ([backend/app/services/realtime_tracker.py:1957-1990](../../../backend/app/services/realtime_tracker.py#L1957-L1990))
   silences the displayed name (overlay shows "Detecting…") when a
   track exceeds `OSCILLATION_FLIPS_THRESHOLD` confirmed swaps across
   `OSCILLATION_DISTINCT_USERS` distinct users in the last
   `OSCILLATION_WINDOW_SECONDS`. Internal binding is preserved so
   attendance + presence keep working — only the visible label is
   suppressed.

The three layers compose. The data fix in §2 above is what makes the
operating point comfortable for them.

## Lessons

- Threshold-only tuning (raise to 0.45) cuts false accepts but leaves
  the swap-flicker problem when two students score ~0.46 against the
  same vector cluster.
- A single-frame swap gate at margin=0.05 sits well inside the noise
  floor of phone-only enrolments and produces the visible label
  flicker. Either widen the margin or require N-frame consensus.
- Synthetic `sim_*` embeddings (the SIM_VARIANTS_PER_CAMERA pipeline)
  help cross-domain recognition lift-off but don't replace real CCTV
  captures. Real captures from `cctv_enroll` outperform the synthetic
  variants at classroom distance.
- Frame-level dedup that just *drops* duplicate-bound bboxes loses
  information the operator needs (one student visibly disappears from
  the overlay). Hungarian assignment with top-2 fallback keeps both
  bboxes and lets the labels arbitrate.
