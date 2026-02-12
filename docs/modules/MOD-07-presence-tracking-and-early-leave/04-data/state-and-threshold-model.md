# State and Threshold Model

## Per-Student Runtime State
| Field | Type | Description |
|---|---|---|
| last_seen | TIMESTAMPTZ | Last scan where student was detected |
| miss_count | INTEGER | Consecutive scans where student was not detected (resets on detection) |
| total_scans | INTEGER | Total scan cycles in current session |
| scans_detected | INTEGER | Scans where student was detected |
| flagged | BOOLEAN | Whether early-leave event has been created for this session |

## Default Threshold Parameters
| Parameter | Env Var | Default | Description |
|---|---|---|---|
| Scan interval | `SCAN_INTERVAL` | 60 seconds | Time between scan evaluation cycles |
| Early-leave threshold | `EARLY_LEAVE_THRESHOLD` | 3 misses | Consecutive misses before flagging |
| Timezone | `TIMEZONE` | Asia/Manila (+08:00) | Session date/time boundary timezone |

## State Transition Rules
1. **Detected** → `miss_count` reset to 0; `scans_detected++`; update `last_seen`.
2. **Not detected** → `miss_count++`.
3. **miss_count >= EARLY_LEAVE_THRESHOLD** and **not flagged** → create `early_leave_events` record; set `flagged = true`; update attendance status to `early_leave` (MOD-06).
4. **Score update** after each scan cycle: `presence_score = (scans_detected / total_scans) × 100`.

## Recovery Behavior
- If a previously missed student is detected again (recovery), `miss_count` resets to 0.
- Recovery does NOT reverse a previously created early-leave event (event is immutable once created).
- Recovery detection does increment `scans_detected` for future score calculations.

## Score Formula
```
presence_score = (scans_detected / total_scans) × 100
```
- If `total_scans` is 0, score defaults to 0 (safe baseline).
- Score is a FLOAT value between 0 and 100.

## Edge Cases
- **Student joins late:** First scan where student is detected starts their tracking. Prior scans count as "not detected."
- **Zero total scans:** Score is 0 (session has not started or no scans have occurred).
- **Multiple early-leave attempts:** Only one early-leave event per `attendance_id` — dedup prevents duplicate flagging.
