# Testing Guide

## Testing Strategy

| Type | Scope | Tools |
|------|-------|-------|
| Unit | Individual functions | pytest |
| Integration | API endpoints | pytest + httpx |
| End-to-end | Full system flow | Manual + scripts |
| Performance | Load and speed | locust (optional) |
| Validation | Success metrics (PRD) | Scripts + manual runs |

---

## Validation Strategy (Success Metrics)

The PRD defines success metrics. Use this strategy to assess whether the system meets them.

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Face detection accuracy | ≥ 95% | Run detector on labeled test set (faces + non-faces). Accuracy = correct detections / total. Use WIDER-Face or custom labeled frames. |
| Face recognition accuracy | ≥ 92% | Register N users; send known face crops; count correct matches. Accuracy = correct matches / total. Vary lighting/angle in test set. |
| Early-leave detection accuracy | ≥ 90% | Simulate sessions: student present then leaves. Count true positives (flagged when actually left) and false positives (flagged when still present). Accuracy = TP / (TP + FP + FN) or use F1; document definition. |
| System response time | < 3 seconds | Measure time from RPi sending a face to server returning recognition result. Use timestamps or pytest timing; report p95. |
| Mobile app response | < 2 seconds | Measure time from user action (e.g. open attendance) to data displayed. Use React Native / Jest or manual stopwatch; report typical case. |

### Validation Test Data
- **Detection:** 100+ frames with labeled face bounding boxes (include occluded, profile, poor light).
- **Recognition:** 5–10 registered users, 20+ crops per user (different angles/lighting).
- **Early leave:** 10+ simulated sessions with known leave times; compare flagged time vs actual.
- **Latency:** Run 50+ requests; record RPi→server and app→server latency.

### When to Run
- After Phase 4 (face recognition) for detection and recognition metrics.
- After Phase 5 (presence) for early-leave and system response time.
- After Phase 7 (mobile) for mobile app response.
- Before thesis defense: run full validation and document results in a short report.

---

## Unit Testing

### What to Test
| Module | Test Cases |
|--------|------------|
| Auth Service | Password hashing, token generation, validation |
| Face Service | Embedding generation, similarity matching |
| Presence Service | Miss counting, early leave logic |
| User Service | CRUD operations, validation |

### Test Structure
```
tests/
├── unit/
│   ├── test_auth_service.py
│   ├── test_face_service.py
│   ├── test_presence_service.py
│   └── test_user_service.py
├── integration/
│   ├── test_auth_endpoints.py
│   ├── test_face_endpoints.py
│   └── test_attendance_endpoints.py
├── fixtures/
│   ├── users.py
│   ├── faces.py
│   └── schedules.py
└── conftest.py
```

### Sample Test Cases

#### Auth Service
| Test | Input | Expected |
|------|-------|----------|
| Hash password | "password123" | Bcrypt hash |
| Verify correct password | hash + "password123" | True |
| Verify wrong password | hash + "wrongpass" | False |
| Generate token | user_id | Valid JWT |
| Decode valid token | valid JWT | user_id |
| Decode expired token | expired JWT | Exception |

#### Face Service
| Test | Input | Expected |
|------|-------|----------|
| Generate embedding | Face image | 512-dim vector |
| Match same person | 2 images of same person | Similarity > 0.6 |
| Match different people | 2 images of different people | Similarity < 0.6 |
| No face in image | Image without face | Exception or None |

#### Presence Service
| Test | Input | Expected |
|------|-------|----------|
| First detection | Student detected | miss_count = 0 |
| Miss one scan | Student not detected | miss_count = 1 |
| Recovery after miss | Detected after 1 miss | miss_count = 0 |
| Early leave trigger | 3 consecutive misses | Flag raised |
| Calculate score | 8/10 scans present | 80% |

---

## Integration Testing

### API Endpoint Tests

#### Auth Endpoints
| Endpoint | Test | Expected |
|----------|------|----------|
| POST /auth/register | Valid data | 201, user created |
| POST /auth/register | Duplicate email | 400, error |
| POST /auth/login | Valid credentials | 200, tokens |
| POST /auth/login | Wrong password | 401, error |
| GET /auth/me | Valid token | 200, user data |
| GET /auth/me | No token | 401, error |

#### Face Endpoints
| Endpoint | Test | Expected |
|----------|------|----------|
| POST /face/register | Valid images | 201, registered |
| POST /face/register | No face in image | 400, error |
| POST /face/recognize | Registered face | 200, matched |
| POST /face/recognize | Unknown face | 200, not matched |
| POST /face/process | Valid payload (Edge API) | 200, processed count and matched list |

