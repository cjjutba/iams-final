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
