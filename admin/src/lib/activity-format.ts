/**
 * Display-time helpers for activity events.
 *
 * The backend emits some legacy summaries with raw UUIDs (e.g.
 * "Recognition match: user=bc104016-49d0-4f1a-8ce2-7fff8b816418
 *  track=214 confidence=0.68"). Newer emits build the summary with
 * the resolved name from the tracker name_map, but historical rows
 * already in postgres still carry UUIDs. To clean those up visually
 * without a backfill, the admin substitutes any UUID substring with
 * the API-enriched ``subject_user_name`` / ``actor_name`` when one of
 * those is present and matches the corresponding ID.
 *
 * Methodology copy lives here too — keyed off ``event_type`` so the
 * detail sheet can render a "How this is computed" section only for
 * events that actually have a formula. The numbers are static (as
 * configured at thesis writing time); see ``backend/app/config.py``
 * for the live values.
 */

import type { ActivityEvent } from '@/types'

/**
 * Replace any UUID in ``event.summary`` with a friendlier label
 * (subject name or actor name) when the IDs match. Preserves the
 * surrounding sentence so "user=<uuid> track=214" becomes
 * "user=Christian Jutba track=214".
 *
 * Falls back to the original summary when no substitution is possible
 * — older events without an enriched name will still show the UUID
 * rather than "[unknown]" because that's still useful evidence.
 *
 * Implementation note: this function is called on every list-row
 * render (124+ events on a busy schedule), so the previous version
 * tried to short-circuit with ``UUID_RE.test()``. That broke on every
 * other call because ``.test()`` on a /g regex advances ``lastIndex``
 * — a notorious JS gotcha. We just always run ``.replace()`` now;
 * it's a no-op on no-match anyway, and the regex is fresh per call.
 */
export function formatEventSummary(event: ActivityEvent): string {
  if (!event.summary) return event.summary

  // Build the substitution map from the IDs the API enriched. Multiple
  // distinct UUIDs can land in one summary in theory (e.g. an audit
  // payload that mentions an actor and a subject) so we look up each
  // one individually.
  const subs: Record<string, string> = {}
  if (event.subject_user_id && event.subject_user_name) {
    subs[event.subject_user_id] = event.subject_user_name
  }
  if (event.actor_id && event.actor_name) {
    subs[event.actor_id] = event.actor_name
  }

  if (Object.keys(subs).length === 0) return event.summary

  return event.summary.replace(
    /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/g,
    (uuid) => subs[uuid] ?? uuid,
  )
}

// ---------------------------------------------------------------------------
// Methodology — per-event-type "how is this computed" copy.
//
// The detail sheet renders this only when an entry exists for the event's
// type. Empty entries (admin actions, lifecycle events) intentionally
// have no methodology — there's no formula to explain.
// ---------------------------------------------------------------------------

export interface MethodologyEntry {
  /** One-line headline for the section. */
  title: string
  /**
   * Short body paragraphs. Rendered as separate <p> tags so multi-step
   * derivations can be broken up without HTML in the strings.
   */
  body: string[]
  /**
   * Optional pseudo-formula rendered in a code-style block.
   * Example: ``presence_score = (scans_present / total_scans) × 100``.
   */
  formula?: string
}

