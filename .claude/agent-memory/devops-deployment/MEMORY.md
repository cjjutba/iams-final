# DevOps Deployment Memory

## Key Deployment Architecture Decisions

### Two-Tier Pilot Testing Design
- **Backend:** Laptop on classroom WiFi (0.0.0.0:8000)
- **Edge Device:** Raspberry Pi on same network
- **Mobile:** APK distributed directly (no store deployment)
- **Database:** Supabase cloud (pooler connection required for IPv4)
- **Rationale:** Quick setup, no cloud costs, easy troubleshooting, suitable for MVP pilot

### Network Configuration Patterns
- Backend MUST bind to 0.0.0.0 (not 127.0.0.1) for network access
- Firewall MUST allow port 8000 inbound
- Supabase pooler URL required (direct connection is IPv6-only)
- CORS wildcard ["*"] acceptable for pilot (restrict in production)
- Same WiFi network required for all devices (check for AP isolation)

## Critical File Paths

### Backend Production Files
- `backend/.env.production.example` - Production config template
- `backend/run_production.py` - Multi-worker uvicorn launcher
- `backend/scripts/validate_env.py` - Pre-flight environment checker
- `backend/scripts/start_production.sh` - Automated startup with checks
- `backend/scripts/monitor.sh` - Health monitoring script
- `backend/scripts/backup.sh` - FAISS + config backup
- `backend/iams-backend.service` - Systemd service definition

### Edge Device Files
- `edge/.env.example` - Edge configuration template
- `edge/scripts/setup_rpi.sh` - Automated Raspberry Pi setup
- `edge/scripts/wifi_setup.sh` - WiFi configuration helper
- `edge/scripts/health_check.sh` - Edge device monitoring
- `edge/iams-edge.service` - Systemd service for auto-start

### Mobile Deployment Files
- `mobile/app.json` - Expo configuration (bundle ID: com.jrmsu.iams)
- `mobile/eas.json` - Build profiles (development/preview/pilot/production)
- `mobile/.env.production.example` - Mobile environment template

## Environment Variable Patterns

### Backend Critical Variables
```env
SUPABASE_URL=https://xxx.supabase.co
DATABASE_URL=postgresql://postgres.xxx@aws-0-region.pooler.supabase.com:5432/postgres  # POOLER required
SECRET_KEY=<32+ char random>  # Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
DEBUG=false  # MUST be false in production
CORS_ORIGINS=["*"]  # Wildcard OK for pilot, restrict for production
```

### Edge Device Critical Variables
```env
SERVER_URL=http://192.168.1.100:8000  # Backend IP (find with ipconfig/ifconfig)
CAMERA_INDEX=0  # Usually 0, check with ls /dev/video*
ROOM_ID=301  # Optional, links detections to specific room
```

### Mobile Build Configuration
```json
// eas.json pilot profile
"env": {
  "API_BASE_URL": "http://192.168.1.100:8000/api/v1",  // Backend IP
  "WS_BASE_URL": "ws://192.168.1.100:8000/api/v1/ws"   // WebSocket URL
}
```

## Deployment Scripts Best Practices

### Environment Validation First
- ALWAYS run `validate_env.py` before starting services
- Catches misconfiguration early (wrong URLs, missing secrets, permission issues)
- Exit with status 1 on failure to prevent bad deployments

### Production Startup Sequence
1. Load .env.production (or fallback to .env)
2. Run environment validation
3. Check DEBUG=false (warn if true)
4. Calculate workers: (2 × CPU cores) + 1
5. Start uvicorn with: host="0.0.0.0", reload=False, workers=calculated

### Monitoring Script Features
- Check API health endpoint (/api/v1/health)
- Verify process running (pgrep uvicorn)
- Check CPU/memory/disk usage (alert thresholds: 80%, 80%, 85%)
- Parse recent logs for errors
- Test database connectivity
- Verify FAISS index exists
- Log all checks to monitor.log with timestamps

### Backup Strategy
- **FAISS Index:** Daily backup, 7-day retention, compressed with gzip
- **Database:** Supabase auto-backup (manual export via dashboard)
- **Config Files:** tar.gz of .env, alembic.ini
- **Uploads:** tar.gz of data/uploads directory
- Cleanup old backups automatically (find -mtime +7)

## Common Deployment Issues & Solutions

### Backend Won't Start
1. **Port 8000 in use:** `lsof -i :8000` → `kill -9 <PID>`
2. **Database connection failed:** Check using POOLER URL, not direct
3. **Permission denied:** `mkdir -p logs data/faiss data/uploads && chmod 755`
4. **Module not found:** Virtual environment not activated

