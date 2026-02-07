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
