"""Pre-flight session readiness check — flag students likely to fail recognition.

Why this exists
---------------
The realtime tracker auto-heals recognition gaps via ``AutoCctvEnroller``,
but auto-heal needs ~30-60 s of sustained 0.50+ confidence per student
per camera before it commits. During a live demo or an actual class
that starts cold, a student who appears as "Unknown" for the first 30 s
is a real attendance/UX problem even if the system would self-correct
given another minute.

This script runs against today's (or a specified) schedules and prints
a per-room readiness table. For every enrolled student × room combo it
classifies the coverage:

  * READY     — has >= MIN_CCTV_PER_ROOM cctv_<stream_key>_* embeddings.
                Direct camera-domain support; recognition will commit
                within seconds of first detection.
  * LIKELY OK — has phone + per-camera sim_<stream_key>_* embeddings but
                fewer than MIN_CCTV_PER_ROOM cctv embeddings for this
                room. Recognition will work in ~70-80% of cases but
                margin can be tight when poses differ from the
                registered angles.
  * AT RISK   — missing per-camera sim coverage AND no cctv. Either the
                student registered before the camera-lens-aware sim
                pipeline shipped (2026-04-25) or auto-enroll has never
                fired for them. Recognition is uncertain.
  * NOT REGISTERED — student has no face_registration row at all.
                Recognition is impossible until they register from the
                student APK.

For every non-READY row, a one-line copy-paste ``cctv_enroll`` command
is printed so the operator can fix the gap with a single shell
invocation while the student sits in front of that camera.

Usage
-----
::

    docker exec iams-api-gateway-onprem python -m scripts.preflight_session
    docker exec iams-api-gateway-onprem python -m scripts.preflight_session --date 2026-04-26
    docker exec iams-api-gateway-onprem python -m scripts.preflight_session --schedule-id <uuid>
    docker exec iams-api-gateway-onprem python -m scripts.preflight_session --room EB226
    docker exec iams-api-gateway-onprem python -m scripts.preflight_session --all-today  # ignores time-of-day, lists every schedule with day_of_week == today

Exit codes:
    0 — All enrolled students in scope are READY.
    1 — At least one student is LIKELY OK or AT RISK.
    2 — At least one student is NOT REGISTERED, or no schedules matched.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable

from sqlalchemy import select

from app.database import SessionLocal
from app.models.enrollment import Enrollment
from app.models.face_embedding import FaceEmbedding
from app.models.face_registration import FaceRegistration
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.user import User, UserRole

# ── Coverage tiers ────────────────────────────────────────────────────
TIER_READY = "READY"
TIER_LIKELY = "LIKELY OK"
TIER_RISK = "AT RISK"
TIER_NOT_REG = "NOT REGISTERED"

# Tier styling for terminal output.
_TIER_COLOUR = {
    TIER_READY: "\033[32m",   # green
    TIER_LIKELY: "\033[33m",  # yellow
    TIER_RISK: "\033[31m",    # red
    TIER_NOT_REG: "\033[91;1m",  # bold red
}
_RESET = "\033[0m"


@dataclass(frozen=True)
class StudentCoverage:
    """Per-student × per-room coverage snapshot."""

    student_id: str  # users.id (uuid)
    student_code: str  # users.student_id (e.g. "21-A-02211")
    full_name: str
    has_registration: bool
    phone_count: int
    cctv_for_room: int
    sim_for_room: int

    def tier(self, min_cctv_per_room: int) -> str:
        if not self.has_registration:
            return TIER_NOT_REG
        if self.cctv_for_room >= min_cctv_per_room:
            return TIER_READY
        if self.sim_for_room > 0 and self.phone_count >= 3:
            return TIER_LIKELY
        return TIER_RISK


@dataclass(frozen=True)
class ScheduleReport:
    schedule_id: str
    subject_code: str
    subject_name: str
    room_name: str
    room_stream_key: str | None
    day_of_week: int
    start_time: time
    end_time: time
    rows: list[StudentCoverage]


# ── Coverage classification ─────────────────────────────────────────────


_PHONE_LABELS = {"up", "down", "left", "right", "center"}


def _classify_label(angle_label: str | None, stream_key: str) -> str | None:
    """Return one of ``phone``, ``cctv_room``, ``sim_room`` or None.

    Other-room cctv/sim labels return None — they still help recognition
    on this room's pipeline thanks to the cross-camera sim variants, but
    we don't credit them as direct coverage for THIS room's tier check.
    Doing so would mislead the operator about why recognition will or
    won't bind on this room specifically.
    """
    if not angle_label:
        return None
    if angle_label in _PHONE_LABELS:
        return "phone"
    cctv_prefix = f"cctv_{stream_key}_"
    sim_prefix = f"sim_{stream_key}_"
    if angle_label.startswith(cctv_prefix):
        return "cctv_room"
    if angle_label.startswith(sim_prefix):
        return "sim_room"
    return None


def _coverage_for_room(
    db,
    enrolled_student_ids: list[str],
    stream_key: str | None,
) -> list[StudentCoverage]:
    """Build a StudentCoverage row per enrolled student.

    One round-trip: pull all (student, registration_id, embedding label)
    tuples for the enrolled cohort in one query, then bucket in Python.
    Avoids N+1 round-trips when a class has 30+ students.
    """
    if not enrolled_student_ids:
        return []

    # Pull every enrolled student's name even if they have no registration —
    # NOT REGISTERED is a tier we want to surface, not silently drop.
    students = (
        db.query(User)
        .filter(User.id.in_(enrolled_student_ids))
        .all()
    )
    student_by_id = {str(s.id): s for s in students}

    # Pull all face embeddings for the enrolled cohort in one query.
    rows: Iterable[tuple] = []
    if stream_key is None:
        # Defensive: a room without a stream_key can't run the realtime
        # pipeline anyway, but we still want to surface NOT REGISTERED.
        rows = []
    else:
        rows = (
            db.query(
                FaceRegistration.user_id,
                FaceEmbedding.angle_label,
            )
            .join(FaceEmbedding, FaceEmbedding.registration_id == FaceRegistration.id)
            .filter(FaceRegistration.user_id.in_(enrolled_student_ids))
            .all()
        )

    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"phone": 0, "cctv_room": 0, "sim_room": 0}
    )
    has_reg: set[str] = set()
    for user_id, label in rows:
        sid = str(user_id)
        has_reg.add(sid)
        cat = _classify_label(label, stream_key or "")
        if cat is None:
            continue
        counts[sid][cat] += 1

    # If a student appears in face_registrations but with zero embeddings
    # (mid-registration crash, deleted-then-re-uploaded, etc.) they should
    # still count as registered — surface low coverage as AT RISK.
    if stream_key is not None:
        reg_only = (
            db.query(FaceRegistration.user_id)
            .filter(FaceRegistration.user_id.in_(enrolled_student_ids))
            .all()
        )
        for (uid,) in reg_only:
            has_reg.add(str(uid))

    out: list[StudentCoverage] = []
    for sid in enrolled_student_ids:
        student = student_by_id.get(sid)
        if student is None:
            # Enrollment row points to a deleted user — skip and let the
            # operator notice via the row count mismatch.
            continue
        c = counts[sid]
        full_name = " ".join(filter(None, [student.first_name, student.last_name]))
        out.append(
            StudentCoverage(
                student_id=sid,
                student_code=str(student.student_id or ""),
                full_name=full_name or sid,
                has_registration=sid in has_reg,
                phone_count=c["phone"],
                cctv_for_room=c["cctv_room"],
                sim_for_room=c["sim_room"],
            )
        )
    # Sort: weakest coverage first so the operator's eye lands on the
    # action items, not the green rows.
    tier_order = {TIER_NOT_REG: 0, TIER_RISK: 1, TIER_LIKELY: 2, TIER_READY: 3}
    return sorted(out, key=lambda r: (tier_order.get(r.tier(0), 99), r.full_name))


# ── Schedule selection ─────────────────────────────────────────────────


def _select_schedules(
    db,
    *,
    schedule_id: str | None,
    target_date: date | None,
    room_filter: str | None,
    all_today: bool,
) -> list[Schedule]:
    """Apply filters + return matching schedules.

    Default behaviour (no filters): every schedule whose day_of_week
    matches `today` AND whose start_time..end_time window contains
    `now`. This matches what the gateway's session_lifecycle_check
    auto-starts.
    """
    q = db.query(Schedule).join(Room, Room.id == Schedule.room_id)
    if schedule_id is not None:
        q = q.filter(Schedule.id == schedule_id)
        return q.all()

    target = target_date or date.today()
    dow = target.weekday()
    q = q.filter(Schedule.day_of_week == dow)

    if room_filter:
        # Accept room name (e.g. "EB226") or stream_key (e.g. "eb226").
        rf = room_filter.strip()
        q = q.filter(
            (Room.name == rf) | (Room.stream_key == rf.lower()) | (Room.stream_key == rf)
        )

    if not all_today and target == date.today():
        # Default: only schedules whose window contains "now".
        now = datetime.now().time()
        q = q.filter(Schedule.start_time <= now, Schedule.end_time >= now)

    return q.order_by(Schedule.start_time, Schedule.subject_code).all()


# ── Output ─────────────────────────────────────────────────────────────


def _enrolled_student_ids(db, schedule_id: str) -> list[str]:
    rows = (
        db.query(Enrollment.student_id)
        .filter(Enrollment.schedule_id == schedule_id)
        .all()
    )
    return [str(r[0]) for r in rows]


def _format_table(rows: list[StudentCoverage], min_cctv: int) -> str:
    if not rows:
        return "  (no enrolled students)\n"

    name_w = max(len(r.full_name) for r in rows)
    code_w = max(len(r.student_code) for r in rows)
    name_w = max(name_w, len("STUDENT"))
    code_w = max(code_w, len("ID"))

    lines: list[str] = []
    header = (
        f"  {'STUDENT'.ljust(name_w)}  "
        f"{'ID'.ljust(code_w)}  "
        f"{'PHONE':>5}  {'CCTV':>4}  {'SIM':>4}  TIER"
    )
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))

    for r in rows:
        tier = r.tier(min_cctv)
        colour = _TIER_COLOUR.get(tier, "")
        lines.append(
            f"  {r.full_name.ljust(name_w)}  "
            f"{r.student_code.ljust(code_w)}  "
            f"{r.phone_count:>5}  "
            f"{r.cctv_for_room:>4}  "
            f"{r.sim_for_room:>4}  "
            f"{colour}{tier}{_RESET}"
        )
    return "\n".join(lines) + "\n"


def _print_report(
    rep: ScheduleReport,
    *,
    min_cctv: int,
    show_fix_commands: bool,
) -> tuple[int, int, int]:
    """Print one schedule's report; return (n_ready, n_warn, n_blocked)."""
    print()
    print("=" * 78)
    window = f"{rep.start_time.strftime('%H:%M')}–{rep.end_time.strftime('%H:%M')}"
    print(
        f"  {rep.subject_code} · {rep.subject_name} · {rep.room_name} "
        f"({window})"
    )
    print(f"  schedule_id: {rep.schedule_id}")
    print("=" * 78)
    print(_format_table(rep.rows, min_cctv))

    n_ready = sum(1 for r in rep.rows if r.tier(min_cctv) == TIER_READY)
    n_warn = sum(1 for r in rep.rows if r.tier(min_cctv) in (TIER_LIKELY, TIER_RISK))
    n_blocked = sum(1 for r in rep.rows if r.tier(min_cctv) == TIER_NOT_REG)

    if show_fix_commands and rep.room_stream_key:
        flagged = [
            r for r in rep.rows
            if r.tier(min_cctv) in (TIER_LIKELY, TIER_RISK) and r.has_registration
        ]
        if flagged:
            print("  ┌─ One-line fixes (run while the student sits in front of the camera) ─┐")
            for r in flagged:
                print(
                    f"  │ {r.full_name} ({r.student_code})\n"
                    f"  │   docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \\\n"
                    f"  │       --user-id {r.student_id} --room {rep.room_name} --captures 5"
                )
            print("  └────────────────────────────────────────────────────────────────────────┘")

        not_reg = [r for r in rep.rows if r.tier(min_cctv) == TIER_NOT_REG]
        if not_reg:
            print("  ┌─ Cannot auto-fix (student must register from the student APK first) ─┐")
            for r in not_reg:
                print(f"  │ {r.full_name} ({r.student_code})  user_id={r.student_id}")
            print("  └────────────────────────────────────────────────────────────────────────┘")

    return n_ready, n_warn, n_blocked


