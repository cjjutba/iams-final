# State and Threshold Model

## Per-Student Runtime State
- last_seen
- miss_count
- total_scans
- scans_detected
- flagged

## Default Threshold Parameters
- `SCAN_INTERVAL`: 60 seconds
- `EARLY_LEAVE_THRESHOLD`: 3 misses

## State Transition Rules
1. Detected -> miss_count reset; scans_detected++.
2. Not detected -> miss_count++.
3. miss_count >= threshold and not flagged -> create early_leave_event.
4. Score update after each scan cycle.

## Score Formula
`presence_score = scans_detected / total_scans * 100`
