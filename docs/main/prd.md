# Product Requirements Document (PRD)

## Project Name
**IAMS** — Intelligent Attendance Monitoring System

## Problem Statement
Current attendance systems only check students once at entry. Students can leave early undetected. Manual roll calls waste class time and are prone to errors.

## Solution
A camera-based system that continuously monitors student presence throughout class sessions and alerts faculty when students leave early.

## Target Users

| User | Needs |
|------|-------|
| Students | View attendance status, receive notifications |
| Faculty | Monitor live attendance, receive early-leave alerts |
| Admin | Manage users, schedules, generate reports (optional; no admin dashboard in MVP) |

## Core Features

### Must Have (MVP)
- Face registration via mobile app (students only)
- Automatic attendance marking when student detected
- Continuous presence tracking during class
- Early-leave detection and alerts
- Mobile app for students (view attendance)
- Mobile app for faculty (live dashboard, alerts)
- Attendance history and records
- Student registration with university validation (manual Student ID + optional ID scan)
- Faculty login only (pre-seeded accounts; no self-registration in MVP)

### Should Have
- Manual attendance override by faculty
- Attendance reports (export to CSV/PDF)
- Late arrival detection
- Schedule management

### Nice to Have
- Web admin dashboard
- Faculty registration via invite code
- Analytics and trends
- Multiple classroom support
- Parent notifications

## User Stories

### Student
- As a student, I can complete onboarding and choose "Student" on the welcome screen
- As a student, I can register by verifying my identity (Student ID manual or scan), then creating account and registering my face
- As a student, I can register my face so the system recognizes me
- As a student, I can view my attendance status for today
- As a student, I can see my attendance history

### Faculty
- As a faculty, I can log in with pre-provided credentials (no self-registration in MVP)
- As a faculty, I can see who is present in my current class
- As a faculty, I receive an alert when a student leaves early
- As a faculty, I can view attendance summary after class
- As a faculty, I can manually mark attendance if system fails

### Admin
- As an admin, I can add/remove users (via scripts or future dashboard)
- As an admin, I can create class schedules
- As an admin, I can assign students to classes

## Registration Flows (Summary)

### Student Registration
1. **Onboarding** — 4–5 slides (what is IAMS, how attendance works, face registration, privacy)
2. **Welcome** — User selects "Student" or "Faculty"
3. **Student Login** — Student ID + password; link "Register" for new users
4. **Register flow (3 steps + review):**
   - **Step 1 – Verify identity:** Enter Student ID (manual) or optionally scan/upload ID. System validates against university data (CSV/JRMSU). Show name, course, year; user confirms "Is this me?"
   - **Step 2 – Account setup:** Email (pre-filled if from university), phone, password
   - **Step 3 – Face registration:** Capture 3–5 angles, review photos
   - **Review & submit:** Summary screen; user agrees to terms and creates account. Backend validates and creates account (and optionally syncs with Supabase Auth)

### Faculty Registration (MVP)
- **No self-registration.** Faculty accounts are **pre-seeded** from a list provided by the client (JRMSU). Faculty only **login** (email + password). Message on login screen: "Faculty accounts are created by the administrator. Contact your department if you need access."
- **Future:** Optional invite-code flow: department provides code → faculty enters code → confirm details → set email/password → account created. No face registration for faculty.

## Pilot Testing

- **Pilot:** Deploy system in specific classroom(s); students and faculty use **their own mobile phones** to access the app.
- **Deployment options:**
  - **Same WiFi only:** Backend runs on laptop or lab machine; phones on same campus WiFi. App and RPi talk to local server. Supabase used for DB + Auth (hosted).
  - **Access from anywhere:** Backend (FastAPI) on cloud VM; Supabase for DB + Auth. Phones and RPi reach same API URL. Enables checking attendance from home or other buildings.
- **Data:** Student/faculty validation and schedules use university data. For thesis: client provides CSV export (e.g. engineering students, faculty, schedule for that classroom). Import once or sync via script. Live university API optional if client provides it.

## Success Metrics

| Metric | Target |
|--------|--------|
| Face detection accuracy | ≥ 95% |
| Face recognition accuracy | ≥ 92% |
| Early-leave detection accuracy | ≥ 90% |
| System response time | < 3 seconds |
| Mobile app response | < 2 seconds |

## Constraints
- Single classroom deployment (pilot)
- Requires network access (same WiFi for local server, or internet for cloud)
- Camera must have clear view of students
- Students must register face beforehand
- Faculty accounts pre-seeded in MVP (no admin dashboard)

## Out of Scope
- Outdoor tracking
- Behavior analysis
- Emotion detection
- Integration with school LMS
- Full admin dashboard in MVP

## Timeline
12 weeks for MVP

## Hardware Required
- Raspberry Pi 4 (4GB)
- Camera module or USB webcam
- Laptop as local server (with GPU) or cloud VM for pilot
- Mobile phones for testing (students/faculty use own devices)

## Data Requirements from Client (JRMSU)
- **Students:** CSV with student_id, last_name, first_name, course, year, section, email (optional)
- **Faculty:** CSV with employee_id, last_name, first_name, department, email (for pre-seeding)
- **Schedule:** CSV with subject_code, subject_name, faculty_employee_id, day_of_week, start_time, end_time (single classroom)
