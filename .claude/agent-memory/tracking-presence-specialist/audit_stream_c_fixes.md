---
name: Stream C audit fixes applied
description: Five bugs fixed in presence_service.py - wrong Redis key, field mismatch, race condition, unbatched commits, unbounded set growth
type: project
---

Stream C audit fixes applied to `backend/app/services/presence_service.py` on 2026-03-30:

1. **C1 - _redis_clear_room wrong ID**: Was passing `schedule_id` instead of `room_id`. Fixed by capturing `room_id = self._get_room_id(schedule)` before deleting session from `self._active_sessions`.

2. **C2 - confidence field mismatch**: `_get_identified_users_from_scan()` creates dicts with key `"confidence"`, but `process_session_scan()` was reading `"similarity"`. Both occurrences fixed.

3. **C3 - Race condition on scan counters**: Python-level read-increment-write replaced with `self.db.query(AttendanceRecord).filter(...).update({...})` using SQL-level `AttendanceRecord.scans_present + 1` expressions. Required adding `AttendanceRecord` import.

4. **C4 - Batch DB commits**: Added `self.db.commit()` after the per-student loop to flush all SQL-level `.update()` calls at once. The repo methods (`log_presence`, `update`) still commit individually inside the loop for check-in paths.

5. **C5 - Unbounded _ended_sessions set**: Added `PresenceService.cleanup_old_ended_sessions()` call at the start of `run_scan_cycle()` to purge previous-day records.

**Why:** These were identified during a codebase audit. The Redis key bug would silently fail to clear presence state. The field mismatch caused `None` confidence values. The race condition could corrupt counters under overlapping scans.

**How to apply:** When reviewing presence_service.py changes in future, verify these patterns remain correct.
