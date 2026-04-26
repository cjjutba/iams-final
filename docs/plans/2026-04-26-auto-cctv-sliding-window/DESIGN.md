# 2026-04-26 — Auto-CCTV: sliding-window enrolment

Continuous-but-bounded auto enrolment for CCTV-side embeddings, with
quality-weighted eviction once the per-(user, room) cap is reached.

## Problem

Phone selfies (close-up, rectilinear, warm WB) and CCTV crops
(40-100 px, wide-angle barrel-distorted, cool WB) sit in different
regions of ArcFace embedding space. Cross-domain similarities top out
around 0.45-0.65 — well above noise but far from the 0.70+ "unambiguous"
band where the swap-gate / frame-mutex / oscillation suppressor never
need to fire.

The current `AutoCctvEnroller` (shipped 2026-04-25) closes that gap by
opportunistically capturing real CCTV embeddings during a student's
first sessions. It works, but it's append-only and capped at 15 captures
per (user, room) in `.env.onprem`. After the cap, two things stop
happening:

1. **Drift adaptation.** A student who grows a beard, gets glasses, or
   changes haircut has no path for their CCTV cluster to track the
   change. Recognition silently degrades over the term.
2. **Lighting / season coverage.** A student auto-enrolled in
   September morning sun ends up under-represented in November's
   late-afternoon overhead-light conditions. Same student, different
   embedding distribution.

The user's instinct is right: *the enroller should keep updating*. The
naive form ("remove the cap, write forever") is what produced the
2026-04-25 Desiree↔Ivy Leah identity-swap incident — append-only
auto-enrolment is a feedback loop where every wrong commit makes the
next wrong commit easier.

## Goals

- Enroll continuously enough that the cluster tracks face drift across
  a whole term.
- Stay bounded in storage, FAISS size, and per-query cost.
- Make it structurally impossible for one bad commit to rewrite the
  cluster (the 2026-04-25 failure mode).
- Keep the realtime hot path's cost at "one dict lookup + a few
  comparisons" — same as today.

## Design

Three independent additions, all on top of the existing
`AutoCctvEnroller`:

### 1. Higher cap + sliding-window eviction

- `AUTO_CCTV_ENROLL_LIFETIME_CAP` raised from 15 → 30. Bounded blast
  radius if the swap-safe gate (below) ever leaks a wrong commit.
- When a new buffered batch arrives at a saturated (user, room), the
  enroller evicts the **lowest-quality existing CCTV embedding**
  before inserting the new one. "Quality" is the existing
  `face_embeddings.quality_score` column — historically populated with
  the recognition confidence (0-1), which we re-purpose as a
  composite "should we keep this" score (see §2).
- Eviction order: lowest score first. Ties broken by `created_at`
  (older first), so even a tie eventually moves the cluster forward.
- The legacy `cctv_<idx>` rows (no room) are evictable too — they
  scored well enough to land in the cluster originally; they can be
  replaced by a higher-quality room-scoped capture from the same
  student.

**Storage cost** at N=200 students × 2 rooms × 30 captures = 12K
vectors. `IndexFlatIP` query cost stays well under 5 ms; that's the
threshold where we'd need to migrate to IVF/PQ. Disk: ~12K × 12 KB ≈
145 MB. Postgres rows: 12K. All trivial.

**FAISS deletion caveat.** `IndexFlatIP` does not support native
removal — `faiss_manager.remove(faiss_id)` only deletes the
`user_map` entry, leaving an orphan vector that no top-K can return
(no user_id maps to it). We accept this. The orphan inflates
`index.ntotal` but not query results; the existing
`scripts.rebuild_faiss` is the periodic cleanup tool. Each eviction
logs a counter so the operator can decide when to rebuild.

### 2. Composite quality score at intake

Today `quality_score` stores the recognition confidence at capture
time. We replace it with a composite that covers what "should we keep
this" actually means:

```
quality_score = 0.6 * confidence + 0.4 * normalized_blur
```

- `confidence` ∈ [0, 1] — FAISS top-1 sim at the moment we offered
  this capture. High = ArcFace strongly agreed it's this user.
- `normalized_blur` ∈ [0, 1] — Laplacian variance / 200, clamped.
  200 is the empirical "very sharp face crop" ceiling on the M5 +
  Reolink combo (typical sharp classroom face: 80-180; blurry: <40).
  Sharper crops are more useful as future training references.

Cheap to compute (single grayscale Laplacian — already implemented in
`face_quality.compute_blur_score`). The realtime tracker's
`assess_recognition_quality` ALREADY computes this for every
recognition crop; we just need to thread the result through to the
offer site so we don't recompute.