# ── Main ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Day to check (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument("--schedule-id", help="Check only this schedule UUID.")
    parser.add_argument(
        "--room",
        help="Filter by room name (EB226) or stream_key (eb226). Combines with --date.",
    )
    parser.add_argument(
        "--all-today",
        action="store_true",
        help="List every schedule whose day_of_week matches the target date, "
        "ignoring the start/end window. Default is to show only sessions whose "
        "window contains 'now'.",
    )
    parser.add_argument(
        "--min-cctv-per-room",
        type=int,
        default=3,
        help="Minimum cctv_<room>_* embeddings before student is READY (default: 3).",
    )
    parser.add_argument(
        "--no-fix-commands",
        action="store_true",
        help="Suppress the per-student copy-paste cctv_enroll commands.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        schedules = _select_schedules(
            db,
            schedule_id=args.schedule_id,
            target_date=args.date,
            room_filter=args.room,
            all_today=args.all_today,
        )
        if not schedules:
            scope = []
            if args.schedule_id:
                scope.append(f"schedule_id={args.schedule_id}")
            if args.date:
                scope.append(f"date={args.date.isoformat()}")
            if args.room:
                scope.append(f"room={args.room}")
            if args.all_today:
                scope.append("all-today=true")
            scope_str = ", ".join(scope) if scope else "current window of today"
            print(f"No schedules found for: {scope_str}")
            return 2

        total_ready = total_warn = total_blocked = 0
        for sched in schedules:
            room: Room | None = (
                db.query(Room).filter(Room.id == sched.room_id).first()
            )
            if room is None:
                # A schedule with a deleted room can't run anyway — skip.
                continue
            student_ids = _enrolled_student_ids(db, str(sched.id))
            rows = _coverage_for_room(db, student_ids, room.stream_key)
            rep = ScheduleReport(
                schedule_id=str(sched.id),
                subject_code=sched.subject_code,
                subject_name=sched.subject_name,
                room_name=room.name,
                room_stream_key=room.stream_key,
                day_of_week=sched.day_of_week,
                start_time=sched.start_time,
                end_time=sched.end_time,
                rows=rows,
            )
            r, w, b = _print_report(
                rep,
                min_cctv=args.min_cctv_per_room,
                show_fix_commands=not args.no_fix_commands,
            )
            total_ready += r
            total_warn += w
            total_blocked += b

        # Final summary
        print()
        print("=" * 78)
        print(
            f"  SUMMARY: {total_ready} READY · "
            f"{_TIER_COLOUR[TIER_LIKELY]}{total_warn} need attention{_RESET} · "
            f"{_TIER_COLOUR[TIER_NOT_REG]}{total_blocked} not registered{_RESET}"
        )
        print("=" * 78)

        if total_blocked > 0:
            return 2
        if total_warn > 0:
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
