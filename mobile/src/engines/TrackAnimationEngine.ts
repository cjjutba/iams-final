import { Animated } from "react-native";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface FusedTrack {
  track_id: number;
  bbox: [number, number, number, number]; // [x, y, w, h] floats
  confidence: number;
  user_id: string | null;
  name: string | null;
  student_id: string | null;
  similarity: number | null;
  state: "confirmed" | "tentative";
  missed_frames: number;
}

export interface AnimatedTrack {
  trackId: number;
  x: Animated.Value;
  y: Animated.Value;
  w: Animated.Value;
  h: Animated.Value;
  opacity: Animated.Value;
  userId: string | null;
  name: string | null;
  studentId: string | null;
  similarity: number | null;
  missedFrames: number;
  lastSeen: number; // timestamp
}

// ── Constants ──────────────────────────────────────────────────────────────────

const SPRING_CONFIG = {
  stiffness: 300,
  damping: 25,
  mass: 0.8,
  useNativeDriver: false, // layout props can't use native driver
};

const FADE_IN_DURATION = 150; // ms
const FADE_OUT_DURATION = 300; // ms
const STALE_THRESHOLD = 3; // messages without track before fade-out
const MAX_POOL_SIZE = 20;

// ── Engine ─────────────────────────────────────────────────────────────────────

export class TrackAnimationEngine {
  private tracks: Map<number, AnimatedTrack> = new Map();
  private pool: AnimatedTrack[] = [];
  private missedCount: Map<number, number> = new Map();

  /**
   * Main update called at ~30 FPS.
   * Receives the latest fused tracks from the backend, reconciles with
   * existing animated tracks, and returns the current set for rendering.
   */
  update(incomingTracks: FusedTrack[]): AnimatedTrack[] {
    const now = Date.now();
    const incomingIds = new Set<number>();

    // 1. Process each incoming track
    for (const ft of incomingTracks) {
      incomingIds.add(ft.track_id);
      this.missedCount.set(ft.track_id, 0);

      const existing = this.tracks.get(ft.track_id);

      if (existing) {
        // Spring-animate position & size to new values
        this._animateTo(existing.x, ft.bbox[0]);
        this._animateTo(existing.y, ft.bbox[1]);
        this._animateTo(existing.w, ft.bbox[2]);
        this._animateTo(existing.h, ft.bbox[3]);

        // Update opacity: 1.0 normal, 0.5 if missed_frames > 0
        const targetOpacity = ft.missed_frames > 0 ? 0.5 : 1.0;
        this._animateTo(existing.opacity, targetOpacity);

        // Update metadata
        existing.userId = ft.user_id;
        existing.name = ft.name;
        existing.studentId = ft.student_id;
        existing.similarity = ft.similarity;
        existing.missedFrames = ft.missed_frames;
        existing.lastSeen = now;
      } else {
        // New track: create and fade in
        const track = this._createTrack(ft, now);
        Animated.timing(track.opacity, {
          toValue: ft.missed_frames > 0 ? 0.5 : 1.0,
          duration: FADE_IN_DURATION,
          useNativeDriver: false,
        }).start();
        this.tracks.set(ft.track_id, track);
      }
    }

    // 2. Handle tracks NOT in incoming (stale detection)
    const trackEntries = Array.from(this.tracks.entries());
    for (const [trackId, track] of trackEntries) {
      if (incomingIds.has(trackId)) continue;

      const missed = (this.missedCount.get(trackId) ?? 0) + 1;
      this.missedCount.set(trackId, missed);

      if (missed >= STALE_THRESHOLD) {
        // Fade out, then delete and return to pool
        Animated.timing(track.opacity, {
          toValue: 0,
          duration: FADE_OUT_DURATION,
          useNativeDriver: false,
        }).start(() => {
          this.tracks.delete(trackId);
          this.missedCount.delete(trackId);
          this._returnToPool(track);
        });
      }
    }

    return Array.from(this.tracks.values());
  }

  /** Return current animated tracks without mutation. */
  getAll(): AnimatedTrack[] {
    return Array.from(this.tracks.values());
  }

  /** Clear all tracks, pool, and missed counts. */
  clear(): void {
    // Stop any running animations
    for (const track of Array.from(this.tracks.values())) {
      track.x.stopAnimation();
      track.y.stopAnimation();
      track.w.stopAnimation();
      track.h.stopAnimation();
      track.opacity.stopAnimation();
    }
    this.tracks.clear();
    this.pool = [];
    this.missedCount.clear();
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  /** Spring-animate an Animated.Value to a target number. */
  private _animateTo(animValue: Animated.Value, target: number): void {
    Animated.spring(animValue, {
      toValue: target,
      stiffness: SPRING_CONFIG.stiffness,
      damping: SPRING_CONFIG.damping,
      mass: SPRING_CONFIG.mass,
      useNativeDriver: SPRING_CONFIG.useNativeDriver,
    }).start();
  }

  /**
   * Create an AnimatedTrack from a FusedTrack.
   * Tries to recycle from the pool first; otherwise allocates new Animated.Values.
   */
  private _createTrack(ft: FusedTrack, now: number): AnimatedTrack {
    const recycled = this.pool.pop();

    if (recycled) {
      // Reset recycled values to new positions (no animation on initial set)
      recycled.trackId = ft.track_id;
      recycled.x.setValue(ft.bbox[0]);
      recycled.y.setValue(ft.bbox[1]);
      recycled.w.setValue(ft.bbox[2]);
      recycled.h.setValue(ft.bbox[3]);
      recycled.opacity.setValue(0); // will fade in
      recycled.userId = ft.user_id;
      recycled.name = ft.name;
      recycled.studentId = ft.student_id;
      recycled.similarity = ft.similarity;
      recycled.missedFrames = ft.missed_frames;
      recycled.lastSeen = now;
      return recycled;
    }

    return {
      trackId: ft.track_id,
      x: new Animated.Value(ft.bbox[0]),
      y: new Animated.Value(ft.bbox[1]),
      w: new Animated.Value(ft.bbox[2]),
      h: new Animated.Value(ft.bbox[3]),
      opacity: new Animated.Value(0), // will fade in
      userId: ft.user_id,
      name: ft.name,
      studentId: ft.student_id,
      similarity: ft.similarity,
      missedFrames: ft.missed_frames,
      lastSeen: now,
    };
  }

  /** Return a track to the pool for reuse (up to MAX_POOL_SIZE). */
  private _returnToPool(track: AnimatedTrack): void {
    if (this.pool.length < MAX_POOL_SIZE) {
      this.pool.push(track);
    }
  }
}
