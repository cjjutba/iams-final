"""
Automatic Session Scheduler

Manages automatic start/stop of attendance sessions based on schedule times.
Runs as an APScheduler job every 60 seconds inside the API gateway.

Dual-mode design:
- Automatic: Sessions auto-start at schedule.start_time, auto-end at schedule.end_time
- Manual: Faculty can start/end sessions early from the mobile app
- Override: Manual actions take priority; scheduler won't restart a manually-ended session

I/O contract:
  - Reads:    schedules table (via ScheduleRepository)
  - Calls:    PresenceService.start_session(), .end_session()
  - State:    Module-level set tracks manually-ended sessions per day
"""

from datetime import date, datetime

from app.config import logger
from app.database import SessionLocal
from app.repositories.schedule_repository import ScheduleRepository
from app.services.presence_service import PresenceService

# ── module-level state ────────────────────────────────────────

# Track sessions that were manually ended today so the scheduler
# doesn't restart them.  Reset daily.
_manually_ended_today: set[str] = set()
_last_reset_date: date = date.today()


def _reset_daily_tracking():
    """Reset the manually-ended tracking set at the start of each new day."""
    global _manually_ended_today, _last_reset_date
    today = date.today()
    if today != _last_reset_date:
        _manually_ended_today = set()
        _last_reset_date = today
        logger.info("Session scheduler: daily tracking reset")


def mark_manually_ended(schedule_id: str):
    """
    Mark a session as manually ended so the auto-scheduler won't restart it.

    Called from the end_session API endpoint when faculty manually ends
    a session before the scheduled end time.

    Args:
        schedule_id: Schedule UUID string
    """
    _reset_daily_tracking()
    _manually_ended_today.add(schedule_id)
    logger.info(f"Session {schedule_id} marked as manually ended (won't auto-restart today)")


def is_manually_ended(schedule_id: str) -> bool:
    """Check if a session was manually ended today."""
    _reset_daily_tracking()
    return schedule_id in _manually_ended_today


# ── scheduler entry point ────────────────────────────────────

async def auto_manage_sessions():
    """
    Automatically start and stop attendance sessions based on schedule times.

    Called every 60 seconds by APScheduler (job id: ``auto_session_manager``).

    Algorithm per schedule for today's day-of-week:
      1. If now is within [start_time, end_time) **and** no active session
         **and** not manually ended -> auto-start.
      2. If an active session exists **and** now >= end_time -> auto-end.

    Respects manual overrides:
      - If faculty already started a session manually, the scheduler won't
        interfere (``is_session_active`` returns True, so auto-start is skipped).
      - If faculty manually ended a session, the scheduler won't restart it
        (checked via ``is_manually_ended``).

    Note: The 60-second presence scan cycle (``run_scan_cycle``) is scheduled
    as a *separate* APScheduler job in ``main.py``.  This function only handles
    session lifecycle (start / end).
    """
    _reset_daily_tracking()

    db = SessionLocal()
    try:
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, matches our schedule convention

        schedule_repo = ScheduleRepository(db)
        presence_service = PresenceService(db)

        # Get all active schedules for today's day-of-week
        today_schedules = schedule_repo.get_by_day(current_day)

        if not today_schedules:
            return

        for schedule in today_schedules:
            schedule_id = str(schedule.id)
            is_active = presence_service.is_session_active(schedule_id)

            # --- Auto-start logic ---
            if (
                not is_active
                and current_time >= schedule.start_time
                and current_time < schedule.end_time
            ):
                # Don't restart if manually ended by faculty
                if is_manually_ended(schedule_id):
                    continue

                try:
                    logger.info(
                        f"Auto-starting session for {schedule.subject_code} "
                        f"({schedule.subject_name}) at {current_time.strftime('%H:%M')}"
                    )
                    await presence_service.start_session(schedule_id)
                    logger.info(f"Auto-session started: {schedule.subject_code}")
                except Exception as e:
                    logger.error(
                        f"Failed to auto-start session for {schedule.subject_code}: {e}"
                    )

            # --- Auto-end logic ---
            elif is_active and current_time >= schedule.end_time:
                try:
                    logger.info(
                        f"Auto-ending session for {schedule.subject_code} "
                        f"({schedule.subject_name}) at {current_time.strftime('%H:%M')}"
                    )
                    await presence_service.end_session(schedule_id)
                    logger.info(f"Auto-session ended: {schedule.subject_code}")
                except Exception as e:
                    logger.error(
                        f"Failed to auto-end session for {schedule.subject_code}: {e}"
                    )

    except Exception as e:
        logger.error(f"Error in auto_manage_sessions: {e}")
    finally:
        db.close()
