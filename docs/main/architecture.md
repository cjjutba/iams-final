# System Architecture

## Overview
IAMS uses a two-tier architecture: an edge device (Raspberry Pi) captures and detects faces, then sends them to a backend server (laptop or cloud) for recognition and tracking. Database and authentication are handled by **Supabase** (PostgreSQL + Auth). The mobile app is built with **React Native** and can talk to the backend over the same network (pilot) or over the internet (cloud backend).

## Architecture Diagram

```
CLASSROOM                    BACKEND (Laptop or Cloud VM)
┌─────────────────────┐     ┌─────────────────────────────────┐
│   Raspberry Pi      │     │   FastAPI Backend               │
│   ┌───────────┐     │     │   ┌─────────────────────────┐   │
│   │  Camera   │     │ WiFi │   │  Face Recognition       │   │
│   └─────┬─────┘     │ ───►│   │  (FaceNet + FAISS)      │   │
│         ▼           │     │   └─────────────────────────┘   │
│   ┌───────────┐     │     │   ┌─────────────────────────┐   │
│   │  Face     │     │     │   │  Tracking + Presence    │   │
│   │  Detect   │     │     │   │  (DeepSORT + Algorithm) │   │
│   └─────┬─────┘     │     │   └─────────────────────────┘   │
│         ▼           │     │   ┌─────────────────────────┐   │
│   ┌───────────┐     │     │   │  FAISS (local)         │   │
│   │  Crop &   │     │     │   └─────────────────────────┘   │
│   │  Send     │     │     └───────────────┬─────────────────┘
│   └───────────┘     │                     │
└─────────────────────┘                     │
                                            │ HTTPS / WebSocket
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
            │   Supabase    │       │ Student App   │       │ Faculty App   │
            │ (PostgreSQL   │       │(React Native) │       │(React Native) │
            │  + Auth)      │       └───────────────┘       └───────────────┘
            └───────────────┘
```

## Components

### Edge Layer (Raspberry Pi)
| Component | Responsibility |
|-----------|----------------|
| Camera Module | Capture video frames |
| Face Detector | Find faces in frame (MediaPipe) |
| Cropper | Extract and compress face images |
| Sender | POST cropped faces to backend |

### Backend Layer (Laptop or Cloud)
| Component | Responsibility |
|-----------|----------------|
| API Gateway | Handle all HTTP/WebSocket requests |
| Auth | Supabase Auth or JWT validation (backend verifies tokens) |
| Face Service | Generate embeddings, match faces |
| Tracking Service | Track identities across frames |
| Presence Service | Log presence, detect early leave |
| Notification Service | Push alerts via WebSocket |

### Data Layer
| Store | Purpose |
|-------|---------|
| Supabase (PostgreSQL) | Users, schedules, attendance records |
| Supabase Auth | Login, registration (students); faculty pre-seeded |
| FAISS (on backend) | Face embeddings for fast similarity search |
| File System | Registered face images (optional backup) |

### Client Layer
| App | Users | Features |
|-----|-------|----------|
| Student App (React Native) | Students | Onboarding, register (verify ID → account → face), view attendance |
| Faculty App (React Native) | Faculty | Login only (pre-seeded), live dashboard, alerts, reports |

## Data Flow

### Attendance Marking
```
1. Camera captures frame
2. RPi detects faces
3. RPi crops and sends to backend
4. Backend generates embedding
5. Backend searches FAISS for match
6. If matched → mark present (write to Supabase)
7. Push update to mobile apps via WebSocket
```

### Continuous Presence Check
```
1. Backend runs scan every 60 seconds
2. For each enrolled student:
   - If detected → reset miss counter
   - If not detected → increment miss counter
3. If miss counter ≥ 3 → flag early leave
4. Send alert to faculty app
```

## Network

| Connection | Protocol | Port / Notes |
|------------|----------|--------------|
| RPi → Backend | HTTP POST | 8000 (or cloud URL) |
| Mobile → Backend | HTTP/WebSocket | 8000 or HTTPS |
| Mobile → Supabase | HTTPS | Auth, optional data |
| Backend → Supabase | TCP (Postgres) | 5432 or Supabase pooler |

## Security
- JWT tokens (Supabase Auth or custom) for API authentication
- HTTPS in production and for Supabase
- Face embeddings stored (not raw images)
- Role-based access (student, faculty, admin)

## Deployment Options (Pilot)
- **Local pilot:** Backend on laptop/lab machine; RPi and phones on same WiFi; Supabase in cloud for DB + Auth.
- **Cloud pilot:** Backend on cloud VM; RPi and phones reach backend URL; Supabase for DB + Auth. Enables access from anywhere.

## Scalability Path
- Current: 1 classroom, 1 RPi, backend (local or cloud), Supabase
- Future: Multiple RPis → Cloud server → Load balancer
