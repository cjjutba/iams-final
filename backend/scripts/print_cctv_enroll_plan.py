"""
Print the per-room / per-student CCTV-enrolment command plan.

Reads the current DB state and emits one ``docker exec ... cctv_enroll``
command per (student, room) pair where the student is actively enrolled
in a schedule for that room AND has fewer than ``--target`` cctv_*
embeddings on file. Operator copy-pastes the output to run the actual
enrolments.

Usage (inside the api-gateway container):
  docker exec iams-api-gateway-onprem python -m scripts.print_cctv_enroll_plan
  docker exec iams-api-gateway-onprem python -m scripts.print_cctv_enroll_plan --target 5

Runs against the current DB so the plan stays accurate after new students
register or after partial cctv_enrol runs. The original RUNBOOK.md
(docs/plans/2026-04-25-identity-swap-hardening/) shows the format and
operator preflight steps.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _run(target: int) -> int:
    # Late imports so the script doesn't need a fully-booted FastAPI app.
    from app.database import SessionLocal
    from app.models.enrollment import Enrollment
    from app.models.face_embedding import FaceEmbedding
    from app.models.face_registration import FaceRegistration
    from app.models.room import Room
    from app.models.schedule import Schedule
    from app.models.user import User

    db = SessionLocal()
    try:
        rows = (
            db.query(User.id, User.first_name, User.last_name, Room.stream_key, Room.name)
            .join(Enrollment, Enrollment.student_id == User.id)
            .join(Schedule, Schedule.id == Enrollment.schedule_id)
            .join(Room, Room.id == Schedule.room_id)
            .filter(User.role == "STUDENT")
            .filter(Room.stream_key.isnot(None))
            .distinct()
            .order_by(Room.stream_key, User.first_name)
            .all()
        )

        per_room: dict[str, list[tuple[str, str, int, int]]] = {}
        for uid, fn, ln, stream_key, room_name in rows:
            reg = (
                db.query(FaceRegistration)
                .filter(
                    FaceRegistration.user_id == uid,
                    FaceRegistration.is_active.is_(True),
                )
                .first()
            )
            if not reg:
                continue
            embs = (
                db.query(FaceEmbedding)
                .filter(FaceEmbedding.registration_id == reg.id)
                .all()
            )
            cctv_count = sum(
                1 for e in embs if e.angle_label and e.angle_label.startswith("cctv_")
            )
            full = f"{fn} {ln}".strip()
            per_room.setdefault(room_name, []).append(
                (full, str(uid), cctv_count, len(embs))
            )

        if not per_room:
            print("No student enrolments found across any room with a stream_key.")
            return 1

        print()
        print("# CCTV-enrolment plan (auto-generated). See")
        print("# docs/plans/2026-04-25-identity-swap-hardening/RUNBOOK.md for context.")
        print(f"# Target: {target} cctv_* embeddings per (student, room) pair.")
        print()

        for room_name in sorted(per_room.keys()):
            entries = sorted(per_room[room_name])
            ok = sum(1 for _, _, c, _ in entries if c >= target)
            need = sum(1 for _, _, c, _ in entries if c < target)
            print(f"### {room_name}  ({ok} OK, {need} need enrol)")
            print()
            print("```bash")
            for full, uid, cctv_count, _total in entries:
                if cctv_count >= target:
                    continue
                print(
                    f"docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \\\n"
                    f"    --user-id {uid} --room {room_name} --captures 5  # {full} (currently {cctv_count} cctv)"
                )
                print()
            print("```")
            print()

        # Skipped students summary
        all_ok = []
        for room_name, entries in per_room.items():
            for full, uid, cctv_count, _total in entries:
                if cctv_count >= target:
                    all_ok.append((room_name, full, cctv_count))
        if all_ok:
            print("### Already enrolled (skipped)")
            print()
            for room_name, full, cctv_count in sorted(all_ok):
                print(f"- {full} @ {room_name} ({cctv_count} cctv)")
            print()

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print CCTV-enrol command plan")
    parser.add_argument(
        "--target",
        type=int,
        default=3,
        help="Min cctv_* embeddings per (student, room) before considered OK",
    )
    args = parser.parse_args()
    sys.exit(_run(args.target))
