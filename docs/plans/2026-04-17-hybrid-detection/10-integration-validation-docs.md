# Session 10 — Integration Validation, Tuning, and Documentation

**Deliverable:** end-to-end test plan executed on-device, tuned config values committed, docs updated, CLAUDE.md brought current.
**Blocks:** final merge to main.
**Blocked by:** ALL other sessions (01-09).
**Est. effort:** 4 hours.

---

## 1. Scope

Ship the feature. This session is the gate: it only runs after every other session is merged into `feat/architecture-redesign`. It validates the whole stack works end-to-end, tunes the matcher/config thresholds against real video, and updates the project's CLAUDE.md + implementation doc so future Claude sessions start from a correct architecture description.

## 2. Files

| Path | New / Modified |
|------|----------------|
| `CLAUDE.md` | MODIFIED (architecture section + user flows + tech details) |
| `docs/main/implementation.md` | MODIFIED (hybrid subsection) |
| `docs/plans/2026-04-17-hybrid-detection/TUNING.md` | NEW — final threshold values + rationale |
| `memory/lessons.md` | MODIFIED — append lessons from all 10 sessions |
| `android/app/src/androidTest/java/com/iams/app/hybrid/LiveFeedHybridE2ETest.kt` | NEW (optional instrumented test — see §6) |

## 3. On-device test matrix

Run these on a Pixel 6a (mid-range) and a Samsung A54. Each takes ≤ 10 min.

### 3.1 Golden path
1. Start local backend (`docker compose up -d`), seed data, confirm `/health/time` returns epoch ms.
2. Start RTSP fake source from a test video with 2 enrolled faces.
3. Launch app, log in as faculty, open Live Feed.
4. **Expect:** video renders, green boxes at 30 fps on both faces within 500 ms, correct names, skew < 100 ms in HUD.

### 3.2 WebSocket interruption
1. During a golden-path session, `adb shell cmd wifi set-wifi-enabled disabled`.
2. **Expect:** boxes continue (ML Kit), go from BOUND to COASTING (dimmed green) after 100 ms, labels still show. HUD shows RTT = -1, mode = DEGRADED after 3 s.
3. Wait 5 s, re-enable Wi-Fi.
4. **Expect:** within 2 s, names refresh (BOUND again), mode = HYBRID.

### 3.3 Backend down
1. `docker compose stop api-gateway`.
2. **Expect:** WS drops. Boxes continue following faces (ML Kit). Mode transitions to DEGRADED then OFFLINE (after 3 s). Labels become "Unknown" after 3 s identity-hold.
3. `docker compose start api-gateway`.
4. **Expect:** WS reconnects, names re-appear, no crash.

### 3.4 ML Kit unavailable
1. Revoke camera permissions OR force-disable Play Services (use a test APK variant).
2. **Expect:** mode = BACKEND_ONLY. Legacy `InterpolatedTrackOverlay` shows boxes. No crash.

### 3.5 Identity swap stress
1. Two enrolled students stand adjacent, cross paths, swap positions.
2. **Expect:** names stay with the correct face. No flipping. (If flipping: raise `iouBindThreshold` to 0.5, raise `firstBindGraceMs` to 800 ms.)

### 3.6 Long-running stability
1. Leave Live Feed open for 30 min on each device.
2. **Expect:** no memory growth in Android Studio Profiler (flat Java heap), no battery drain > 8 %, no frame rate degradation.

### 3.7 Multi-face load
1. Use a test video with 10 faces (screenshots of registered students).
2. **Expect:** all 10 boxes render, backend FPS stays > 15 in HUD, ML Kit FPS stays > 12.

## 4. Threshold tuning

Record HUD snapshots for each test, fill in `TUNING.md`:

```markdown
# Hybrid Detection — Final Tuning (2026-04-17)

| Setting | Starting | Final | Rationale |
|---------|----------|-------|-----------|
| MatcherConfig.iouBindThreshold | 0.40 | ??  | bump if identity swaps observed in 3.5 |
| MatcherConfig.iouReleaseThreshold | 0.20 | ?? | bump if coasting flickers |
| MatcherConfig.identityHoldMs | 3000 | ??  | lower if stale-name complaints |
| MatcherConfig.firstBindGraceMs | 500 | ??  | |
| HybridFallbackController mlkitSilenceTimeoutMs | 2000 | ??  | |
| HybridFallbackController wsSilenceTimeoutMs | 3000 | ??  | |
```

