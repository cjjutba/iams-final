# Lessons

Append-only log of planning/implementation lessons worth keeping for future sessions. Read at the start of every session per project CLAUDE.md policy.

---

## 2026-04-17: Hybrid detection rollout — master lessons

Ten parallel Claude Code sessions delivered the ML Kit + backend matcher architecture. What the experiment taught us:

- **Freeze contracts in the master plan, not in code.** When N sessions run in parallel, the document *is* the integration point. Our master plan §5 nailed down every data class and public method signature; sessions coded against it even before upstream PRs merged. A contract change mid-flight would have blocked nine sessions.
- **Don't redefine existing types.** `MlKitFace` lives in `com.iams.app.webrtc`; `TrackInfo` in `com.iams.app.data.model`. Sessions had to import, not shadow. Two parallel sessions drifting on the same type's shape would have turned merging into a rewrite.
- **Commit messages are a contract too.** One session's commit `hybrid: integrate hybrid detection sessions 06-10` actually only committed plan docs and silently deleted 55 historical design files. Treat grouped commit messages that claim large work as a red flag; audit the diff, not the summary.
- **Feature-flag hybrid architecture from day one.** `BuildConfig.HYBRID_DETECTION_ENABLED` exists so the legacy `InterpolatedTrackOverlay` path stays reachable. Ship with rollback already in place — don't invent it after the first regression.
- **The matcher must be single-threaded.** `Dispatchers.Default.limitedParallelism(1)` on the ViewModel side is cleaner than making the matcher thread-safe. Keep mutable matcher state private and serialise at the caller.
- **Greedy IoU ≠ Hungarian for N ≤ 20 faces.** Sort candidates descending, accept when neither side is claimed. The maths converges fast; Hungarian adds complexity with no gain at classroom scales.
- **Median-of-5 HTTP clock sync gave ± 50 ms on a LAN.** NTP/SNTP was overkill for our matcher's 1.5 s `maxClockSkewMs` tolerance.
- **ML Kit `faceId` is the correct stickiness key.** Keying identity bindings on `faceId` (stable until the face leaves) outperforms keying on geometric centroid.
- **Backwards-compatible JSON extensions beat a v2 endpoint.** Adding `server_time_ms` + `frame_sequence` to `frame_update` without a protocol version bump let old Android builds keep running unchanged.
- **Observability first.** The diagnostic HUD (FPS / skew / binding counts / seq-gap) is how you know the pipeline is healthy without grepping logcat. Red-thresholded metrics catch regressions faster than raw numbers.
- **Matcher, overlay, fallback controller: one domain, three concerns, three files.** Separation keeps each piece ≤ 300 lines and independently testable.
- **Explicit mode enum beats booleans-in-booleans.** `HybridMode { HYBRID, BACKEND_ONLY, DEGRADED, OFFLINE }` names its own transitions; a pair of booleans would have left the reader to infer semantics.
- **Tick-based state machines are simpler than event-driven when all transitions are time-based.** `HybridFallbackController` re-evaluates every 500 ms; no event plumbing needed.
- **Observability-first HUD pays for itself.** Once the HUD was up, threshold tuning became "watch the red numbers disappear" instead of guesswork.
- **Validation ≠ code done.** The code landed, but the on-device scenario matrix (`10-integration-validation-docs.md` §3) still needs a real device + live RTSP. That's deferred to the next physical test session; don't declare shipped until those boxes are ticked.
- **Unattended parallel sessions can drift.** Session 06 and Session 10 both were reported as done in a grouped commit that didn't implement them. Always audit the diff — trust, but verify.

---

## 2026-04-24: System Activity timeline — design lessons

Planning the unified `activity_events` feature (real-time + historical event stream for thesis defense). What the design review taught us:

