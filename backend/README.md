# IAMS Backend

**Intelligent Attendance Monitoring System - Backend API**

FastAPI-based backend for facial recognition attendance tracking with continuous presence monitoring and early-leave detection.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or Supabase account)
- CUDA-capable GPU (optional, for faster face recognition)

### Installation

1. **Clone and navigate to backend folder:**
```bash
cd backend
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

5. **Run database migrations:**
```bash
alembic upgrade head
```

6. **Start development server:**
```bash
python run.py
# or: uvicorn app.main:app --reload
```

7. **Access API documentation:**
```
http://localhost:8000/api/v1/docs
```

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration and settings
│   ├── database.py          # Database connection
│   │
│   ├── models/              # SQLAlchemy models (8 models)
│   │   ├── user.py
│   │   ├── face_registration.py
│   │   ├── room.py
│   │   ├── schedule.py
│   │   ├── enrollment.py
│   │   ├── attendance_record.py
│   │   ├── presence_log.py
│   │   └── early_leave_event.py
│   │
│   ├── schemas/             # Pydantic schemas (6 files)
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── face.py          # Includes Edge API contract
│   │   ├── schedule.py
│   │   ├── attendance.py
│   │   └── common.py
│   │
│   ├── routers/             # API endpoints (6 routers)
│   │   ├── auth.py          # Authentication
│   │   ├── users.py         # User management
│   │   ├── face.py          # Face recognition + Edge API
│   │   ├── schedules.py     # Schedule management
│   │   ├── attendance.py    # Attendance tracking
│   │   └── websocket.py     # Real-time notifications
│   │
│   ├── services/            # Business logic
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── face_service.py
│   │   ├── presence_service.py
│   │   └── ml/
│   │       ├── face_recognition.py  # FaceNet model
│   │       └── faiss_manager.py     # FAISS index
│   │
│   ├── repositories/        # Data access layer
│   │   ├── user_repository.py
│   │   ├── schedule_repository.py
│   │   ├── attendance_repository.py
│   │   └── face_repository.py
│   │
│   └── utils/               # Utilities
│       ├── security.py      # Auth utilities
│       ├── dependencies.py  # FastAPI dependencies
│       └── exceptions.py    # Custom exceptions
│
├── alembic/                 # Database migrations
├── data/                    # FAISS index and uploads
├── logs/                    # Application logs
├── tests/                   # Unit and integration tests
├── .env                     # Environment variables (create from .env.example)
├── requirements.txt         # Python dependencies
└── run.py                   # Development server runner
```

---

## 🔑 Key Features

### 1. **Authentication**
- Student registration (verify ID → create account → register face)
- Faculty login (pre-seeded accounts)
- JWT tokens (custom for faculty, Supabase for students)

### 2. **Face Recognition**
- FaceNet model (InceptionResnetV1, pretrained on VGGFace2)
- FAISS vector search (512-dim embeddings, cosine similarity)
- Edge API for Raspberry Pi integration

### 3. **Continuous Presence Tracking**
- 60-second scan intervals
- Early-leave detection (3 consecutive misses)
- Presence scoring (% detected across all scans)
- Real-time alerts via WebSocket

### 4. **Attendance Management**
- Automated attendance marking
- Manual faculty override
- Attendance history and summaries
- Live attendance monitoring

---

## 📡 API Endpoints

### Authentication (`/api/v1/auth`)
- `POST /verify-student-id` - Validate student ID
- `POST /register` - Create student account
- `POST /login` - Login (email/student_id + password)
- `GET /me` - Get current user
- `POST /change-password` - Change password

### Users (`/api/v1/users`)
- `GET /` - List users (admin only)
- `GET /{id}` - Get user by ID
- `PATCH /{id}` - Update user
- `DELETE /{id}` - Deactivate user (admin only)

### Face Recognition (`/api/v1/face`)
- `POST /register` - Register face (3-5 images)
- `POST /process` - **Edge API for Raspberry Pi**
- `GET /status` - Check registration status
- `POST /recognize` - Single face recognition (testing)

### Schedules (`/api/v1/schedules`)
- `GET /` - List all schedules
- `GET /me` - Get my schedules
- `GET /{id}` - Get schedule details
- `GET /{id}/students` - Get enrolled students (faculty)
- `POST /` - Create schedule (admin only)

### Attendance (`/api/v1/attendance`)
- `GET /today` - Today's attendance (faculty)
- `GET /me` - My attendance history (student)
- `GET /live/{schedule_id}` - Live attendance status (faculty)
- `POST /manual` - Manual entry (faculty)
- `GET /{id}/logs` - Presence scan logs

### WebSocket (`/api/v1/ws`)
- `WS /{user_id}` - Real-time connection
- Events: `early_leave`, `attendance_update`, `session_start`, `session_end`

---

## 🔧 Configuration

### Environment Variables (`.env`)

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=postgresql://...

# JWT
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Face Recognition
FAISS_INDEX_PATH=data/faiss/faces.index
RECOGNITION_THRESHOLD=0.6
USE_GPU=true

# Presence Tracking
SCAN_INTERVAL_SECONDS=60
EARLY_LEAVE_THRESHOLD=3
GRACE_PERIOD_MINUTES=15
```

---

## 🧪 Testing

### Run Tests
```bash
pytest
pytest -v  # Verbose
pytest --cov=app  # With coverage
```

### Test API with Postman
1. Import Postman collection (if available)
2. Test authentication flow
3. Test face registration
4. Test Edge API with Base64 images

---

## 🚀 Deployment

### Local Development (Recommended for Thesis)
1. Backend on laptop (http://192.168.x.x:8000)
2. Database on Supabase cloud
3. All devices on same WiFi

### Cloud Deployment (Production)
1. Deploy to Railway/Render/VPS
2. Database on Supabase cloud
3. Set environment variables
4. Enable HTTPS
5. Configure CORS origins

---

## 📊 Performance Targets

| Metric | Target | Maximum |
|--------|--------|---------|
| Face detection | 30ms | 50ms |
| Face recognition | 50ms | 100ms |
| End-to-end latency | 200ms | 500ms |
| Concurrent users | 50 | 100 |

---

## 🔒 Security

- **Password Hashing:** bcrypt (cost factor 12)
- **JWT Tokens:** HS256 algorithm, 30-minute expiry
- **Face Data:** Only embeddings stored (512-dim vectors), not raw images
- **CORS:** Configurable origins
- **Input Validation:** Pydantic schemas for all requests

---

## 📝 License

MIT License - JRMSU Thesis Project

---

## 👥 Contributors

IAMS Development Team - Computer Engineering, JRMSU

---

## 📞 Support

For issues or questions:
- Check API documentation: `/api/v1/docs`
- Review logs: `logs/app.log`
- Contact: support@iams.jrmsu.edu.ph
