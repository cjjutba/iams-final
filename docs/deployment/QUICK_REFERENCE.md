# IAMS Deployment Quick Reference Card

Print this for quick access during deployment.

## Network Configuration

**Find Backend IP:**
```bash
# Windows
ipconfig

# Linux/Mac
hostname -I
```

**Backend IP:** _________________ (fill in)

**Edge Device IP:** _________________ (fill in)

**WiFi SSID:** _________________ (fill in)

## Essential Commands

### Backend

```bash
# Start
cd backend
./scripts/start_production.sh

# Stop
./scripts/stop_production.sh

# Health Check
curl http://localhost:8000/api/v1/health

# Monitor
./scripts/monitor.sh

# Backup
./scripts/backup.sh

# View Logs
tail -f logs/app.log

# Validate Config
python scripts/validate_env.py
```

### Edge Device

```bash
# SSH
ssh pi@<edge-ip>

# Start
sudo systemctl start iams-edge

# Stop
sudo systemctl stop iams-edge

# Status
sudo systemctl status iams-edge

# Health Check
./scripts/health_check.sh

# View Logs
tail -f logs/edge.log

# Validate Config
python scripts/validate_env.py
```

### Mobile App

```bash
# Build Pilot APK
cd mobile
eas build -p android --profile pilot

# Check Build Status
eas build:list

# Download APK
eas build:download --platform android --latest
```

## Troubleshooting

### Backend Not Starting
```bash
# Check port
lsof -i :8000

# Kill process
kill -9 <PID>

# Check environment
python scripts/validate_env.py

# Check logs
tail -50 logs/app.log
```

### Backend Not Accessible from Network
```bash
# Windows Firewall
netsh advfirewall firewall add rule name="IAMS" dir=in action=allow protocol=TCP localport=8000

# Linux Firewall
sudo ufw allow 8000/tcp
```

### Edge Device Not Detecting
```bash
# Check camera
ls -l /dev/video*

# Test camera
libcamera-hello

# Check logs
tail -f logs/edge.log

# Restart service
sudo systemctl restart iams-edge
```

### Mobile App Can't Connect
1. Verify same WiFi network
2. Test in browser: http://<backend-ip>:8000/api/v1/health
3. Check backend firewall
4. Verify correct IP in APK build

## Configuration Files

### Backend (.env.production)
```env
SUPABASE_URL=https://xxx.supabase.co
DATABASE_URL=postgresql://...pooler.supabase.com:5432/postgres
SECRET_KEY=<32+ char random>
DEBUG=false
CORS_ORIGINS=["*"]
```

### Edge (.env)
```env
SERVER_URL=http://<backend-ip>:8000
CAMERA_INDEX=0
ROOM_ID=301
```

### Mobile (eas.json pilot profile)
```json
"env": {
  "API_BASE_URL": "http://<backend-ip>:8000/api/v1",
  "WS_BASE_URL": "ws://<backend-ip>:8000/api/v1/ws"
}
```

## Health Check URLs

**Backend Health:**
```
http://<backend-ip>:8000/api/v1/health
```

**Backend Docs:**
```
http://<backend-ip>:8000/api/v1/docs
```

## Emergency Procedures

### Complete Restart
```bash
# 1. Stop everything
./scripts/stop_production.sh
ssh pi@<edge-ip> "sudo systemctl stop iams-edge"

# 2. Backup current state
./scripts/backup.sh

# 3. Restart
./scripts/start_production.sh
ssh pi@<edge-ip> "sudo systemctl start iams-edge"

# 4. Verify
curl http://localhost:8000/api/v1/health
./scripts/monitor.sh
```

### Restore from Backup
```bash
# List backups
ls -lh backups/

# Restore (replace TIMESTAMP)
./scripts/restore.sh TIMESTAMP
```

## Daily Checklist

**Morning:**
- [ ] Check backend running
- [ ] Check edge device running
- [ ] Test face recognition
- [ ] Verify schedules loaded

**During Operation:**
- [ ] Monitor logs for errors
- [ ] Check queue status (edge device)
- [ ] Verify attendance records creating
- [ ] Respond to user issues

**Evening:**
- [ ] Backup FAISS index
- [ ] Review error logs
- [ ] Document issues
- [ ] Plan fixes

## Contact Information

**Technical Lead:** _________________

**Phone:** _________________

**Email:** _________________

## Status Indicators

**Backend Healthy:**
```json
{
  "status": "healthy",
  "database": "connected",
  "faiss": "loaded"
}
```

**Edge Device Healthy:**
- Process running: ✓
- Camera accessible: ✓
- Backend reachable: ✓
- Queue empty or low: ✓
- Temperature < 70°C: ✓

**Mobile App Working:**
- Connects to backend: ✓
- Login successful: ✓
- Schedules display: ✓
- WebSocket connected: ✓
- Face registration works: ✓

## File Locations

**Backend:**
- Code: `/opt/iams/backend` or `./backend`
- Logs: `logs/app.log`
- FAISS: `data/faiss/faces.index`
- Backups: `backups/`

**Edge Device:**
- Code: `/home/pi/iams-edge`
- Logs: `logs/edge.log`
- Config: `.env`

**Documentation:**
- Main guide: `docs/deployment/README.md`
- Checklist: `docs/deployment/pilot-deployment-checklist.md`
- Troubleshooting: `docs/deployment/troubleshooting-guide.md`

---

**Keep this card accessible during deployment!**
