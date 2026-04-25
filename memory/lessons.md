# Lessons

Append-only log of planning/implementation lessons worth keeping for future sessions. Read at the start of every session per project CLAUDE.md policy.

---

## 2026-04-25: Don't put admin WHEP on the same path as the FrameGrabber

Tried switching the admin live page from sub → main for sharper demo footage. Result: black screen with WebRTC negotiation hanging, plus the lag we'd just fixed came right back. Symptom is intermittent — sometimes the connection completed and worked for a few seconds before stalling.

Root cause is multi-reader contention on the same mediamtx path. The api-gateway's `FrameGrabber` is permanent (always-on for every camera-equipped room since the 2026-04-25 always-on-grabbers change). It holds a long-lived RTSP reader on `eb226`. When the browser opens a WHEP session on the same `eb226` path, mediamtx must fan the publisher's frames to two consumers; their keyframe-wait windows can collide and the WebRTC negotiation stalls before the first frame is presented. The original code's comment about "WebRTC jitter buffer drift over long sessions" was understating it — under the always-on-grabber regime the contention shows up immediately, not just over hours.

The architectural fix isn't trivial: you'd need a third mediamtx path (`eb226-display`) fed by an ffmpeg `-c copy` fanout from the cam-relay supervisor, so admin display and ML pipeline read from physically separate paths even though the source is one camera. Until that exists, **the admin display MUST use the sub path**. Don't try to "make main work" with WHEP tuning — the contention is at the publisher fanout layer, not the receiver buffer.

Reverted by restoring `displayStreamKey = ${streamKey}-sub` in [admin/src/routes/schedules/[id]/live.tsx](admin/src/routes/schedules/%5Bid%5D/live.tsx). Kept the `playoutDelayHint=0` + `writeQueueSize=128` lat-cut from the same session — those fixed real lag with sub and remain valid.

---

## 2026-04-25: ML sidecar — native CoreML escape hatch from Docker

Built a native macOS Python sidecar (`backend/ml-sidecar/`) that the api-gateway proxies its realtime SCRFD + ArcFace calls to via `host.docker.internal:8001`. The win is single-line: ONNX Runtime built for Linux ships without `CoreMLExecutionProvider`, so InsightFace inside the Docker container is permanently pinned to CPU even on an M5. Moving inference to a native process gets `["CoreMLExecutionProvider", "CPUExecutionProvider"]` and the Apple Neural Engine starts doing real work.

Key non-obvious details I'd forget without writing them down:

- **Static-shape ONNX is mandatory for CoreML to delegate.** `buffalo_l` ships with dynamic input shapes; ORT's CoreML EP silently falls back to CPU on dynamic graphs. The codebase already had `backend/scripts/export_static_models.py` for this — run it on the host to produce `~/.insightface/models/buffalo_l_static/`. The static pack name is wired through `INSIGHTFACE_STATIC_PACK_NAME` env. Without this step the sidecar boots, the providers list shows CoreML, but actual delegation is silently zero.
- **The gateway's `app.config.Settings` requires `DATABASE_URL`.** The sidecar reuses `InsightFaceModel` from `app.services.ml`, which transitively imports `app.config`. Setting `os.environ.setdefault("DATABASE_URL", "sqlite:///...")` *before* the import is enough to satisfy pydantic-settings without dragging in a real DB. Same trick disables Redis/background-jobs flags so the sidecar doesn't try to start a Redis subscriber.
- **`from X import Y` holds a stale reference.** Tried to monkey-patch `app.services.ml.insightface_model.insightface_model` at runtime; `realtime_pipeline.py` had already `from ... import insightface_model` so its local name still pointed at the old object. Solution: `app.services.ml.inference.get_realtime_model()` selector, called inside `SessionPipeline.start()` instead of importing the module symbol at file load.
- **Failover policy: degrade, don't refuse.** If `ML_SIDECAR_URL` is set but `/health` fails at gateway boot, the lifespan binds the in-process model anyway and logs a warning. A wedged sidecar shouldn't take the API down — same pattern as cam-relay being optional for non-camera operations.
- **macOS 26 TCC + launchd is a known trap.** Same reason `iams-cam-relay.sh` uses nohup+disown instead of a LaunchAgent: ffmpeg/uvicorn spawned by launchctl get sandboxed in ways that block local-network reads. The sidecar follows the same pattern.
- **Reusing `InsightFaceModel` in the sidecar saved ~200 lines of code.** Tempting to write a "minimal" sidecar from scratch with raw onnxruntime calls. Don't. The model class already handles thread-count tuning, static-pack resolution, provider introspection, and warmup. The sidecar wrapping is ~250 lines because the heavy lifting is already in `app.services.ml.insightface_model`.
- **JPEG transport is the right pragmatic choice.** Considered raw mmap, multipart, gRPC. JPEG-encode (~5-10ms) + base64 + JSON is ~10ms total per request, dwarfed by the speedup. Optimize later if profiling actually flags this. Don't pre-optimize.
- **Two endpoints (`/detect` and `/embed`), not one combined.** The realtime tracker's tri-state recognition relies on calling SCRFD every frame but ArcFace only on tracks needing identity work. A combined endpoint forced ArcFace on every detected face every frame, defeating the optimization. Two endpoints preserve the existing ML-budget design.

---

## 2026-04-25: Strict session-gated ML + boot-time warmup

The user observed multi-minute cold starts on the admin live page when no session was running, then asked us to remove preview pipelines entirely. Killing preview without addressing cold-start would have just shifted the lag from "viewer connect" to "session start" — equally bad for the demo. The fix is the policy + the warmup together, not either alone.

- **Cold-start has multiple sources, not one.** RTSP I-frame wait (~5-15 s), FFmpeg first-frame buffering, ONNX Runtime SCRFD JIT (~3-5 s on M5 at det_size=960), and FAISS hydration each contribute. Skipping any one of them leaves a visible lag. The warmup pass at boot is one synthetic `detect()` call on a noise frame — that's enough to JIT SCRFD because ORT optimises per-graph on first call.
- **Always-on FrameGrabbers cost ~10-15 % idle CPU on the M5 for two H.264 main streams** (decode-and-discard). That's the price of "session start feels instant." Cheaper than running ML 24/7, and dramatically nicer than a 30-90 s cold-start gap right at the moment a real class begins.
- **Strict session gating ≠ "ML always off".** ML still runs full-tilt during real sessions. The gating just means there's no hidden preview pipeline burning cycles when nobody's actually attending class. The live page still works out-of-window — it just shows raw WHEP video without overlays, which is exactly what the user asked for.
- **`preview_mode` was load-bearing in three files.** main.py created/destroyed preview pipelines, presence.py's manual Start Session swapped a preview for a full pipeline, websocket.py's disconnect handler reaped previews. Removing it cleanly required tracking down all three. The compile-test catches the syntax errors but not the missing call sites — `grep` for the symbol across the whole repo before declaring it dead.
- **Don't let `if not self._preview_mode:` rot into the codebase.** SessionPipeline accumulated 6 of those guards before we removed preview_mode. Each one was correct in isolation, but together they made the file harder to scan. When a feature flag is killed, kill the guards in the same change — leaving them as "dead but working" makes future readers ask "is preview ever set true?" and waste time chasing a ghost.

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