- **Verify "dead wiring" claims before assuming greenfield.** Initial research concluded `log_audit()` had no call sites; Plan-agent caught one at `face.py:298`. The convention existed, just underused. When wrapping or replacing a helper, grep for call sites in both directions (model exists? helper exists? call sites?) before deciding scope.
- **Prefer "extend what exists" over "new parallel infra" for WS fanout.** Tempting to create a new Redis channel `iams:events`. Right move was a subchannel under the existing `REDIS_WS_CHANNEL` with one new routing branch in the existing `_redis_subscribe_loop`. Adds one if/elif; avoids a second pubsub connection, second subscriber task, second reconnect loop. Apply this lens whenever adding real-time features — find the closest existing multiplexer.
- **Thesis-grade evidence requires immutable rows, not computed views.** A view-of-unions feels clean but shifts if the underlying service logic shifts. Written-once event rows are reproducible evidence. For a thesis defense, prefer the row-ful architecture even at a small storage/complexity cost.
- **Share the caller's transaction for audit/activity writes.** `emit_event()` defaults to `db.flush()` (not commit) and reuses the caller's session. Event rows become atomic with their state change — no orphan events, no missing events. Only standalone callers (with no existing tx) pass `autocommit=True`.
- **Cardinality gating for real-time events must happen at the emit site, not the consumer.** Emitting every FAISS frame would swamp the WS. The existing `_recognized_captured: set[(user_id, track_id)]` in `realtime_pipeline.py` gives us one emission per tracker identity transition for free. When adding real-time events, look for an existing state-set or invariant that already has the cardinality you want before adding downsampling logic downstream.
- **FK `ondelete="SET NULL"` for thesis evidence tables.** Activity log must outlive PII deletion. All `subject_*_id` and `actor_id` FKs use SET NULL; `ref_*` drilldown columns carry no FK constraint at all (detail rows may be pruned by retention policy).
- **Admin-only for WS + REST.** A WS stream of all activity can exfiltrate other students' check-in events if exposed to faculty/student roles. Check `payload.get("role") == "admin"` in the WS handler and close 4003 otherwise; use `get_current_admin` on REST routes.
- **One-direction unification between audit and activity.** `log_audit()` calls `emit_event()` internally — but service-driven `emit_event()` calls do NOT call `log_audit()`. Many activity events (RECOGNITION_MATCH, MARKED_PRESENT) are system-driven, not admin actions. Document this contract in both helpers.
- **`init_db()` vs Alembic schema drift.** Lifespan calls `init_db()` (main.py:89) before Alembic migrates. Old DBs without a table will auto-create from the SQLAlchemy model, NOT the migration. Column types, server_defaults, and indexes MUST be identical between model and migration — match the recognition_events migration pattern exactly.
- **Client-side buffer cap on pause.** Real-time feeds buffer events while paused. At 50 events/min a 30-minute pause = 1500 events; at peak could be much more. Cap client buffer at 5,000 with oldest-drop policy and an overflow banner. Same pattern Dozzle uses.

---

## 2026-04-25: Live-feed overlay — honest, fast, frame-pinned (plan)

Planning the three-step fix for "bounding box drifts onto the wrong person at 1.5 fps". What the design review taught us:

- **Smoothness on a slow source is a lie that turns into bug reports.** The admin overlay had snap-then-lerp interpolation + velocity extrapolation on top of a backend stuck at 1.5 fps. The "smooth" movement was extrapolating along a stale velocity for 500 ms while the face had already moved or left frame — looked like the box was glued to the wrong person. Default to "honest blink at backend rate" before reaching for client interpolation; only add interpolation when the backend rate is genuinely high enough that interpolation is just polish, not papering-over.
- **The Apple Neural Engine path for InsightFace requires *static* ONNX shapes.** `buffalo_l` ships SCRFD with dynamic input shapes. Putting `CoreMLExecutionProvider` first in the providers list does nothing in that case — the EP refuses to delegate dynamic-shape graphs and silently falls back to CPU. The fix is re-exporting the ONNX with `onnx.tools.update_model_dims.update_inputs_outputs_dims` to bake in `[1, 3, 960, 960]`, then `onnxsim.simplify()`. Verify by logging the actual provider each model picked after `app.prepare()`, not by trusting the providers-list config.
- **For overlay-on-video alignment, the upstream RTP timestamp is the only clock all consumers share.** Backend wall-clock + WHEP `video.currentTime` align *by accident* because typical jitter buffers happen to roughly match pipeline latency — they're on different clocks. The right primitive is the RTSP source's RTP 90 kHz timestamp, propagated through both the FFmpeg grabber (`-copyts -fps_mode passthrough -progress pipe:3`) and `requestVideoFrameCallback().rtpTimestamp` on the browser side. Both consumers are downstream of the local mediamtx, so the upstream timestamp is the same value on both sides.
- **`requestVideoFrameCallback().rtpTimestamp` is Chromium-only.** Not part of the WebRTC spec proper. Acceptable for the admin live page (Brave/Chrome on the Mac), but ship the Step-1 "blink" path as the Safari fallback so the aligner gracefully degrades.
- **Three independently-deployable phases beat one big-bang refactor.** Step 1 (overlay strip) is one-file, ~10 minutes, fixes the most user-visible issue. Steps 2 and 3 are gated on observing Step 1's result. The plan's rollout sequence enforces "land in order; do not bundle" and gives a per-step rollback.
- **Backend-already-broadcasts-X is not a free lunch.** `velocity` was on the wire and read only by `DetectionOverlay.tsx`; Android `Models.kt` declares but never reads it. Removing from the wire would have been backwards-compatible but coordinating a backend redeploy with the frontend deploy doubles the rollout risk. Cheaper to leave the field broadcast and just stop reading it client-side — keeps Step 1 a pure single-file change with zero coordination cost.
