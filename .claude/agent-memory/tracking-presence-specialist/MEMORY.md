# Tracking & Presence Monitoring Implementation Notes

## Overview
DeepSORT-based tracking system integrated with continuous presence monitoring for IAMS classroom attendance.

## Key Implementation Patterns

### 1. Tracking Service (tracking_service.py)
**Simplified DeepSORT approach** for 60-second interval scans (not continuous video):
- **Track lifecycle**: Creation → Update → Deletion (after max_age)
- **Association strategy**: IoU-based matching + identity consistency bonus
- **Track aging**: 180 seconds (3 × 60s scan interval) before removal
- **Session isolation**: Tracks are per-schedule, no cross-session contamination
- **Identity persistence**: user_id maintained across detections via confidence-based updates

**Critical parameters**:
```python
max_age = 180          # 3 scans at 60s interval
min_hits = 1           # Single detection confirms track (for discrete scans)
iou_threshold = 0.3    # Minimum IoU for detection-track matching
```

**Matching algorithm**:
1. Compute IoU between existing tracks and new detections
2. Apply identity consistency bonus (0.5x cost if same user_id)
3. Greedy matching (best IoU above threshold)
4. Unmatched detections → new tracks

### 2. Presence Service (presence_service.py)
**Session-based presence tracking** with early-leave detection:
- **Session start**: Creates attendance records for all enrolled students, initializes tracking
- **Detection logging**: Links face recognition to attendance records via tracking
- **Scan cycles**: Every 60s, checks which students are present using tracking service
- **Early leave**: 3 consecutive misses → flag + create event + WebSocket alert
- **Scoring**: `(scans_present / total_scans) × 100%`

**Integration with tracking**:
```python
# Update tracker with detection
detection = Detection(bbox=bbox, confidence=1.0, user_id=user_id, recognition_confidence=confidence)
tracking_service.update(schedule_id, [detection])

# Check who's present in scan cycle
identified_users = tracking_service.get_identified_users(schedule_id)
present_user_ids = set(identified_users.keys())
```

### 3. Early Leave Detection Logic
**3-consecutive-miss threshold** (NOT 3 total misses):
- Counter increments on each missed scan
- Counter resets to 0 when student reappears
- Event created only once when threshold reached
- `early_leave_flagged` prevents duplicate events

**Example sequence**:
```
Scan 1: Miss → consecutive_misses = 1
Scan 2: Miss → consecutive_misses = 2
Scan 3: Present → consecutive_misses = 0 (RESET)
Scan 4: Miss → consecutive_misses = 1
Scan 5: Miss → consecutive_misses = 2
Scan 6: Miss → consecutive_misses = 3 → FLAG EARLY LEAVE
```

### 4. APScheduler Background Job
**60-second interval job** in main.py:
```python
scheduler.add_job(
    run_presence_scan_cycle,
    'interval',
    seconds=settings.SCAN_INTERVAL_SECONDS,  # 60
    id='presence_scan_cycle',
    replace_existing=True,
    max_instances=1  # Prevent overlapping runs
)
```

**Job function**:
- Creates new DB session for each run
- Calls `presence_service.run_scan_cycle()`
- Processes all active sessions in parallel
- Graceful error handling (per-session try/catch)

### 5. Presence Score Calculation
**Formula**: `(scans_present / total_scans) × 100%`
- Updated after every scan (whether detected or not)
- Reflects continuous presence, not just initial check-in
- Rounded to 2 decimal places

**Edge cases**:
- `total_scans = 0` → score = 0.0
- Student never checked in → not counted in scans
- Early leave → subsequent scans still logged (as missed)

## Database Tables Used

### presence_logs
- `id`: BigInteger (auto-increment)
- `attendance_id`: FK to attendance_records
- `scan_number`: Sequential scan number (1, 2, 3, ...)
- `scan_time`: Timestamp of scan
- `detected`: Boolean (present or not)
- `confidence`: Recognition confidence (if detected)

### early_leave_events
- `id`: UUID
- `attendance_id`: FK to attendance_records
- `detected_at`: When early leave was detected
- `last_seen_at`: Last time student was present
- `consecutive_misses`: Number of consecutive misses (should be ≥ 3)
- `notified`: Boolean flag
- `notified_at`: When faculty was notified

### attendance_records
- `total_scans`: Total scans performed during session
- `scans_present`: Number of scans where student was detected
- `presence_score`: Calculated percentage

## API Endpoints

### Session Management
- `POST /api/v1/presence/sessions/start` - Start session
- `POST /api/v1/presence/sessions/end` - End session
- `GET /api/v1/presence/sessions/active` - List active sessions

### Presence Data
- `GET /api/v1/presence/{attendance_id}/logs` - Get scan logs
- `GET /api/v1/presence/early-leaves` - Get early leave events (with filters)

### Tracking Stats
- `GET /api/v1/presence/tracking/stats/{schedule_id}` - Real-time tracking stats

## Testing Approach

### Tracking Service Tests (test_tracking_service.py)
- Track creation and lifecycle
- IoU-based association
- Identity consistency bonus
- Track aging and cleanup
- Multi-track handling
- Session isolation
- Confidence updates

### Presence Service Tests (test_presence_service.py)
- Session start/end
- Detection logging (check-in)
- Scan cycle processing
- Early leave detection (3 consecutive misses)
- Consecutive miss reset on reappearance
- Presence score calculation
- Integration with tracking service

## Known Limitations & Design Decisions

1. **Not continuous video tracking**: Designed for 60-second discrete scans, not real-time video
2. **Simplified tracking**: Uses IoU + identity matching (no deep appearance features)
3. **Single detection per scan**: Assumes one face detection per student per scan cycle
4. **No track recovery**: Once track ages out, new detection creates new track
5. **Stationary assumption**: Works best when students are seated (classroom environment)

## Configuration Settings

From `config.py`:
```python
SCAN_INTERVAL_SECONDS = 60        # Scan frequency
EARLY_LEAVE_THRESHOLD = 3         # Consecutive misses
GRACE_PERIOD_MINUTES = 15         # Late check-in grace period
SESSION_BUFFER_MINUTES = 5        # Buffer before/after class
```

## Future Enhancements

- [ ] Add appearance-based re-identification (deep features)
- [ ] Support for multiple cameras per room
- [ ] Confidence-weighted presence scoring
- [ ] Anomaly detection (unusual absence patterns)
- [ ] Batch scan processing optimization
- [ ] Track visualization for debugging

## References

- [MOD-07 Documentation](docs/modules/MOD-07-presence-tracking-and-early-leave/)
- [DeepSORT Paper](https://arxiv.org/abs/1703.07402) (concept reference, not fully implemented)
- [Implementation Guide](docs/main/implementation.md) - Presence Tracking section
