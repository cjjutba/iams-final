# Fullscreen + Pinch-to-Zoom for Faculty Live Feed

**Date:** 2026-04-10
**Status:** Approved

## Overview

Add fullscreen mode with pinch-to-zoom to the Faculty Live Feed screen (`FacultyLiveFeedScreen`). Applies to all classroom feeds since they share the same screen.

## Approach

In-place fullscreen toggle within the existing `FacultyLiveFeedScreen` — no new screens or navigation routes. A boolean state controls which layout parts are visible.

## Design

### State

- `isFullscreen: Boolean` — toggles normal vs fullscreen layout
- `scale: Float` — zoom level, 1.0x to 3.0x
- `offset: Offset` — pan position, clamped to video bounds

### Normal Mode (unchanged)

```
Column(fillMaxSize)
├── IAMSHeader
├── ConnectionStatusBar
├── SessionControlBar
└── Column
    ├── Box (video + overlay + fullscreen button)
    └── Column (bottom panel)
```

### Fullscreen Mode

```
Box(fillMaxSize, black background)
└── Box (transformable: pinch-zoom + pan, graphicsLayer)
    ├── NativeWebRtcVideoPlayer (fillMaxSize)
    ├── HybridFaceOverlay (fillMaxSize)
    └── Exit fullscreen button (top-right, semi-transparent, auto-hide after 3s)
```

### Fullscreen Toggle

**Enter:** Tap fullscreen icon (bottom-right of video) →
1. `isFullscreen = true`
2. Force landscape orientation
3. Enable immersive mode (hide system bars)
4. Reset zoom to 1x

**Exit:** Tap exit button (top-right) OR press Back →
1. `isFullscreen = false`
2. Restore portrait orientation
3. Restore system bars
4. Reset zoom

### Pinch-to-Zoom (fullscreen only)

- Compose `transformable` modifier + `rememberTransformableState`
- Zoom: 1.0x–3.0x
- Pan: only when scale > 1.0, clamped to bounds
- Applied via `graphicsLayer { scaleX, scaleY, translationX, translationY }` on the Box containing both video and overlay — keeps bounding boxes aligned

### Fullscreen Button

- **Normal mode:** bottom-right of video, `Icons.Default.Fullscreen`, semi-transparent dark bg
- **Fullscreen mode:** top-right, `Icons.Default.FullscreenExit`, auto-hides after 3s of no interaction, tap video to show again

### UI in Fullscreen

Video + face overlay + exit button only. No panel, no header, no session bar.

## Files Changed

- `FacultyLiveFeedScreen.kt` — all changes here (state, conditional layout, zoom, orientation, immersive mode, button)

No changes to: `NativeWebRtcVideoPlayer.kt`, `HybridFaceOverlay.kt`, `MlKitFrameSink.kt`, navigation, or ViewModel.
