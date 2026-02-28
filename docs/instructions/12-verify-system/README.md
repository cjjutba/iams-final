# Step 12: Verify the System

Run through this checklist to confirm everything is set up correctly before pilot testing.

---

## Checklist

### Database
- [ ] Docker Desktop is running
- [ ] `docker ps` shows `iams-postgres` with status "Up"
- [ ] Database has 12 tables (check with pgAdmin or `\dt` command)

### Backend Server
- [ ] Backend is running (`python run.py`)
- [ ] http://localhost:8000/api/v1/health returns `{"status": "healthy"}`
- [ ] http://localhost:8000/docs loads the Swagger UI

### Authentication
- [ ] Faculty login works:
  - `POST /api/v1/auth/login` with `faculty@gmail.com` / `password123`
  - Response includes `access_token` and `refresh_token`

### Mobile App
- [ ] App opens and shows the login/register screen
- [ ] Faculty can log in from the mobile app
- [ ] Student can verify their Student ID (`21-A-02177`)
- [ ] Student registration flow completes (ID verification > account creation > face capture)

### Network
- [ ] Phone can reach `http://<laptop-ip>:8000/docs` from its browser
- [ ] All devices are on the same Wi-Fi network

### Camera (if connected)
- [ ] Camera is accessible via RTSP (test with VLC)
- [ ] Faculty can see the live feed from the mobile app dashboard

---

## How to Test Each Item

### Test the health endpoint
```bash
curl http://localhost:8000/api/v1/health
```
Expected: `{"status":"healthy"}`

### Test faculty login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"faculty@gmail.com\", \"password\": \"password123\"}"
```
Expected: JSON response with `access_token`, `refresh_token`, and user details.

### Test student ID verification
```bash
curl http://localhost:8000/api/v1/auth/verify-student-id/21-A-02177
```
Expected: JSON with student details (name, course, year, section).

### Test database tables
```bash
docker exec -it iams-postgres psql -U postgres -d iams -c "
SELECT 'users' AS tbl, COUNT(*) FROM users
UNION ALL SELECT 'rooms', COUNT(*) FROM rooms
UNION ALL SELECT 'schedules', COUNT(*) FROM schedules
UNION ALL SELECT 'student_records', COUNT(*) FROM student_records;
"
```
Expected:
```
      tbl       | count
----------------+-------
 users          |     1
 rooms          |     3
 schedules      |    13
 student_records|     1
```

---

**Next step:** [13 - Daily Operation](../13-daily-operation/README.md)
