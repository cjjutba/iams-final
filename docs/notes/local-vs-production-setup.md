# IAMS: Local Development vs Production Setup Guide

This guide explains how to switch between **local Docker Desktop** (for testing) and **production VPS** (for deployment). The codebase is the same — only environment variables and build configs change.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Local Setup (Docker Desktop)](#local-setup-docker-desktop)
4. [Production Setup (VPS)](#production-setup-vps)
5. [Android App Configuration](#android-app-configuration)
6. [Admin Portal Configuration](#admin-portal-configuration)
7. [Edge Device (Raspberry Pi) Configuration](#edge-device-raspberry-pi-configuration)
8. [Switching Between Local and Production](#switching-between-local-and-production)
9. [Database Seeding](#database-seeding)
10. [Testing the Full Pipeline Locally](#testing-the-full-pipeline-locally)
11. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
                    LOCAL (Docker Desktop)              PRODUCTION (VPS 167.71.217.44)
                    ─────────────────────               ──────────────────────────────
Docker Compose:     docker-compose.yml                  deploy/docker-compose.prod.yml
Backend .env:       backend/.env                        backend/.env.production
Backend URL:        http://<YOUR_LAN_IP>:8000           http://167.71.217.44 (port 80 via nginx)
mediamtx RTSP:      rtsp://<YOUR_LAN_IP>:8554           rtsp://167.71.217.44:8554
mediamtx WHEP:      http://<YOUR_LAN_IP>:8889           http://167.71.217.44:8889
Admin Portal:       http://localhost:5173                https://iams-thesis.vercel.app
Database:           postgresql://admin:123@...           postgresql://iams:iams_prod_password@...
```

Both environments run the same 7 services: PostgreSQL, Redis, mediamtx, coturn, api-gateway, dozzle, and a reverse proxy (nginx in production).

---

## Prerequisites

### For Local Development

- **Docker Desktop** installed and running (macOS, Windows, or Linux)
- **Git** to clone the repository
- **Android Studio** (for building and running the Android app)
  - Android SDK 35, minimum SDK 26
  - JDK 17
- **Node.js 18+** (for the admin portal, optional)
- **FFmpeg** (optional, for fake RTSP streams without cameras)
- **sshpass** (optional, for RPi deploy scripts)

### For Production Deployment

- SSH access to VPS (`ssh root@167.71.217.44`)
- `rsync` installed on your machine (pre-installed on macOS/Linux)

### Windows-Specific Notes

- Docker Desktop for Windows works with WSL2 backend (recommended)
- `host.docker.internal` works on Windows Docker Desktop (same as macOS)
- For `rsync`, install Git Bash or WSL — or manually copy files via SCP
- Android Studio wireless debugging: install Android SDK Platform Tools and ensure `adb` is in your PATH

---

## Local Setup (Docker Desktop)

### Step 1: Clone the Repository

```bash
git clone https://github.com/cjjutba/iams-final.git
cd iams-final
git checkout feat/architecture-redesign
```

### Step 2: Start All Services

```bash
docker compose up -d
```

This starts: postgres, redis, mediamtx, coturn, api-gateway, dozzle, adminer.

To rebuild after code changes:

```bash
docker compose up -d --build
```

### Step 3: Seed the Database

```bash
docker compose exec api-gateway python -m scripts.seed_data
```

This creates:
- 180 student records (from the student list)
- 5 faculty accounts
- 1 admin account (`admin@admin.com` / `123`)
- 2 rooms (EB226, EB227)
- 42 schedules (including 24/7 test schedules)

### Step 3b: Fix Room Camera Endpoints for Local

**IMPORTANT:** The seed script sets Room `camera_endpoint` to `rtsp://mediamtx:8554/eb226`, which works in production (Docker container DNS). Locally, the api-gateway container uses `host.docker.internal` to reach mediamtx, so you must update the Room records:

```bash
# Login as admin
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin@admin.com","password":"123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get room IDs
curl -s http://localhost:8000/api/v1/rooms/ -H "Authorization: Bearer $TOKEN"

# Update each room (replace ROOM_ID with actual UUIDs from above)
curl -X PATCH http://localhost:8000/api/v1/rooms/<EB226_ROOM_ID> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"camera_endpoint": "rtsp://host.docker.internal:8554/eb226"}'

curl -X PATCH http://localhost:8000/api/v1/rooms/<EB227_ROOM_ID> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"camera_endpoint": "rtsp://host.docker.internal:8554/eb227"}'
```

Without this fix, the backend FrameGrabber can't pull frames from mediamtx locally.

### Step 4: Find Your LAN IP

You need your computer's LAN IP so the Android phone can reach the backend.

**macOS:**
```bash
ipconfig getifaddr en0
```

**Windows:**
```powershell
ipconfig | findstr "IPv4"
```

Example: `192.168.88.20`

### Step 5: Verify Backend is Running

```bash
curl http://localhost:8000/api/v1/health
```

### Step 6: View Logs

```bash
# All services
docker compose logs -f

# Just the backend
docker compose logs -f api-gateway

# Recent logs only
docker compose logs --since 5m api-gateway
```

### Step 7: Stop Everything

```bash
docker compose down        # Stop containers (keep data)
docker compose down -v     # Stop and delete all data (full reset)
```

---

## Production Setup (VPS)

### Deploy to VPS

From the project root on your development machine:

```bash
bash deploy/deploy.sh
```

This script:
1. Syncs backend code to VPS via rsync
2. Syncs admin dashboard code
3. Syncs deploy configs (docker-compose, nginx, mediamtx)
4. Builds and restarts containers on VPS
5. Verifies health check

### Seed Production Database

```bash
ssh root@167.71.217.44 "cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml exec api-gateway python -m scripts.seed_data"
```

### View Production Logs

**Via Dozzle (web UI):**
Open http://167.71.217.44:9999 in your browser.

**Via SSH:**
```bash
ssh root@167.71.217.44 "cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml logs --since 10m api-gateway"
```

### Check Production Health

```bash
curl http://167.71.217.44/api/v1/health
```

---

## Android App Configuration

The Android app connects to the backend and mediamtx. The connection targets are set in `android/gradle.properties`.

### Switch to Local (Docker Desktop)

Edit `android/gradle.properties`:

```properties
# Local Docker Desktop — use your computer's LAN IP
IAMS_BACKEND_HOST=192.168.88.20
IAMS_BACKEND_PORT=8000
IAMS_MEDIAMTX_PORT=8554
IAMS_MEDIAMTX_WEBRTC_PORT=8889
```

Replace `192.168.88.20` with your actual LAN IP.

**Important:** The Android phone must be on the **same WiFi network** as the computer running Docker Desktop.

### Switch to Production (VPS)

Edit `android/gradle.properties`:

```properties
# Production VPS
IAMS_BACKEND_HOST=167.71.217.44
IAMS_BACKEND_PORT=80
IAMS_MEDIAMTX_PORT=8554
IAMS_MEDIAMTX_WEBRTC_PORT=8889
```

### After Changing — Rebuild the App

In Android Studio: **Build > Rebuild Project**, then **Run**.

Or via command line:

```bash
cd android
./gradlew assembleDebug
```

The config values are compiled into the APK via `BuildConfig`, so you must rebuild after any change.

---

## Admin Portal Configuration

### Switch to Local

Edit `admin/.env`:

```env
VITE_API_URL=http://192.168.88.20:8000/api/v1
VITE_WS_URL=ws://192.168.88.20:8000
```

Then run:

```bash
cd admin
npm install
npm run dev
```

Opens at http://localhost:5173.

### Switch to Production

Edit `admin/.env`:

```env
VITE_API_URL=/api/v1
VITE_WS_URL=ws://167.71.217.44
```

The production admin portal is deployed on Vercel at https://iams-thesis.vercel.app. Vercel proxies `/api/*` requests to the VPS automatically (configured in `admin/vercel.json`).

---

## Edge Device (Raspberry Pi) Configuration

The RPi is a dumb RTSP relay. It pushes the camera's RTSP stream to mediamtx.

### For Local Testing (RPi pushes to your computer)

SSH into the RPi and edit the environment file:

```bash
# EB226
ssh iams-eb226@192.168.88.12  # password: 123
nano ~/iams-relay.env
```

Change `VPS_RTSP_URL` to your computer's LAN IP:

```env
VPS_RTSP_URL=rtsp://192.168.88.20:8554
```

Then restart:

```bash
sudo systemctl restart iams-relay
```

### For Production (RPi pushes to VPS)

```env
VPS_RTSP_URL=rtsp://167.71.217.44:8554
```

Then restart:

```bash
sudo systemctl restart iams-relay
```

### Deploy Relay to RPi (from dev machine on IAMS-Net)

```bash
bash edge/scripts/deploy-relay.sh eb226   # Deploy to RPi EB226
bash edge/scripts/deploy-relay.sh eb227   # Deploy to RPi EB227
```

### RPi Credentials

| Device | IP | Username | Password |
|--------|-----|----------|----------|
| RPi EB226 | 192.168.88.12 | iams-eb226 | 123 |
| RPi EB227 | 192.168.88.15 | iams-eb227 | 123 |

### Camera Credentials

| Camera | IP | RTSP URL (sub stream) |
|--------|-----|-----------------------|
| EB226 (P340) | 192.168.88.10 | `rtsp://admin:%40Iams2026THESIS%21@192.168.88.10:554/h264Preview_01_sub` |
| EB227 (CX810) | 192.168.88.11 | `rtsp://admin:%40Iams2026THESIS%21@192.168.88.11:554/h264Preview_01_sub` |

---

## Switching Between Local and Production

### Quick Reference — What to Change

| Component | File to Edit | Local Value | Production Value |
|-----------|-------------|-------------|------------------|
| Android app | `android/gradle.properties` | `IAMS_BACKEND_HOST=<YOUR_LAN_IP>`, `IAMS_BACKEND_PORT=8000` | `IAMS_BACKEND_HOST=167.71.217.44`, `IAMS_BACKEND_PORT=80` |
| Admin portal | `admin/.env` | `VITE_API_URL=http://<YOUR_LAN_IP>:8000/api/v1` | `VITE_API_URL=/api/v1` |
| RPi relay | `~/iams-relay.env` on RPi | `VPS_RTSP_URL=rtsp://<YOUR_LAN_IP>:8554` | `VPS_RTSP_URL=rtsp://167.71.217.44:8554` |
| Backend | Automatic | Uses `backend/.env` via `docker-compose.yml` | Uses `backend/.env.production` via `docker-compose.prod.yml` |

### Step-by-Step: Switch to Local

1. Start Docker Desktop
2. Run `docker compose up -d` from project root
3. Seed DB: `docker compose exec api-gateway python -m scripts.seed_data`
4. Fix Room camera endpoints for local (see [Step 3b](#step-3b-fix-room-camera-endpoints-for-local))
5. Edit `android/gradle.properties` → set `IAMS_BACKEND_HOST` to your LAN IP, `IAMS_BACKEND_PORT=8000`
6. Rebuild Android app in Android Studio (Build > Rebuild Project, then Run)
7. (Optional) SSH into RPi and change `VPS_RTSP_URL` to your LAN IP, then `sudo systemctl restart iams-relay`
8. (Optional) Edit `admin/.env` and run `npm run dev` in `admin/`

### Step-by-Step: Switch to Production

1. Edit `android/gradle.properties` → set `IAMS_BACKEND_HOST=167.71.217.44`, `IAMS_BACKEND_PORT=80`
2. Rebuild Android app in Android Studio (Build > Rebuild Project, then Run)
3. Deploy backend: `bash deploy/deploy.sh`
4. SSH into RPi and change `VPS_RTSP_URL` to `rtsp://167.71.217.44:8554`, then `sudo systemctl restart iams-relay`
5. Admin portal: use https://iams-thesis.vercel.app (auto-deploys from git push)

### Network Requirements

- **Local testing with phones:** The Android phone and the computer running Docker Desktop must be on the **same WiFi network**. The phone connects to `http://<LAN_IP>:8000` for the API and `http://<LAN_IP>:8889` for WebRTC.
- **Local testing with RPi cameras:** The computer must be on **IAMS-Net** WiFi (password: `iamsthesis123`) since the RPi and cameras are on that network (192.168.88.x subnet).
- **Production:** The phone only needs **internet access** (any network). It connects to the VPS at `167.71.217.44`.
- **Firewall:** Make sure your computer's firewall allows incoming connections on ports 8000, 8554, 8887 (UDP), and 8889 for local testing.

---

## Database Seeding

### Local

```bash
docker compose exec api-gateway python -m scripts.seed_data
```

### Production

```bash
ssh root@167.71.217.44 "cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml exec api-gateway python -m scripts.seed_data"
```

### What Gets Seeded

| Data | Count |
|------|-------|
| Students | ~180 (from `docs/data/ListofStudents_All-thesis-purposes.md`) |
| Faculty | 5 |
| Admin | 1 (`admin@admin.com` / `123`) |
| Rooms | 2 (EB226, EB227) |
| Schedules | 42 (including 24/7 test schedules) |
| System settings | 7 |

### Faculty Logins (password: `password123`)

| Email | Room |
|-------|------|
| faculty.eb226@gmail.com | EB226 |
| faculty.eb227@gmail.com | EB227 |
| ryan.elumba@jrmsu.edu.ph | Both |
| maricon.gahisan@jrmsu.edu.ph | Both |
| troy.lasco@jrmsu.edu.ph | Both |

**WARNING:** Seeding wipes ALL existing data including face registrations and attendance records. Only seed when you want a clean slate.

---

## Testing the Full Pipeline Locally

### With Real Cameras (on IAMS-Net)

1. Your computer must be on **IAMS-Net** WiFi (password: `iamsthesis123`)
2. Start Docker Desktop: `docker compose up -d`
3. Point RPi relays to your computer's IP (see [Edge Device Configuration](#edge-device-raspberry-pi-configuration))
4. Update Android app to point to your computer's IP
5. Rebuild and run the app
6. Open the faculty live feed — you should see the camera stream

### Without Cameras (fake RTSP stream)

Use your webcam or a video file as a fake RTSP source:

```bash
# Webcam (macOS)
ffmpeg -f avfoundation -i "0" -c:v libx264 -f rtsp rtsp://localhost:8554/eb226

# Webcam (Windows)
ffmpeg -f dshow -i video="Integrated Camera" -c:v libx264 -f rtsp rtsp://localhost:8554/eb226

# Loop a video file (any platform)
ffmpeg -stream_loop -1 -re -i test_video.mp4 -c:v libx264 -f rtsp rtsp://localhost:8554/eb226
```

The backend will grab frames from this stream and process them through the face recognition pipeline.

### Verifying the Full Pipeline Locally

After starting everything, verify each component:

```bash
# 1. Backend is healthy
curl http://localhost:8000/api/v1/health

# 2. Check if RTSP stream is being published to mediamtx
curl -s -X POST "http://localhost:8889/eb226/whep" -H "Content-Type: application/sdp" -d "v=0"
# HTTP 400 = stream exists (good), HTTP 404 = no stream

# 3. Check FAISS status (face embeddings)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin@admin.com","password":"123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/v1/face/statistics -H "Authorization: Bearer $TOKEN"
# faiss_vectors should be > 0 if students have registered faces

# 4. Check active sessions
curl -s http://localhost:8000/api/v1/presence/sessions/active -H "Authorization: Bearer $TOKEN"
```

---

## Troubleshooting

### Black Screen on Live Feed

1. **Check if the RPi relay is pushing:**
   ```bash
   curl -s -X POST "http://<HOST>:8889/eb226/whep" -H "Content-Type: application/sdp" -d "v=0"
   ```
   - HTTP 400 = stream exists (good)
   - HTTP 404 = "no one is publishing" (RPi relay is down)

2. **Restart the RPi relay:**
   ```bash
   ssh iams-eb226@192.168.88.12  # password: 123
   sudo systemctl restart iams-relay
   tail -10 ~/iams-relay.log
   ```

3. **Check backend logs for FFmpeg errors:**
   ```bash
   # Local
   docker compose logs -f api-gateway | grep FFmpeg

   # Production
   ssh root@167.71.217.44 "cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml logs --since 5m api-gateway | grep FFmpeg"
   ```

### "0 Detected" / No Bounding Boxes

- **FAISS has 0 embeddings:** No students have registered their faces. Check:
  ```bash
  curl http://<HOST>/api/v1/face/statistics -H "Authorization: Bearer <token>"
  ```
  If `faiss_vectors: 0`, students need to register faces via the Android app.

- **Backend pipeline not running:** Check if sessions are active:
  ```bash
  curl http://<HOST>/api/v1/presence/sessions/active -H "Authorization: Bearer <token>"
  ```

### Android App Can't Connect

- Phone and backend must be on the **same network**
- Check `gradle.properties` has the correct IP and port
- Rebuild the app after changing `gradle.properties`
- Test backend reachability from the phone's browser: `http://<HOST>:<PORT>/api/v1/health`

### Database Reset

```bash
# Local — full wipe and reseed
docker compose exec api-gateway python -m scripts.seed_data

# Production — full wipe and reseed
ssh root@167.71.217.44 "cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml exec api-gateway python -m scripts.seed_data"
```

### RPi Relay Keeps Dying

The relay process may crash if:
- The camera goes to sleep or loses power
- The network between RPi and VPS/computer drops
- The RTSP URL is wrong in `~/iams-relay.env`

The systemd service auto-restarts, but check logs:
```bash
ssh iams-eb226@192.168.88.12  # password: 123
tail -30 ~/iams-relay.log
sudo systemctl status iams-relay
```

### Docker Container Name Conflicts

If you see `container name is already in use` errors:
```bash
# Remove the conflicting container
docker rm -f <container_name>

# Then restart
docker compose up -d
```

### CORS Errors in Admin Portal (Local)

The backend's CORS config in `backend/.env` must include your admin portal URL:
```env
CORS_ORIGINS=["https://iams-thesis.vercel.app","http://localhost:5173","http://localhost:3000"]
```

If you access the admin portal from a different URL, add it to the list.

### Port Reference

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| 8000 | api-gateway | HTTP | Backend API (local only, nginx proxies in prod) |
| 80 | nginx | HTTP | Reverse proxy (production only) |
| 5432 | postgres | TCP | Database |
| 6379 | redis | TCP | Cache |
| 8554 | mediamtx | RTSP/TCP | RTSP ingest from RPi |
| 8889 | mediamtx | HTTP | WHEP endpoint (WebRTC signaling) |
| 8887 | mediamtx | UDP | WebRTC media |
| 3478 | coturn | TCP/UDP | TURN server |
| 9997 | mediamtx | HTTP | mediamtx API (local only) |
| 9999 | dozzle | HTTP | Log viewer |