### 3. Daily intake throttle (post-cap only)

Once a (user, room) is at the cap of 30, accept at most
`AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT=2` replacement batches per
UTC day for that pair. Pre-cap (still filling toward 30) is unaffected
— a fresh student should fill quickly.

Why: stops a single bad lighting day from rewriting half the cluster.
With 30 captures and 2 replacements/day, the cluster has a half-life
of ~10 days under unfavourable conditions but stays intact under good
ones. Compatible with quality-weighted eviction: a sharp captures from
a bad-lighting day will still evict a blurry capture from a good day,
which is the right tradeoff.

State lives in `_UserRoomEnrollState.replacements_today` plus
`replacement_window_started_at` (UTC midnight). Reset crosses midnight
locally; no clock-skew complications because we use UTC.

### 4. Swap-safe commit gate

Today's commit gate checks `mean_sim_to_phone_embedding ≥ 0.30`. That
catches "wrong person whose CCTV crops don't even resemble the user's
phone selfie" but misses "wrong person who happens to look kinda like
the user's phone selfie" — exactly the failure mode of the 2026-04-25
Desiree↔Ivy Leah swap.

Add a cross-user check per capture:

1. For each new embedding `e` in the batch, run
   `faiss_manager.search(e, k=5)` (filtering OUT the claimed user's
   existing vectors).
2. Let `competing_top1_sim` = max sim against any OTHER user_id.
3. Let `claimed_top1_sim` = mean sim against the claimed user's
   existing vectors.
4. **Reject the batch if any single capture has
   `competing_top1_sim > claimed_top1_sim - SWAP_SAFE_MARGIN`.**

`SWAP_SAFE_MARGIN` defaults to `RECOGNITION_MARGIN` (0.10) — the same
gap the realtime path requires for unambiguous matches. If a single
capture in the batch isn't decisively closer to the claimed user than
to anyone else, the entire batch is discarded and the buffer resets.

Cost: one batched FAISS search per commit (5 captures × 1 search ≈ 1
ms). Background-thread only — never on the realtime hot path.

## Hot-path impact

Zero. All of §1-§4 happen inside `_do_commit` on the background
executor. The `offer_capture` hot-path code stays at:

- Dict lookup on `_states[(user_id, room_key)]`
- Compare `cctv_count` vs cap (now 30)
- Compare `confidence` vs threshold
- Compare `consecutive_high_conf_frames` vs stability gate
- Compare `now - last_capture_at` vs spacing
- Append to deque

Same as today.

## Migration / backward compatibility

- Existing `face_embeddings` rows with the legacy `cctv_<idx>` label
  are handled by the existing `parse_cctv_label` helper. They count
  toward the new 30-cap when the user appears in any room (because
  `parse_cctv_label("cctv_5")` returns `(None, 5)` → `_legacy` bucket
  → not counted toward any specific room cap). Eviction can pick
  legacy rows when their `quality_score` is the lowest in the
  candidate pool — they have NULL `quality_score` for old captures,
  so they're always the most-evictable.
- Bootstrap reads `(user_id, label, quality_score, faiss_id,
  image_storage_key)` instead of just `(user_id, label)`, so the
  enroller knows what's evictable on first commit without a re-query.
- No DB migration needed (every column already exists).

## Failure modes (closed)

| Failure | Mitigation |
|---|---|
| Wrong-identity batch slips past the buffer | Swap-safe per-capture gate (§4) refuses the whole batch |
| Cluster drifts from real face over many commits | Quality-weighted eviction keeps highest-quality captures; daily throttle limits drift rate |
| Bad lighting day rewrites the cluster | Daily replacement limit (§3) caps damage at 2 batches/day |
| Storage growth unbounded | Hard cap of 30/(user, room); IndexFlatIP query cost stays well under 5 ms |
| FAISS index inflates with orphans | Counter logged per eviction; manual `rebuild_faiss` is the cleanup tool |
| Realtime hot path slows down | All new logic is on the background executor |

## Out of scope

- **Pose estimation at intake.** Yaw/pitch could improve diversity,
  but landmarks are computed in the ArcFace path and not currently
  threaded through to the offer site. Adding the plumbing is a bigger
  refactor than this plan justifies. Quality + confidence + sliding-
  window already give us pose diversity over time.
- **Per-room threshold tuning.** Each room's CCTV embedding cluster
  may want its own `RECOGNITION_THRESHOLD`. Out of scope; current
  global threshold + per-room synthesis is good enough.
- **Operator UI for review/rollback.** The student-detail page already
  shows CCTV captures with thumbnails. A future plan can add a
  "reject this capture" admin action that triggers manual eviction.

## Lessons (filled in after execution)

- TBD