Apply final values via a small PR against whichever file holds the defaults (Session 01's `MatcherConfig` companion, Session 09's `Config` data class).

## 5. Docs updates

### `CLAUDE.md`
- Update the architecture diagram in §1 to show the hybrid flow (ML Kit on phone + backend).
- Update §1 text: "ML Kit runs on the Android phone for face detection" — currently this is technically true of the legacy CLAUDE.md but the live-feed path had been backend-only. Re-confirm it now reflects the hybrid truth.
- Add a row to the "Key Technical Details" section:
  > **Hybrid Detection:** ML Kit on phone owns bbox positions (30 fps); backend owns identity recognition (20 fps via SCRFD+ArcFace). `FaceIdentityMatcher` binds them via IoU. Feature-flagged via `BuildConfig.HYBRID_DETECTION_ENABLED`.

### `docs/main/implementation.md`
Add a new subsection:
- What hybrid is, why it exists.
- Links to this plan folder.
- Tuning thresholds (copy from `TUNING.md`).

### `memory/lessons.md`
Append (per CLAUDE.md "Plan Mode: Lesson Capture"):

```
## 2026-04-17: Hybrid detection — master lessons

- Parallel sessions only work if contracts are frozen in a master plan before any session starts.
- The backend does NOT need to change for most live-feed UX improvements — client-side gains are huge.
- `MlKitFrameSink` was already correct; integration was pure plumbing.
- Feature-flagging from day one saved at least one rollback.
- Median-of-5 HTTP clock sync gave ± 50 ms; NTP was overkill.
- ML Kit `faceId` is the right stickiness key for matching.
- IoU 0.40 bind / 0.20 release is stable; Hungarian not needed below ~20 faces.
```

## 6. Optional: Instrumented E2E test

`LiveFeedHybridE2ETest.kt` using Compose Test + fake WS server. Out-of-scope if time-boxed; add a TODO comment in the file linking back to this plan.

## 7. Acceptance criteria

- [ ] All scenarios in §3 pass on both devices.
- [ ] `TUNING.md` committed with final values.
- [ ] CLAUDE.md and `docs/main/implementation.md` reflect the hybrid architecture.
- [ ] `memory/lessons.md` updated.
- [ ] PR 10 merges; `feat/architecture-redesign` branches sees GREEN CI.
- [ ] Merge to `main` with `bash deploy/deploy.sh` **only when the user approves** (per project policy).

## 8. Anti-goals

- Do not change implementation code unless tuning reveals a concrete bug — file a follow-up issue instead.
- Do not ship new features here.
- Do not deploy to VPS without explicit user approval (project CLAUDE.md policy).
- Do not skip the 30-min stability test — it's the main regression detector.

## 9. Handoff notes

After this PR merges, the feature is live in debug builds. Release builds need the `HYBRID_DETECTION_ENABLED` flag flipped to `true` in `release` buildType of `app/build.gradle.kts` — that's a separate one-line PR after 1 week of debug-build soak.

## 10. Risks

- **Regression in legacy path:** with `HYBRID_DETECTION_ENABLED=false`, must behave exactly as pre-plan. Test scenario 3.4 covers it.
- **On-device timing variance:** thresholds tuned on Pixel 6a may under-perform on a lower-tier device. Document device baseline in `TUNING.md`.
- **User-visible color semantics:** the green/orange/dimmed-green/blue palette is opinionated. If faculty don't like it, iterate in a follow-up.

## 11. Commit message template

```
hybrid(10): e2e validation, tuning, docs

Runs the §3 test matrix on Pixel 6a and Samsung A54, records final matcher
and fallback thresholds in TUNING.md, updates CLAUDE.md and implementation.md
to describe the hybrid architecture, and appends master lessons to memory.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 12. Lessons

- Validation session = "day 0 of maintenance". If you can't describe how it broke in §3 scenarios, future-you won't be able to either.
- TUNING.md separate from code so future Claude sessions can read rationale, not just values.
