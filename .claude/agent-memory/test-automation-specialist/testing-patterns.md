# Testing Patterns for IAMS Backend

## conftest.py Pattern

### Environment Variables (MUST be first)
```python
import os
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key-for-testing-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-32chars!!")
os.environ.setdefault("DEBUG", "false")
# THEN import app modules
```

### SQLite In-Memory Engine
```python
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
```
- UUID columns from PostgreSQL dialect auto-fallback to CHAR(32) in SQLAlchemy 2.x
- Use function-scoped fixtures: create_all before, drop_all after each test

### TestClient Setup
```python
# Must mock: check_db_connection (tries real PG), scheduler (APScheduler)
# FaceNet/FAISS imports are inside try/except in startup, so they fail gracefully
with patch("app.main.check_db_connection", return_value=True), \
     patch("app.main.scheduler") as mock_scheduler:
    mock_scheduler.running = False
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
```

## Mock User Pattern (for service unit tests)
```python
user = MagicMock(spec=User)
user.id = uuid.uuid4()
user.email = email
user.password_hash = hash_password(plain_password)  # real hash for verify_password
user.is_active = True
```

## Auth Header Pattern
```python
token = create_access_token({"user_id": str(user.id)})
headers = {"Authorization": f"Bearer {token}"}
```

## Service Test Pattern
```python
service = AuthService(MagicMock())  # mock DB session
service.user_repo = MagicMock()     # replace repo with mock
service.user_repo.get_by_identifier.return_value = mock_user
```

## Integration Test Patterns (Added 2026-02-07)

### Mock FaceNet for Integration Tests
```python
with patch('app.services.face_service.facenet_model') as mock_facenet:
    def mock_embedding(img_bytes):
        emb = np.random.randn(512).astype(np.float32)
        return emb / np.linalg.norm(emb)  # L2 normalize
    mock_facenet.generate_embedding = MagicMock(side_effect=mock_embedding)
```

### Mock FAISS for Integration Tests
```python
with patch('app.services.face_service.faiss_manager') as mock_faiss:
    mock_faiss.add = MagicMock(return_value=1)  # FAISS ID
    mock_faiss.search = MagicMock(return_value=[("user-id", 0.85)])
    mock_faiss.save = MagicMock()
```

### Edge API Integration Test Pattern
```python
with patch('app.routers.face.FaceService') as mock_service:
    service_instance = MagicMock()
    service_instance.facenet.decode_base64_image = MagicMock(return_value=MagicMock())

    async def mock_recognize(img_bytes, threshold=None):
        return "user-123", 0.85

    service_instance.recognize_face = AsyncMock(side_effect=mock_recognize)
    mock_service.return_value = service_instance

    response = client.post(f"{API}/face/process", json=payload)
```

### Presence Tracking Test Pattern
```python
@pytest.mark.asyncio
async def test_early_leave(db_session, test_schedule, test_student):
    presence_service = PresenceService(db_session)
    session = await presence_service.start_session(str(test_schedule.id))

    # First detection (check-in)
    await presence_service.log_detection(str(test_schedule.id), str(test_student.id), 0.85)

    # Simulate 3 missed scans
    for i in range(3):
        session.scan_count += 1
        await presence_service.process_session_scan(str(test_schedule.id))

    # Check early leave flagged
    record = repo.get_by_student_date(str(test_student.id), str(test_schedule.id), date.today())
    assert record.status == AttendanceStatus.EARLY_LEAVE
```

## UUID Conversion for SQLite (CRITICAL)

**Problem:** SQLite uses CHAR(32) for UUID. Comparing `UUID_column == string` fails with `'str' object has no attribute 'hex'`

**Solution:** Convert string to UUID in repository methods:

```python
def get_by_id(self, entity_id: str) -> Optional[Model]:
    import uuid
    if isinstance(entity_id, str):
        entity_id = uuid.UUID(entity_id)
    return self.db.query(Model).filter(Model.id == entity_id).first()
```

**Fixed:**
- `schedule_repository.get_by_id`
- `schedule_repository.get_enrolled_students`
- `schedule_repository.get_current_schedule`

**Need fixing:**
- `attendance_repository.get_by_id`
- `attendance_repository.get_by_student_date`
- `face_repository.get_by_user`
- `user_repository.get_by_id`

## Test Suite Summary

**Total Tests:** 284
- Unit: 88 tests
- Integration: 160 tests (108 new)
- Performance: 36 tests (new)

**Pass Rate:** 81% (230/284)

**New Test Files:**
- `tests/integration/test_edge_integration.py` - Edge device API (24 tests)
- `tests/integration/test_registration_flow.py` - Face registration (18 tests)
- `tests/integration/test_attendance_flow.py` - Attendance marking (26 tests)
- `tests/integration/test_presence_tracking.py` - Early leave detection (34 tests)
- `tests/integration/test_end_to_end.py` - Complete workflows (8 tests)
- `tests/performance/test_load.py` - Scalability tests (36 tests)
