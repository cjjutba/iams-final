# API Reference

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication

**Auth Provider:** Supabase Auth. Mobile app uses Supabase client SDK (`@supabase/supabase-js`) for login, token refresh, and password reset. Backend verifies Supabase-issued JWT on all protected routes.

All protected endpoints require:
```
Header: Authorization: Bearer <supabase_jwt>
```

---

## Auth Endpoints (Backend)

### Verify Student Identity (Registration Step 1)
```
POST /auth/verify-student-id

Request:
{
  "student_id": "2024-0001"
}

Response (200) - Valid:
{
  "success": true,
  "data": {
    "valid": true,
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "course": "BS Computer Engineering",
    "year": "3rd Year",
    "section": "CPE-3A",
    "email": "juandelacruz@email.com"
  }
}

Response (200) - Invalid:
{
  "success": true,
  "data": { "valid": false }
}
```
*Validates against university data (CSV/JRMSU). Used by React Native app in student registration Step 1.*

### Register User (Student – after identity verified)
```
POST /auth/register

Request:
{
  "email": "student@email.com",
  "password": "securepassword",
  "first_name": "Juan",
  "last_name": "Dela Cruz",
  "role": "student",
  "student_id": "2024-0001",
  "phone": "09171234567"
}

Response (201):
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "role": "student"
  },
  "message": "Account created. Please check your email to verify your account."
}
```
*Backend creates user in Supabase Auth (via Admin API) and inserts profile into local `users` table. Supabase sends email verification automatically. `phone` is optional.*

### Get Current User
```
GET /auth/me

Header: Authorization: Bearer <supabase_jwt>

Response (200):
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "role": "student",
    "student_id": "2024-0001",
    "phone": "09171234567",
    "email_confirmed": true
  }
}
```

---

## Auth Operations (Supabase Client — Mobile)

These operations are handled by the Supabase client SDK on the mobile app. They do not hit backend endpoints.

### Login
```
supabase.auth.signInWithPassword({ email, password })

Returns Supabase session:
{
  "access_token": "supabase_jwt",
  "refresh_token": "refresh_token",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": { ... }
}
```
*Mobile stores tokens via Supabase client. Backend does not have a /auth/login endpoint; login is handled entirely by Supabase client. Backend checks `is_active` and `email_confirmed` on protected route access.*

### Token Refresh
```
supabase.auth.refreshSession()

Returns new Supabase session with refreshed access_token.
```
*Supabase client handles refresh automatically when access token expires. No backend endpoint needed.*

### Request Password Reset
```
supabase.auth.resetPasswordForEmail(email, { redirectTo })

Supabase sends password reset email to user.
```

### Complete Password Reset
```
supabase.auth.updateUser({ password: newPassword })

Called after user clicks reset link and is redirected back to the app.
```

### Email Verification
```
Automatic: Supabase sends confirmation email on registration.
User clicks verification link in email.
Supabase sets email_confirmed_at on the user record.
Backend syncs this status and enforces it on protected routes.
```

---

## User Endpoints

### List Users (Admin)
```
GET /users?role=student&page=1&limit=20

Response (200):
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100
  }
}
```

### Get User
```
GET /users/{id}

Response (200):
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "student@email.com",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "role": "student",
    "student_id": "2024-0001",
    "phone": "09171234567",
    "is_active": true,
    "email_confirmed": true,
    "created_at": "2026-01-15T10:00:00Z"
  }
}
```
*Requires admin or own record (JWT `sub` matches path `id`).*

### Update User
```
PATCH /users/{id}

Request (student/faculty — own profile):
{
  "first_name": "Updated Name",
  "phone": "09179876543"
}

Response (200):
{
  "success": true,
  "data": { ... }
}
```
*Editable fields: first_name, last_name, phone. Email is immutable (returns 400). Admin can also update role, student_id, is_active.*

### Delete User (Admin)
```
DELETE /users/{id}

Response (200):
{
  "success": true,
  "message": "User permanently deleted"
}
```

---

## Face Endpoints

### Register Face
```
POST /face/register

Request (multipart/form-data):
- images: File[] (3-5 face images)

Response (201):
{
  "success": true,
  "data": {
    "embedding_id": "uuid",
    "registered_at": "2024-01-15T10:00:00Z"
  }
}
```

### Recognize Face (Edge Device)
```
POST /face/recognize

Request (multipart/form-data):
- image: File (cropped face image)
- room_id: string

Response (200):
{
  "success": true,
  "data": {
    "matched": true,
    "user_id": "uuid",
    "confidence": 0.85,
    "student_name": "Juan Dela Cruz"
  }
}

Response (200) - No match:
{
  "success": true,
  "data": {
    "matched": false,
    "user_id": null,
    "confidence": 0.0
  }
}
```

### Process Frame (Edge Device) — Edge API Contract

Used by the Raspberry Pi to send one or more cropped faces per request. See technical-specification.md for full contract.

```
POST /face/process

Request (application/json):
{
  "room_id": "uuid",
  "faces": [
    {
      "image": "base64_encoded_jpeg",
      "bbox": [x, y, width, height]
    }
  ],
  "timestamp": "2024-01-15T10:00:00Z"
}

Response (200):
{
  "success": true,
  "data": {
    "processed": 3,
    "matched": [
      {"user_id": "uuid", "confidence": 0.85},
      {"user_id": "uuid", "confidence": 0.92}
    ],
    "unmatched": 1
  }
}
```

