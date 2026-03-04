# Folder Structure

## Root Layout

```
iams/
├── docs/                   # Documentation
├── backend/                # FastAPI server
├── edge/                   # Raspberry Pi code
├── mobile/                 # React Native app
├── scripts/                # Utility scripts (seeders, CSV import)
├── data/                   # Local data files
├── .env.example            # Environment template
├── .gitignore
└── README.md
```

---

## Backend Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings and env vars (Supabase URL, etc.)
│   ├── database.py             # Supabase/PostgreSQL connection
│   │
│   ├── models/                 # SQLAlchemy or Pydantic models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── schedule.py
│   │   ├── enrollment.py
│   │   ├── attendance.py
│   │   └── presence_log.py
│   │
│   ├── schemas/                # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── face.py
│   │   ├── attendance.py
│   │   └── schedule.py
│   │
│   ├── routers/                # API endpoints
│   │   ├── __init__.py
│   │   ├── auth.py             # Login, register (or delegate to Supabase)
│   │   ├── users.py            # User CRUD
│   │   ├── face.py             # Face register, recognize
│   │   ├── attendance.py       # Attendance records
│   │   ├── schedules.py        # Class schedules
│   │   └── websocket.py        # Real-time updates
│   │
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── face_service.py     # FaceNet + FAISS
│   │   ├── tracking_service.py # DeepSORT
│   │   ├── presence_service.py # Continuous tracking logic
│   │   └── notification_service.py
│   │
│   ├── repositories/           # Database queries (Supabase/Postgres)
│   │   ├── __init__.py
│   │   ├── user_repository.py
│   │   ├── attendance_repository.py
│   │   └── schedule_repository.py
│   │
│   └── utils/                  # Helpers
│       ├── __init__.py
│       ├── security.py         # JWT, password hashing
│       ├── dependencies.py     # FastAPI dependencies
│       └── exceptions.py       # Custom exceptions
│
├── alembic/                    # Database migrations (if using local Postgres)
│   ├── versions/
│   └── env.py
│
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_face.py
│   └── test_attendance.py
│
├── alembic.ini
├── requirements.txt
├── .env
└── run.py                      # Dev server runner
```

---

## Edge Structure (Raspberry Pi)

```
edge/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Settings
│   ├── camera.py               # Frame capture
│   ├── detector.py             # Face detection (MediaPipe)
│   ├── processor.py            # Crop and compress
│   └── sender.py                # HTTP client to backend
│
├── models/                     # TFLite models (MediaPipe export)
│   └── face_detection.tflite
│
├── requirements.txt
├── .env
└── run.py
```

---

## Mobile Structure (React Native)

```
mobile/
├── src/
│   ├── App.tsx                 # Entry point
│   ├── config/
│   │   ├── routes.ts
│   │   ├── theme.ts
│   │   └── constants.ts        # API URL, Supabase URL
│   │
│   ├── models/                 # Data models / types
│   │   ├── user.ts
│   │   ├── attendance.ts
│   │   └── schedule.ts
│   │
│   ├── store/                  # State management (Zustand or Context)
│   │   ├── authStore.ts
│   │   ├── attendanceStore.ts
│   │   └── scheduleStore.ts
│   │
│   ├── services/               # API calls
│   │   ├── api.ts
│   │   ├── authService.ts      # Supabase Auth + backend
│   │   ├── faceService.ts
│   │   └── websocketService.ts
│   │
│   ├── screens/                # UI screens
│   │   ├── onboarding/
│   │   │   └── OnboardingScreen.tsx
│   │   ├── auth/
│   │   │   ├── WelcomeScreen.tsx      # Student / Faculty select
│   │   │   ├── StudentLoginScreen.tsx
│   │   │   ├── FacultyLoginScreen.tsx
│   │   │   └── StudentRegisterScreen.tsx  # Steps: verify ID, account, face, review
│   │   ├── student/
│   │   │   ├── HomeScreen.tsx
│   │   │   ├── AttendanceScreen.tsx
│   │   │   └── FaceRegisterScreen.tsx
│   │   └── faculty/
│   │       ├── DashboardScreen.tsx
│   │       ├── LiveAttendanceScreen.tsx
│   │       └── ReportsScreen.tsx
│   │
│   ├── components/            # Reusable components
│   │   ├── AttendanceCard.tsx
│   │   ├── StudentTile.tsx
│   │   └── AlertDialog.tsx
│   │
│   └── utils/
│       ├── helpers.ts
│       └── validators.ts
│
├── assets/
│   ├── images/
│   └── fonts/
│
├── __tests__/
├── package.json
├── app.json
├── tsconfig.json
└── .env
```

---

## Docs Structure

```
docs/
├── main/
│   ├── prd.md                      # Product requirements
│   ├── architecture.md             # System design
│   ├── tech-stack.md               # Technologies used
│   ├── folder-structure.md         # This file
│   ├── implementation.md           # How to build
│   ├── step-by-step.md             # Development phases
│   ├── technical-specification.md  # Detailed specs
│   ├── best-practices.md           # Coding guidelines
│   ├── api-reference.md            # API endpoints
│   ├── database-schema.md          # Table definitions
│   ├── deployment.md               # How to deploy
│   └── testing.md                  # Testing strategy
│
└── screens/                        # Mobile app screens & navigation
    ├── README.md                   # Intro and index
    └── screen-list.md              # Complete screen list, flow, navigation, MVP priority
```

---

## Data Folder

```
data/
├── faiss/
│   └── faces.index             # FAISS index file (backend)
├── uploads/
│   └── faces/                  # Registered face images (backup)
└── logs/
    └── app.log
```

---

## Scripts (Optional)

```
scripts/
├── seed_faculty.ts or .py       # Pre-seed faculty from CSV
├── import_students.ts or .py    # Import student list for validation
└── import_schedule.ts or .py   # Import schedule for classroom
```

---

## Key Principles

| Principle | Application |
|-----------|-------------|
| Separation of concerns | Routes → Services → Repositories → Models |
| Single responsibility | Each file does one thing |
| Dependency injection | Services injected via FastAPI Depends |
| Configuration | All settings in config and .env (Supabase URL, backend URL) |
| Testability | Business logic in services, easy to mock |
