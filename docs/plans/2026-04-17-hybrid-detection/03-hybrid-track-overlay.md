# Session 03 — HybridTrackOverlay

**Deliverable:** the Compose overlay that renders ML Kit-positioned boxes with matcher-supplied identities at 30 fps.
**Blocks:** session 06, 08, 09.
**Blocked by:** session 01 (reads its types).
**Est. effort:** 4 hours.

Read [00-master-plan.md](00-master-plan.md) §5.1 (shared types) and session 01 plan (matcher API). Copy styling decisions from [InterpolatedTrackOverlay.kt](../../../android/app/src/main/java/com/iams/app/ui/components/InterpolatedTrackOverlay.kt).

---

## 1. Scope

New composable that replaces `InterpolatedTrackOverlay` in the hybrid code path. Inputs are:

- `tracks: List<HybridTrack>` — from `matcher.tracks`.
- `videoFrameWidth`, `videoFrameHeight` — from `MlKitFrameSink.frameSize` (session 02).
- `isVideoReady: Boolean` — same as legacy overlay.

Outputs: Canvas draws boxes + labels. No side effects, no state mutation of inputs.

## 2. Files

| Path | New? |
|------|------|
| `android/app/src/main/java/com/iams/app/ui/components/HybridTrackOverlay.kt` | NEW |

## 3. Implementation steps

### Step 1 — Composable signature

```kotlin
@Composable
fun HybridTrackOverlay(
    tracks: List<HybridTrack>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0,
    isVideoReady: Boolean = true,
    showCoasting: Boolean = true,
)
```

### Step 2 — Local render state

Unlike `InterpolatedTrackOverlay`, we do NOT need snap interpolation because ML Kit already delivers new positions at 30 fps. Draw directly from `track.bbox`. Keep only:

```kotlin
private class TrackRenderState(
    val alpha: Animatable<Float, *>,
    var lastSeenNs: Long,
)
```

Keyed by `mlkitFaceId`.

### Step 3 — Fade in/out

Use the same 150 ms fade-in / 300 ms fade-out from `InterpolatedTrackOverlay:91-109`. When an `mlkitFaceId` stops appearing in `tracks`, start fade-out; remove state when alpha < 0.01 f.

### Step 4 — Aspect-fit mapping

Copy the crop-offset calculation from `InterpolatedTrackOverlay:182-202` verbatim — it's the same video surface, same math. Use `videoFrameWidth`/`videoFrameHeight` from the ML Kit sink (session 02).

### Step 5 — Draw loop

Inside `drawWithCache { onDrawBehind { ... } }`:

```kotlin
for (track in tracks) {
    val state = renderStates[track.mlkitFaceId] ?: continue
    val alpha = state.alpha.value * fadeMultiplier
    if (alpha < 0.01f) continue

    // Suppress "MLKIT_ONLY" tracks younger than 800ms to avoid flashing boxes for
    // transient false positives (same rule as InterpolatedTrackOverlay line 220).
    if (track.source == HybridSource.MLKIT_ONLY) {
        val age = now - state.createdNs
        if (age < 800_000_000L) continue
    }

    // Don't render coasting tracks if caller disabled it.
    if (track.source == HybridSource.COASTING && !showCoasting) continue

    val boxColor = when (track.source) {
        HybridSource.BOUND       -> Color(0xFF4CAF50).copy(alpha = alpha)  // green: identity fresh
        HybridSource.COASTING    -> Color(0xFF8BC34A).copy(alpha = alpha * 0.9f) // dimmed green: identity held
        HybridSource.MLKIT_ONLY  -> Color(0xFFFF9800).copy(alpha = alpha)  // orange: detected, no identity
        HybridSource.FALLBACK    -> Color(0xFF2196F3).copy(alpha = alpha)  // blue: backend-only mode
    }

    val (left, top, right, bottom) = mapNormalizedToCanvas(track.bbox, ...)
    drawRect(color = boxColor, topLeft = Offset(left, top),
             size = Size(right - left, bottom - top),
             style = Stroke(width = 2.5f))

    val label = when {
        track.identity.status == "recognized" && !track.identity.name.isNullOrEmpty() ->
            track.identity.name!!
        track.source == HybridSource.MLKIT_ONLY -> "Detecting…"
        else -> "Unknown"
    }
    drawNameLabel(textMeasurer, label, left, top, boxColor, alpha)
}
```

Reuse `drawNameLabel` — copy it verbatim from `InterpolatedTrackOverlay.kt:285-311`.

### Step 6 — 30 fps invalidation

Same `withFrameNanos` loop as the legacy overlay (`InterpolatedTrackOverlay:79-89`) to trigger re-draw at 30 fps.

## 4. Acceptance criteria

- [ ] Compiles; no Compose warnings.
- [ ] With a static list of 3 fake `HybridTrack`s (use `@Preview` composable), all three boxes render in the right positions and colours.
- [ ] Fade-in is visible when a new face appears (eye test: not an instant pop).
- [ ] Fade-out is visible when a face leaves (300 ms smooth).
- [ ] `showCoasting = false` hides coasting tracks.
- [ ] Labels are clipped to one line; oversized names truncate with ellipsis (reuse Compose `TextOverflow.Ellipsis`).
- [ ] No frame drops under Android Studio Layout Inspector during profiling (aim for < 1 ms compose recomposition per frame — `drawWithCache` handles this).

## 5. Anti-goals

- Do not interpolate — ML Kit already gives high-rate positions.
- Do not read from the matcher directly — the overlay takes its input via parameter.
- Do not manage the matcher lifecycle.
- Do not log drawing events.
- Do not preview against real backend data — use a fake list.

## 6. Handoff notes

**For Session 06:** replace `InterpolatedTrackOverlay(tracks=...)` call site at [FacultyLiveFeedScreen.kt:413](../../../android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedScreen.kt#L413). When `BuildConfig.HYBRID_DETECTION_ENABLED` is false, keep `InterpolatedTrackOverlay`. When true, use `HybridTrackOverlay(tracks = matcher.tracks.collectAsStateWithLifecycle().value, ...)`.

**For Session 08 (HUD):** expose a debug tint via `overlayAlpha` multiplier — HUD can dim overlay to 0.5 to make the HUD legible.

## 7. Risks

- **Colour blindness:** the green/orange pairing is problematic. Use shape differences (2.5 px solid for BOUND, 2.5 px dashed for COASTING) as a secondary cue. Add to Session 10's tuning checklist.
- **Label collision when two faces are adjacent:** InterpolatedTrackOverlay has the same issue; out of scope for this session.
- **Remember-map growth:** `renderStates` must be pruned when an `mlkitFaceId` is absent for > 500 ms. Do this in the `LaunchedEffect(tracks)` block.

## 8. Commit message template

```
hybrid(03): add HybridTrackOverlay composable

Renders matcher-produced HybridTracks at 30fps using the native ML Kit
positions. Fade-in/out animations match InterpolatedTrackOverlay for
visual continuity. Color encodes source (bound/coasting/unbound/fallback).

Consumed by FacultyLiveFeedScreen in session 06.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 9. Lessons

- ML Kit's native 30 fps removes the need for snap interpolation — this is simpler than the legacy overlay, not more complex.
- Source enum on the data side lets the overlay stay pure drawing code.
