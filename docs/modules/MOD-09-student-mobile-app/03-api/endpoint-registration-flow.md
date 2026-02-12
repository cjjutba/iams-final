# Endpoint Contract: Registration Flow

## Scope
Endpoints used in student registration flow (Steps 1-4).

## Endpoints
| Endpoint | Auth | Step | Purpose |
|---|---|---|---|
| `POST /auth/verify-student-id` | Pre-auth (no JWT) | Step 1 | Verify student identity against `student_records` |
| `POST /auth/register` | Pre-auth (no JWT) | Step 2 | Create student account (returns tokens) |
| `POST /face/register` | Post-auth (JWT) | Step 3 | Upload 3-5 face images for registration |

## Step Mapping
- **Step 1** (`SCR-007`): Verify student identity (pre-auth).
- **Step 2** (`SCR-008`): Collect account details and register (pre-auth → returns JWT).
- **Step 3** (`SCR-009`): Upload 3-5 face images (post-auth, uses JWT from Step 2).
- **Step 4** (`SCR-010`): Review and confirm (post-auth, no additional API call).

## Step 1: Verify Student ID
```json
POST /api/v1/auth/verify-student-id
Content-Type: application/json

{
  "student_id": "21-A-02177"
}
```
**Auth**: No JWT required (pre-auth).

### Success Response
```json
{
  "success": true,
  "data": {
    "student_id": "21-A-02177",
    "first_name": "Chris",
    "last_name": "Jutba",
    "course": "CPE",
    "year": 4,
    "section": "A",
    "email": "cjjutbaofficial@gmail.com"
  }
}
```

### Error Response (unknown ID)
```json
{
  "success": false,
  "error": {
    "code": "STUDENT_NOT_FOUND",
    "message": "Student ID not found in records"
  }
}
```

### Error Response (already registered)
```json
{
  "success": false,
  "error": {
    "code": "ALREADY_REGISTERED",
    "message": "Student ID is already registered"
  }
}
```

## Step 2: Register Account
```json
POST /api/v1/auth/register
Content-Type: application/json

{
  "student_id": "21-A-02177",
  "email": "cjjutbaofficial@gmail.com",
  "password": "securepassword",
  "first_name": "Chris",
  "last_name": "Jutba"
}
```
**Auth**: No JWT required (pre-auth).

### Success Response (returns tokens)
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": {
      "id": "uuid",
      "email": "cjjutbaofficial@gmail.com",
      "role": "student"
    }
  }
}
```

## Step 3: Face Registration
```
POST /api/v1/face/register
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

images: [file1, file2, file3, ...]  (3-5 images)
```
**Auth**: Post-auth (JWT required from Step 2 registration response).

## Validation Rules
- `verify-student-id` must validate against `student_records` table.
- Duplicate student_id registration is rejected.
- Face upload must satisfy image quality and count constraints (3-5).
- Final submit blocked until all required steps are complete.
- No step skipping — each step must complete before the next enables.