#### Attendance Endpoints
| Endpoint | Test | Expected |
|----------|------|----------|
| GET /attendance/today | Valid schedule | 200, records |
| GET /attendance/me | Student token | 200, own records |
| GET /attendance/me | Faculty token | 403, forbidden |
| POST /attendance/manual | Faculty token | 201, created |
| POST /attendance/manual | Student token | 403, forbidden |

---

## End-to-End Testing

### Test Scenarios

#### Scenario 1: Student Registration (React Native)
```
1. Complete onboarding and welcome; select Student
2. Tap Register; Step 1: enter Student ID (or scan); verify against university data
3. Step 2: enter email, phone, password; create account (Supabase Auth)
4. Step 3: capture 3–5 face angles; review and submit
5. Backend saves face to FAISS; link to user
6. Verify face is registered; login and view attendance
```

#### Scenario 2: Attendance Marking
```
1. Start class session
2. RPi detects student face
3. Server recognizes student
4. Attendance marked as present
5. Mobile app shows update
```

#### Scenario 3: Continuous Presence
```
1. Student marked present at start
2. System runs 10 scans (10 minutes)
3. Student detected in all scans
4. Presence score = 100%
5. No early leave flag
```

#### Scenario 4: Early Leave Detection
```
1. Student marked present at start
2. Student leaves after 5 minutes
3. System misses student for 3 scans
4. Early leave flag raised
5. Faculty receives alert
6. Attendance status = early_leave
```

#### Scenario 5: Recovery After Brief Absence
```
1. Student present for 5 scans
2. Student not detected for 2 scans (restroom)
3. Student detected again on scan 8
4. miss_count resets to 0
5. No early leave flag
6. Presence score = 80%
```

#### Scenario 6: RPi Queue When Server Down
```
1. Stop server
2. RPi continues capturing; queue fills (up to max size)
3. Restart server
4. RPi retries; queued faces sent
5. Verify no crash; optional: verify oldest dropped if queue was full
```

---

## Test Data

### Test Users
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@test.com | admin123 |
| Faculty | faculty@test.com | faculty123 |
| Student 1 | student1@test.com | student123 |
| Student 2 | student2@test.com | student123 |

### Test Schedule
| Subject | Day | Time | Room |
|---------|-----|------|------|
| CS101 | Monday | 08:00-10:00 | Room 301 |

### Test Face Images
- 5 images per test user
- Different angles (front, left, right)
- Different lighting
- With/without glasses

---

## Running Tests

### Commands
```
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/unit/test_auth_service.py

# Run specific test
pytest tests/unit/test_auth_service.py::test_hash_password

# Run with verbose output
pytest -v

# Run only fast tests
pytest -m "not slow"
```

### Coverage Targets
| Module | Target |
|--------|--------|
| Services | 80% |
| Routers | 70% |
| Utils | 90% |
| Overall | 75% |

---

## Manual Testing Checklist

### Before Demo
- [ ] Database has test data
- [ ] FAISS has registered faces
- [ ] RPi connected and capturing
- [ ] Server running without errors
- [ ] Mobile app installed on test phone
- [ ] WebSocket connection working

### Demo Flow
- [ ] Show face registration (mobile)
- [ ] Show recognition working (RPi + server)
- [ ] Show real-time attendance update (mobile)
- [ ] Show early leave detection
- [ ] Show attendance history

### Edge Cases to Test
- [ ] Poor lighting
- [ ] Multiple faces in frame
- [ ] Face with glasses
- [ ] Face partially covered
- [ ] Student not registered
- [ ] Network disconnection
- [ ] Server restart during session
- [ ] RPi queue when server unreachable (see implementation.md)

---

## Performance Testing

### Metrics to Measure
| Metric | Target | Tool |
|--------|--------|------|
| Face detection time | < 50ms | Timer in code |
| Face recognition time | < 100ms | Timer in code |
| API response time | < 500ms | pytest timing |
| WebSocket latency | < 200ms | Browser DevTools |
| End-to-end (RPi→server) | < 3s | See Validation Strategy |

### Load Testing (Optional)
| Scenario | Concurrent Users | Duration |
|----------|------------------|---------|
| Light load | 10 | 5 min |
| Normal load | 30 | 10 min |
| Peak load | 50 | 5 min |

---

## Bug Reporting Template

```
Title: [Short description]

Environment:
- OS: Windows 11
- Python: 3.11
- Browser/App: React Native app v1.0

Steps to Reproduce:
1. Step one
2. Step two
3. Step three

Expected Result:
What should happen

Actual Result:
What actually happened

Screenshots/Logs:
[Attach if available]

Severity: Critical / High / Medium / Low
```
