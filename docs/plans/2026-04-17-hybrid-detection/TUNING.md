# Hybrid Detection — Tuning Log

Date opened: 2026-04-17
Last updated: 2026-04-17

## 1. Threshold defaults (as shipped)

These are the values landed in code at session-06 merge time. They are the starting point for on-device tuning in §3. **Not yet validated against a live RTSP feed** — see §4.

### Matcher (`MatcherConfig` in `com.iams.app.hybrid.HybridTypes`)

| Field | Value | Meaning |
|-------|-------|---------|
| `iouBindThreshold` | `0.40f` | Minimum IoU for a new ML Kit ↔ backend pairing. |
| `iouReleaseThreshold` | `0.20f` | Once bound, keep the binding fresh as long as IoU stays above this (sticky release). |
| `identityHoldMs` | `3_000L` | After losing the backend track, show the last known identity in COASTING mode for this long. |
| `firstBindGraceMs` | `500L` | Protect a fresh binding from being overwritten by a pending backend claim younger than this. |
| `maxClockSkewMs` | `1_500L` | Reserved for future clock-skew gating. Matcher currently does not apply it directly; `TimeSyncClient` publishes the measured skew for the HUD. |
| `backendStalenessMs` | `2_000L` | Reserved; see `HybridFallbackController.Config.wsSilenceTimeoutMs` for the effective value. |

### Fallback controller (`HybridFallbackController.Config`)

| Field | Value | Meaning |
|-------|-------|---------|
| `mlkitSilenceTimeoutMs` | `2_000L` | ML Kit silent longer than this → `BACKEND_ONLY`. |
| `wsSilenceTimeoutMs` | `3_000L` | Backend WS silent longer than this → `DEGRADED` (or `OFFLINE` when combined with ML Kit silence). |
| `rttWarningMs` | `1_500L` | HUD turns the RTT row red above this threshold. |
| `tickIntervalMs` | `500L` | How often the controller re-evaluates modes. |

### Time-sync (`DefaultTimeSyncClient`)

| Field | Value | Meaning |
|-------|-------|---------|
| `POLL_INTERVAL_MS` | `60_000L` | One `/api/v1/health/time` request per minute. |
| `MAX_RTT_MS` | `2_000L` | Samples with RTT above this are discarded. |
| `WINDOW_SIZE` | `5` | Rolling window; skew is median of the window. |

### Diagnostic HUD red-alert thresholds

| Metric | Threshold |
|--------|-----------|
| ML Kit FPS | below `10f` |
| Backend FPS | below `8f` |
| `|skew|` | above `1500 ms` |
| RTT | above `500 ms` |
| Seq gap | any non-zero |

## 2. On-device test matrix status

Taken from session plan [10-integration-validation-docs.md §3](10-integration-validation-docs.md). Fill each row during a real-device soak.

| # | Scenario | Pass? | Notes |
|---|----------|-------|-------|
| 3.1 | Golden path — boxes @30 fps, names within 500 ms | ☐ pending | Needs RTSP source + enrolled students. |
| 3.2 | Wi-Fi off for ≤ 3 s → COASTING, recover within 2 s | ☐ pending | `adb shell svc wifi disable` |
| 3.3 | `docker compose stop api-gateway` mid-session | ☐ pending | Expect OFFLINE after 3 s, graceful recovery. |
| 3.4 | Camera permission revoked → `BACKEND_ONLY` legacy overlay | ☐ pending | Flip via Settings during live feed. |
| 3.5 | Two enrolled students cross paths, no name-flipping | ☐ pending | Tune `iouBindThreshold` higher if it flips. |
| 3.6 | 30-min stability soak — heap flat, FPS steady | ☐ pending | Android Studio Profiler. |
| 3.7 | Multi-face load (10 faces) — backend > 15 fps, ML Kit > 12 fps | ☐ pending | Synthetic video of 10 photos. |

## 3. Tuning change log

Any value change must land in this table along with the code diff.

| Date | Setting | Old | New | Why |
|------|---------|-----|-----|-----|
| 2026-04-17 | — | — | — | Baseline: values above are the initial ship. |
| 2026-04-18 | `iouBindThreshold` | `0.40f` | `0.20f` | First real on-device run on production VPS showed boxes stuck on "Detecting…" even though the Detected panel had the correct identity. Root cause: at `PROCESSING_FPS=10` + ~50-150ms WAN latency, backend bboxes arrive ~100-250ms after ML Kit detected the same face. Even modest head motion in that window drops IoU below 0.40 → binding never forms. Lowering to 0.20 (matches the sticky-release floor) restores binding without enabling swaps — greedy assignment still picks the highest-IoU pair first. |
| 2026-04-18 | `iouReleaseThreshold` | `0.20f` | `0.15f` | Paired with the bind change: keeps the release floor strictly below the bind floor so a freshly bound pair can't instantly release when IoU dips at the boundary. |

## 4. Validation status

**The on-device test matrix has not been executed as of 2026-04-17.** Session 10's plan calls for running it on a Pixel 6a and Samsung A54; that pass is deferred to the next physical test session. The code and HUD are ready; once someone has real hardware + a live (or faked) RTSP source, they should:

1. Build a debug APK: `./gradlew assembleDebug`.
2. Run through each scenario in §2 and mark pass/fail with notes.
3. Tune any failing threshold via §3 and re-run the affected scenario.
4. Commit the updated TUNING.md.

## 5. Known gotchas noted during implementation

- `FaceIdentityMatcher` is single-threaded by contract (master-plan §5.5). The ViewModel routes every matcher call through a `Dispatchers.Default.limitedParallelism(1)` — do not call the matcher from any other dispatcher without serialising there first.
- The matcher is `@ViewModelScoped`, not `@Singleton`. A fresh matcher is created every time faculty open the Live Feed; its state is intentionally per-session.
- `HYBRID_DETECTION_ENABLED` defaults to `true` in `buildConfigField`. Flip it to `false` for the release build until scenario 3.1 has been validated on real hardware.
- `TimeSyncClient` hits the backend once a minute. On a misconfigured VPS with a big clock drift it will publish a large skew but not retry faster — that's intentional. The backend clock should be `systemd-timesyncd` synced.
- The HUD defaults to visible in debug. Long-press the video area to hide it. In release builds, it defaults to hidden (no long-press handler registers; see `FacultyLiveFeedScreen`).
