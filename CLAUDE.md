# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IAMS (Intelligent Attendance Monitoring System) is a CCTV-based facial recognition attendance system for JRMSU. It features:
- Raspberry Pi edge device for face detection (MediaPipe)
- FastAPI backend for face recognition (FaceNet + FAISS) and presence tracking (DeepSORT)
- React Native mobile app for students and faculty
- Supabase for database (PostgreSQL) and authentication

## Architecture

```
RPi (Camera + MediaPipe) → HTTP POST → FastAPI Backend (FaceNet + FAISS + DeepSORT)
                                              ↓
                                    Supabase (PostgreSQL + Auth)
                                              ↓
                          React Native Apps ← WebSocket (real-time updates)
```

**Two-tier design:** Edge device handles detection only; backend handles recognition, tracking, and all business logic.

## Development Commands

### Backend
```bash
cd backend
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac
pip install -r requirements.txt
python run.py                  # Start dev server on port 8000
```

### Testing
```bash
cd backend
pytest                                    # Run all tests
pytest tests/test_auth.py                 # Single test file
pytest -v                                 # Verbose output
pytest --cov=app                          # With coverage
```

### Edge Device (Raspberry Pi)
```bash
cd edge
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py
```

### Mobile App
```bash
cd mobile
pnpm install
pnpm android   # or pnpm ios
```

## Key Technical Details

### Face Recognition Pipeline
- **Registration:** Capture 3-5 face angles → generate FaceNet embeddings → average → store in FAISS
- **Recognition:** Crop face → embedding → FAISS search → match if cosine similarity > 0.6
- **Model:** FaceNet (InceptionResnetV1), 512-dim embeddings, 160x160 input

### Continuous Presence Tracking
- Scans every 60 seconds during class
- 3 consecutive missed scans triggers early-leave alert
- Presence score = (total_present / total_scans) × 100%

### RPi Queue Policy (offline handling)
- Max 500 items, 5-minute TTL, retry every 10 seconds
- Uses `collections.deque(maxlen=500)`

### FAISS Index
- `IndexFlatIP` does not support native delete
- On user removal: rebuild index or filter at search time

## Backend Structure

```
backend/app/
├── main.py           # FastAPI entry
├── config.py         # Settings (Supabase URL, etc.)
├── database.py       # Supabase/PostgreSQL connection
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic request/response
├── routers/          # API endpoints (auth, face, attendance, websocket)
├── services/         # Business logic (face_service, presence_service, tracking_service)
├── repositories/     # Database queries
└── utils/            # Security, dependencies, exceptions
```

**Pattern:** Routes → Services → Repositories → Models (dependency injection via FastAPI Depends)

## Database Schema (8 core tables)

- `users` - All system users with role (student/faculty/admin)
- `face_registrations` - Links users to FAISS embedding IDs
- `rooms` - Classroom locations
- `schedules` - Class schedules (subject, faculty, room, time)
- `enrollments` - Student-schedule relationships
- `attendance_records` - Check-in records
- `presence_logs` - Periodic scan results
- `early_leave_events` - Early leave detections

## API Conventions

- Base URL: `/api/v1`
- Auth: `Authorization: Bearer <jwt_token>`
- Edge API: `POST /api/v1/face/process` (Base64 JPEG, optional room_id/session_id)
- WebSocket: `/ws/{user_id}` for real-time updates

## User Flows

**Students:** Self-register (verify Student ID → create account → capture 3-5 face angles → review)

**Faculty:** Pre-seeded accounts only (no self-registration in MVP). Login via email+password.

## Environment Variables

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=xxxxx...
DATABASE_URL=postgresql://user:pass@host/db
JWT_SECRET_KEY=xxxxx...
BACKEND_URL=http://localhost:8000
```

## Documentation

Detailed docs in `/docs/main/`:
- `prd.md` - Product requirements
- `architecture.md` - System design
- `api-reference.md` - API endpoints
- `database-schema.md` - Table definitions
- `implementation.md` - How components work
- `step-by-step.md` - Development phases
