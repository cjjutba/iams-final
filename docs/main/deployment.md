# Deployment Guide

## Deployment Options

| Environment | Use Case | Complexity |
|-------------|----------|------------|
| Local (Laptop) + Supabase | Development, thesis pilot (same WiFi) | Simple |
| Cloud (VPS) + Supabase | Pilot with access from anywhere | Medium |

---

## Pilot Testing

- **Pilot:** Deploy in specific classroom(s); students and faculty use **their own mobile phones** (React Native app).
- **Same WiFi only:** Backend on laptop/lab machine; phones and RPi on same campus WiFi; Supabase in cloud for DB + Auth.
- **Access from anywhere:** Backend on cloud VM; Supabase for DB + Auth; phones and RPi reach backend URL.

---

## Local Deployment (Recommended for Thesis)

### Prerequisites
- Windows 11 laptop with GPU
- Supabase project created (DB + Auth)
- Python 3.11 installed
- Raspberry Pi connected to same WiFi
- Node.js 20+ (for React Native)

### Step 1: Supabase (Database & Auth)
```
1. Create Supabase project at supabase.com
2. Run migrations (create users, schedules, attendance tables) via Supabase SQL or migrations
3. Note SUPABASE_URL and SUPABASE_ANON_KEY
4. (Optional) Enable Email auth for students; pre-seed faculty via SQL or script
```

### Step 2: Backend
```
1. Navigate to backend folder
2. Create virtual environment
3. Install dependencies
4. Copy .env.example to .env
5. Set SUPABASE_URL, SUPABASE_ANON_KEY, DATABASE_URL (Supabase pooler)
6. Run migrations if using Alembic; else ensure Supabase schema is applied
7. Start server (uvicorn)
```

### Step 3: Edge Device
```
1. SSH into Raspberry Pi
2. Clone edge code
3. Install dependencies
4. Update SERVER_URL in .env (laptop IP:8000 or cloud URL)
5. Configure queue policy (see implementation.md) if needed
6. Start capture service
```

### Step 4: Mobile App (React Native)
```
1. Set API_BASE_URL and SUPABASE_URL/SUPABASE_ANON_KEY in .env or constants
2. npm install / yarn; npx react-native run-android or run-ios
3. Build APK/IPA and install on test devices (students/faculty use own phones)
```

### Network Setup
```
Laptop IP: 192.168.1.100 (example)
Backend URL: http://192.168.1.100:8000
Supabase: https://xxx.supabase.co (cloud)
All pilot devices on same WiFi for local backend
```

---

## Cloud Deployment (Future)

### Architecture
```
Internet
    │
    ▼
┌─────────────┐
│   Domain    │ (api.yourapp.com)
│   + SSL     │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│    VPS      │     │  Supabase   │
│  (Docker)   │────►│  (Postgres  │
│ ┌─────────┐ │     │   + Auth)   │
│ │ FastAPI │ │     └─────────────┘
│ └─────────┘ │
└─────────────┘
```

### VPS Requirements
| Resource | Minimum |
|----------|---------|
| CPU | 2 vCPU |
| RAM | 4 GB |
| Storage | 40 GB SSD |
| OS | Ubuntu 22.04 |

### Docker Setup

#### Dockerfile
```
Backend image:
- Base: python:3.11-slim
- Install dependencies
- Copy application code
- Expose port 8000
- Run uvicorn
```

#### docker-compose.yml
```
Services:
- api (FastAPI application)
- db (PostgreSQL)
- Optional: nginx (reverse proxy)

Volumes:
- PostgreSQL data
- FAISS index
- Logs
```

### Deployment Steps

| Step | Task |
|------|------|
| 1 | Provision VPS |
| 2 | Install Docker and Docker Compose |
| 3 | Clone repository |
| 4 | Configure environment variables |
| 5 | Build Docker images |
| 6 | Start containers |
| 7 | Setup SSL with Certbot |
| 8 | Configure domain DNS |
| 9 | Update RPi and mobile URLs |
| 10 | Test all connections |

### SSL Setup
```
1. Install Certbot
2. Obtain certificate for domain
3. Configure nginx to use certificate
4. Auto-renewal via cron
```

---

## Environment Configuration

### Backend (.env)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
SECRET_KEY=your-local-secret-key
DEBUG=true
CORS_ORIGINS=*
```

### Production (.env.production)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=postgresql://...  # Supabase pooler
SECRET_KEY=strong-random-secret-key
DEBUG=false
CORS_ORIGINS=https://yourapp.com
```

### Edge Device (.env)
```
SERVER_URL=http://192.168.1.100:8000  # Local
# SERVER_URL=https://api.yourapp.com  # Production
CAMERA_INDEX=0
FRAME_WIDTH=640
FRAME_HEIGHT=480
QUEUE_MAX_SIZE=500
QUEUE_TTL_SECONDS=300
RETRY_INTERVAL_SECONDS=10
```

### Mobile App (React Native) (.env or constants)
```
API_BASE_URL=http://192.168.1.100:8000  # or https://api.yourapp.com
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

---

## Startup Commands

### Backend (Local)
```
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Backend (Production)
```
docker-compose up -d
```

### Edge Device
```
cd edge
source venv/bin/activate
python run.py
```

### Auto-start Edge on Boot
```
Create systemd service:
- Service name: iams-edge
- ExecStart: /home/pi/edge/venv/bin/python /home/pi/edge/run.py
- Restart: always
- Enable service
```

---

## Health Checks

### Backend
```
GET /health

Response:
{
  "status": "healthy",
  "database": "connected",
  "faiss": "loaded"
}
```

### Monitoring Checklist
| Check | Frequency |
|-------|-----------|
| API response | Every 1 min |
| Database connection | Every 5 min |
| Edge device status | Every 1 min |
| Disk space | Every 1 hour |
| Memory usage | Every 5 min |

---

## Backup Strategy

### Database
| What | Frequency | Retention |
|------|-----------|-----------|
| Full backup | Daily | 7 days |
| Transaction logs | Continuous | 24 hours |

### FAISS Index
| What | Frequency | Retention |
|------|-----------|-----------|
| Index file | Daily | 7 days |
| After new registrations | Immediate | Latest only |

### Backup Commands
```
Database:
pg_dump iams > backup_$(date +%Y%m%d).sql

FAISS:
cp data/faiss/faces.index backups/faces_$(date +%Y%m%d).index
```

---

## Troubleshooting

### Backend won't start
| Symptom | Check |
|---------|-------|
| Port in use | Kill process on 8000 |
| Database error | Verify PostgreSQL running |
| Module not found | Activate virtualenv |

### Edge device issues
| Symptom | Check |
|---------|-------|
| Camera not found | Check connection, permissions |
| Can't reach server | Verify network, firewall |
| High CPU | Reduce frame rate |
| Queue full / drops | See implementation.md queue policy; check SERVER_URL and retry interval |

### Mobile app issues
| Symptom | Check |
|---------|-------|
| Can't connect | Verify server URL, same network |
| Login fails | Check credentials, token |
| No updates | WebSocket connection |

---

## Rollback Plan

### If deployment fails
```
1. Stop new containers
2. Restore previous database backup
3. Start previous container version
4. Verify functionality
5. Investigate failure cause
```

### Version tags
```
Always tag releases:
- v1.0.0 (initial release)
- v1.0.1 (bug fixes)
- v1.1.0 (new features)
```
