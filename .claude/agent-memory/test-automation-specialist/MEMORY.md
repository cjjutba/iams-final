# Test Automation Specialist - Agent Memory

## Project: IAMS Backend Testing

### Key Architecture Facts
- Python 3.14.2, FastAPI, SQLAlchemy 2.x, Pydantic 2.x, bcrypt (passlib)
- JWT via python-jose (HS256), Supabase for prod DB (PostgreSQL)
- Models use `UUID(as_uuid=True)` from `sqlalchemy.dialects.postgresql`
- SQLAlchemy 2.x UUID type falls back to CHAR(32) on SQLite automatically
- Settings loaded eagerly via pydantic-settings at import time (needs env vars set BEFORE imports)
- App startup loads FaceNet, FAISS, APScheduler -- all wrapped in try/except (log + continue)

### Testing Infrastructure (Created 2026-02-07)
- `pytest.ini` at `backend/pytest.ini` with `testpaths = tests`
- `conftest.py` at `backend/tests/conftest.py`
- pytest and pytest-cov must be pip-installed (not in requirements.txt)
- See [testing-patterns.md](testing-patterns.md) for detailed patterns

### Critical Setup Notes
- **Env vars**: Must `os.environ.setdefault(...)` for SUPABASE_URL, SUPABASE_ANON_KEY, DATABASE_URL, SECRET_KEY before ANY app imports
- **SQLite in-memory**: Use `sqlite://` with StaticPool for test isolation
- **Startup mocking**: Patch `app.main.check_db_connection` and `app.main.scheduler`; FaceNet/FAISS failures are caught by try/except so no extra patching needed
- **TestClient**: Use `raise_server_exceptions=False` for testing error responses
- **User fixture password**: Default "TestPass123" used across all fixtures

### Test File Map
| File | Type | Tests | What it covers |
|------|------|-------|----------------|
| `tests/conftest.py` | Fixtures | - | db_session, client, test users, auth headers |
| `tests/unit/test_security.py` | Unit | 28 | Password hash/verify, JWT create/verify, password strength, bearer extraction |
| `tests/unit/test_auth_service.py` | Unit | 22 | AuthService with mocked UserRepository |
| `tests/unit/test_schemas.py` | Unit | 40 | Pydantic schemas, enums, validation constraints |
| `tests/integration/test_auth_routes.py` | Integration | 18 | Full HTTP cycle: register, login, refresh, me, logout |
| `tests/integration/test_health.py` | Integration | 8 | Health check and root endpoint |

### Known Patterns
- Unit tests for services: mock `service.user_repo` after construction with `MagicMock()`
- Mock user objects: `MagicMock(spec=User)` with real `hash_password()` for password_hash
- Integration tests: register via HTTP, then login (self-contained test data)
- Auth headers: `create_access_token({"user_id": str(user.id)})` -> `Bearer` header

### Potential Issues / TODO
- `FaceData.bbox` uses `min_items`/`max_items` which is Pydantic v1 syntax; may need `min_length`/`max_length` in Pydantic v2 (could cause test failure)
- `UserResponse.from_orm()` is Pydantic v1 style; in v2 it should be `UserResponse.model_validate()`
- `from_attributes = True` is set in Config which is correct for Pydantic v2
- If `from_orm` fails, route integration tests for register/login will fail at the router level
- APScheduler import might produce warnings during tests