export const METHODOLOGY: Record<string, MethodologyEntry> = {
  RECOGNITION_MATCH: {
    title: 'How recognition is decided',
    body: [
      'Each tracked face produces a 512-dim ArcFace embedding. The embedding is L2-normalized, then cosine similarity is computed against every enrolled identity in the FAISS index using inner product.',
      'A match is committed only when the top-1 score clears the recognition threshold AND the gap to the runner-up is wide enough — the margin guard is what prevents look-alikes from being labeled with high confidence.',
      'The "confidence" shown above is the top-1 cosine similarity, in 0..1.',
    ],
    formula:
      'match if (top1 ≥ 0.38) AND (top1 − top2 ≥ 0.06)\nconfidence = top1',
  },
  RECOGNITION_MISS: {
    title: 'How an unknown face is committed',
    body: [
      'After the tracker observes a face for several frames without crossing the recognition threshold, it commits to "unknown" and emits this event once per track to avoid per-frame spam.',
      'A miss does NOT mean the system mis-identified anyone — it means no enrolled identity scored above 0.38, or the runner-up was within 0.06 of the top score (ambiguous).',
    ],
    formula:
      'unknown after UNKNOWN_CONFIRM_ATTEMPTS frames where\n  top1 < 0.38  OR  (top1 − top2) < 0.06',
  },
  MARKED_PRESENT: {
    title: 'How "present" is decided',
    body: [
      'A student is marked PRESENT the first time their identity is recognized within the late-grace window from the schedule\'s start time.',
      'Recognition itself uses the formula in RECOGNITION_MATCH. The status only flips on the first recognition; subsequent scans update the rolling presence score.',
    ],
    formula:
      'PRESENT if first recognition_time ≤ session_start + LATE_GRACE_MINUTES',
  },
  MARKED_LATE: {
    title: 'How "late" is decided',
    body: [
      'Same first-recognition rule as PRESENT, but the recognition timestamp falls after the late-grace window. The student is still counted as having attended.',
    ],
    formula:
      'LATE if first recognition_time > session_start + LATE_GRACE_MINUTES',
  },
  MARKED_ABSENT: {
    title: 'How "absent" is decided',
    body: [
      'Emitted at session end for every enrolled student whose attendance record was never flipped to PRESENT, LATE, or EARLY_LEAVE during the session window.',
    ],
    formula: 'ABSENT if no recognition during session window',
  },
  EARLY_LEAVE_FLAGGED: {
    title: 'How early-leave is detected',
    body: [
      'The presence service runs a scan every 15 seconds. For each PRESENT/LATE student, it counts how many consecutive scans they have NOT been recognized in.',
      'When that counter reaches 3, the student is flagged as EARLY_LEAVE and a notification is dispatched. The threshold is intentionally short to catch real exits while tolerating brief occlusions (someone turning away from the camera).',
    ],
    formula:
      'flag if consecutive_scans_without_detection ≥ 3\n(scan interval = 15 s, ≈ 45 s of continuous absence)',
  },
  EARLY_LEAVE_RETURNED: {
    title: 'How a return is detected',
    body: [
      'After a student is flagged EARLY_LEAVE, the next successful recognition in any subsequent scan flips them back to their previous status (PRESENT or LATE) and stamps the absence duration on the early-leave row.',
    ],
    formula:
      'restore if recognized_after_flag\nabsence_duration = return_time − flag_time',
  },
  CAMERA_OFFLINE: {
    title: 'How camera health is detected',
    body: [
      'The frame grabber\'s ffmpeg subprocess pipes RTSP into the pipeline. When mediamtx returns 404 / DESCRIBE failed (no active publisher) the grabber collapses the noise into one warning and emits this event.',
      'It does NOT fire on transient single-frame drops — only when the publisher is fully gone for the duration of one reconnect cycle.',
    ],
  },
  CAMERA_ONLINE: {
    title: 'How recovery is detected',
    body: [
      'Emitted on the first successful frame read after a CAMERA_OFFLINE. Together they bracket the full outage window in the activity timeline.',
    ],
  },
  PIPELINE_STARTED: {
    title: 'When this fires',
    body: [
      'The session lifecycle scheduler runs every 15 seconds. When it finds a schedule whose (day_of_week, start_time..end_time) window contains "now" and which isn\'t already active, it auto-starts a SessionPipeline and emits this event.',
    ],
  },
  PIPELINE_STOPPED: {
    title: 'When this fires',
    body: [
      'Mirror of PIPELINE_STARTED — fired when the session lifecycle scheduler tears down a SessionPipeline because the schedule\'s end_time has passed.',
    ],
  },
  PIPELINE_CAMERA_SWAPPED: {
    title: 'When this fires',
    body: [
      'An admin changed the schedule\'s assigned room while a session was running. The active SessionPipeline hot-swaps onto the new room\'s FrameGrabber: presence accumulation and attendance records are preserved, but tracker state (ByteTrack IDs, identity cache) is reset because coordinate space changed.',
    ],
  },
}

/**
 * Lookup wrapper so the React component can stay thin.
 */
export function methodologyFor(eventType: string): MethodologyEntry | null {
  return METHODOLOGY[eventType] ?? null
}