**Errors:** 400 (invalid payload), 401 (if protected), 500 (server/recognition error).

### Check Registration Status
```
GET /face/status

Response (200):
{
  "success": true,
  "data": {
    "registered": true,
    "registered_at": "2024-01-15T10:00:00Z"
  }
}
```

---

## Schedule Endpoints

### List Schedules
```
GET /schedules?day=1

Response (200):
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "subject_code": "CS101",
      "subject_name": "Programming 1",
      "faculty_name": "Dr. Santos",
      "room": "Room 301",
      "day_of_week": 1,
      "start_time": "08:00",
      "end_time": "10:00"
    }
  ]
}
```

### Get Schedule
```
GET /schedules/{id}

Response (200):
{
  "success": true,
  "data": { ... }
}
```

### Create Schedule (Admin)
```
POST /schedules

Request:
{
  "subject_code": "CS101",
  "subject_name": "Programming 1",
  "faculty_id": "uuid",
  "room_id": "uuid",
  "day_of_week": 1,
  "start_time": "08:00",
  "end_time": "10:00"
}

Response (201):
{
  "success": true,
  "data": { ... }
}
```

### Get My Schedules (Student/Faculty)
```
GET /schedules/me

Response (200):
{
  "success": true,
  "data": [...]
}
```

### Get Schedule Students
```
GET /schedules/{id}/students

Response (200):
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "student_id": "2024-0001",
      "name": "Juan Dela Cruz"
    }
  ]
}
```

---

## Attendance Endpoints

### Get Today's Attendance
```
GET /attendance/today?schedule_id=uuid

Response (200):
{
  "success": true,
  "data": {
    "schedule": { ... },
    "records": [
      {
        "student_id": "uuid",
        "student_name": "Juan Dela Cruz",
        "status": "present",
        "check_in_time": "08:05:00",
        "presence_score": 95.5
      }
    ],
    "summary": {
      "total": 30,
      "present": 28,
      "late": 1,
      "absent": 1
    }
  }
}
```

### Get My Attendance (Student)
```
GET /attendance/me?start_date=2024-01-01&end_date=2024-01-31

Response (200):
{
  "success": true,
  "data": [
    {
      "date": "2024-01-15",
      "schedule": { ... },
      "status": "present",
      "check_in_time": "08:05:00",
      "presence_score": 95.5
    }
  ]
}
```

### Get Attendance History
```
GET /attendance?schedule_id=uuid&start_date=2024-01-01&end_date=2024-01-31

Response (200):
{
  "success": true,
  "data": [...],
  "pagination": { ... }
}
```

### Manual Attendance Entry (Faculty)
```
POST /attendance/manual

Request:
{
  "student_id": "uuid",
  "schedule_id": "uuid",
  "date": "2024-01-15",
  "status": "present",
  "remarks": "System was down"
}

Response (201):
{
  "success": true,
  "data": { ... }
}
```

### Get Live Attendance (Faculty)
```
GET /attendance/live/{schedule_id}

Response (200):
{
  "success": true,
  "data": {
    "session_active": true,
    "started_at": "08:00:00",
    "current_scan": 15,
    "students": [
      {
        "id": "uuid",
        "name": "Juan Dela Cruz",
        "status": "present",
        "last_seen": "08:45:00",
        "consecutive_misses": 0
      }
    ]
  }
}
```

---

## Presence Endpoints

### Get Presence Logs
```
GET /presence/{attendance_id}/logs

Response (200):
{
  "success": true,
  "data": [
    {
      "scan_number": 1,
      "scan_time": "08:05:00",
      "detected": true,
      "confidence": 0.92
    }
  ]
}
```

### Get Early Leave Events
```
GET /presence/early-leaves?schedule_id=uuid&date=2024-01-15

Response (200):
{
  "success": true,
  "data": [
    {
      "student_id": "uuid",
      "student_name": "Juan Dela Cruz",
      "detected_at": "09:30:00",
      "consecutive_misses": 3
    }
  ]
}
```

---

## WebSocket

### Connect
```
WS /ws/{user_id}
```

### Events Received
```
Attendance Update:
{
  "type": "attendance_update",
  "data": {
    "student_id": "uuid",
    "status": "present",
    "timestamp": "2024-01-15T08:05:00Z"
  }
}

Early Leave Alert:
{
  "type": "early_leave",
  "data": {
    "student_id": "uuid",
    "student_name": "Juan Dela Cruz",
    "schedule_id": "uuid",
    "detected_at": "2024-01-15T09:30:00Z"
  }
}

Session End:
{
  "type": "session_end",
  "data": {
    "schedule_id": "uuid",
    "summary": {
      "present": 28,
      "late": 1,
      "early_leave": 1,
      "absent": 0
    }
  }
}
```

---

## Error Responses

### 400 Bad Request
```
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "details": [...]
  }
}
```

### 401 Unauthorized
```
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token"
  }
}
```

### 403 Forbidden
```
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "You don't have permission"
  }
}
```

### 404 Not Found
```
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "User not found"
  }
}
```

### 500 Server Error
```
{
  "success": false,
  "error": {
    "code": "SERVER_ERROR",
    "message": "An unexpected error occurred"
  }
}
```