### Edge Device Issues
1. **Camera not detected:** Add user to video group: `sudo usermod -a -G video pi`
2. **Backend unreachable:** Check firewall, verify same network, test with curl
3. **Queue filling up:** Backend down or overloaded, check connectivity
4. **High CPU:** Reduce FRAME_RATE or increase FRAME_SKIP

### Mobile App Issues
1. **Can't connect:** Wrong IP in EAS build, rebuild required
2. **Login fails:** Check backend logs, verify user exists in database
3. **WebSocket not connecting:** Check WS_BASE_URL uses ws:// (not http://)
4. **Face registration fails:** Camera permission denied, reinstall app

## Raspberry Pi Optimization

### Camera Positioning
- Height: 2.0-2.5 meters
- Angle: 15-30° downward tilt
- Distance: Captures faces at 1-3 meters
- Coverage: 3-5 meter radius
- Avoid direct sunlight and backlighting

### Performance Tuning
- **RPi 3B+:** 320x240 @ 5 FPS, FRAME_SKIP=2
- **RPi 4B:** 640x480 @ 10 FPS, FRAME_SKIP=1
- **RPi 5:** 640x480 @ 15 FPS, FRAME_SKIP=1
- Monitor temperature: < 70°C OK, > 80°C critical
- Add heatsink/fan if consistently > 75°C

## Mobile App Build Profiles

### Pilot Profile (Recommended for Testing)
- **Build type:** APK (direct install)
- **Distribution:** Internal (no store)
- **Backend:** Local IP (http://192.168.1.100:8000)
- **Build command:** `eas build -p android --profile pilot`
- **Build time:** 10-20 minutes on Expo servers

### Production Profile
- **Build type:** AAB (Play Store) or IPA (App Store)
- **Distribution:** Public stores
- **Backend:** HTTPS domain (https://api.yourdomain.com)
- **Requires:** Store accounts, certificates, store listing

## Systemd Service Configuration

### Backend Service Key Settings
```ini
[Service]
User=iams  # Dedicated user, NOT root
WorkingDirectory=/opt/iams/backend
ExecStart=/opt/iams/backend/venv/bin/python run_production.py
Restart=always
RestartSec=10
MemoryLimit=2G  # Prevent runaway memory usage
ReadWritePaths=/opt/iams/backend/data /opt/iams/backend/logs
```

### Edge Device Service Key Settings
```ini
[Service]
User=pi
SupplementaryGroups=video  # Camera access
MemoryLimit=512M  # Conservative for RPi
CPUQuota=80%  # Leave headroom
Restart=always
RestartSec=5  # Quick restart for reliability
```

## Monitoring Thresholds

### Backend Alerts
- CPU > 80% sustained: Scale up workers or add resources
- Memory > 80%: Reduce workers, check for leaks
- Disk > 85%: Clean old logs, backups
- Error rate > 5 per 100 requests: Investigate logs

### Edge Device Alerts
- CPU > 70%: Reduce frame rate or resolution
- Temperature > 80°C: Improve cooling
- Queue > 100 items: Backend connectivity issue
- Consecutive errors > 10: Restart service

## Deployment Timeline

### First-Time Pilot (4-5 hours)
1. Preparation: 2 hours (Supabase setup, .env config, dependencies)
2. Backend deploy: 30 minutes (start, verify, test)
3. Edge deploy: 45 minutes (mount camera, configure, test)
4. Mobile deploy: 30 minutes (build APK, distribute, test)
5. Integration test: 30 minutes (end-to-end flows)
6. Documentation: 30 minutes (record IPs, create support docs)

### Subsequent Updates
- Backend: 10-15 minutes (pull, restart, verify)
- Edge: 15-20 minutes (update code, restart, test)
- Mobile: 30 minutes (rebuild time, no redistribution time)

## Documentation Files Created

### Deployment Guides
- `docs/deployment/README.md` - Central deployment hub
- `docs/deployment/pilot-deployment-checklist.md` - Step-by-step pilot guide
- `docs/deployment/edge-device-setup.md` - Complete RPi setup
- `docs/deployment/mobile-app-deployment.md` - Mobile build guide
- `docs/deployment/troubleshooting-guide.md` - Common issues & solutions

### Reference: [Link to deployment-patterns.md]

All scripts are executable and production-ready for pilot testing.
