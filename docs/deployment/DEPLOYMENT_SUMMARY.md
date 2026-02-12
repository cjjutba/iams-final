# IAMS Deployment Preparation - Summary

**Status:** ✓ COMPLETE
**Date:** February 7, 2026
**Prepared By:** DevOps Deployment Specialist

## Executive Summary

Complete production deployment infrastructure has been prepared for the IAMS (Intelligent Attendance Monitoring System) pilot testing. All necessary scripts, configuration templates, systemd services, and documentation are production-ready.

## Deliverables Overview

### 1. Configuration Templates (5 files)

✓ **Backend Production Environment**
- `backend/.env.production.example` - Production configuration with security notes
- Includes: Supabase, JWT, CORS, FAISS, logging settings
- Security: Strong SECRET_KEY generation, DEBUG=false enforcement

✓ **Edge Device Configuration**
- `edge/.env.example` - Raspberry Pi configuration
- Includes: Backend URL, camera settings, queue policy, room mapping

✓ **Mobile App Configuration**
- `mobile/.env.production.example` - Mobile app environment
- `mobile/app.json` - Updated with bundle IDs, permissions
- `mobile/eas.json` - Build profiles (development/preview/pilot/production)

### 2. Production Scripts (13 files)

#### Backend Scripts (7 files)

✓ **Production Server Management**
- `backend/run_production.py` - Multi-worker production server
  - Auto-calculates workers: (2 × CPU) + 1
  - Environment validation before start
  - Debug mode warning system

- `backend/scripts/start_production.sh` - Automated startup
  - Pre-flight checks (env, dependencies, database)
  - Directory creation
  - Health verification

- `backend/scripts/stop_production.sh` - Graceful shutdown
  - SIGTERM → SIGKILL escalation
  - Systemd service support

✓ **Environment Validation**
- `backend/scripts/validate_env.py` - Comprehensive validation
  - Required variables check
  - URL format validation
  - Database connection testing
  - Path verification
  - Numeric settings validation

✓ **Monitoring & Health**
- `backend/scripts/monitor.sh` - System health monitoring
  - API health endpoint check
  - Process status verification
  - CPU/memory/disk usage (alert thresholds)
  - Log error scanning
  - Database connection pool check
  - FAISS index status
  - Network connectivity test

✓ **Backup & Recovery**
- `backend/scripts/backup.sh` - Automated backup
  - FAISS index (compressed with gzip)
  - Configuration files (tar.gz)
  - Uploaded files
  - 7-day retention policy

- `backend/scripts/restore.sh` - Interactive restore
  - Timestamp-based restoration
  - Safety confirmations
  - Pre-restore backups
  - Service restart handling

#### Edge Device Scripts (6 files)

✓ **Raspberry Pi Setup**
- `edge/scripts/setup_rpi.sh` - Complete RPi automation
  - System update and dependencies
  - Camera setup and testing
  - Python environment creation
  - WiFi configuration
  - Systemd service installation

✓ **Network Configuration**
- `edge/scripts/wifi_setup.sh` - WiFi helper
  - Network scanning
  - raspi-config integration
  - Manual wpa_supplicant editing
  - Connection verification
  - Backend connectivity testing

✓ **Monitoring**
- `edge/scripts/health_check.sh` - Edge device health
  - Process status
  - Camera access verification
  - Network connectivity
  - Backend reachability
  - Disk/memory usage
  - CPU temperature monitoring
  - Recent log error scanning

✓ **Environment Validation**
- `edge/scripts/validate_env.py` - Pre-flight checks
  - Python version verification
  - Platform detection
  - Camera availability
  - Server URL validation
  - Numeric settings validation

### 3. Systemd Services (2 files)

✓ **Backend Service**
- `backend/iams-backend.service`
- Features: Auto-restart, resource limits, security hardening
- Logging: Separate stdout/stderr logs

✓ **Edge Device Service**
- `edge/iams-edge.service`
- Features: Aggressive restart policy, camera access, memory limits
- Optimized for Raspberry Pi constraints

### 4. Comprehensive Documentation (5 files)

✓ **Central Hub**
- `docs/deployment/README.md` (650+ lines)
- Complete overview, quick reference, prerequisites
- Deployment scenarios, timeline, success criteria

✓ **Pilot Deployment Guide**
- `docs/deployment/pilot-deployment-checklist.md` (500+ lines)
- Step-by-step checklist for pilot testing
- Pre-deployment, deployment day, post-deployment phases
- Daily operations checklist
- Success criteria and rollback procedures

✓ **Edge Device Guide**
- `docs/deployment/edge-device-setup.md` (600+ lines)
- Hardware requirements and setup
- Quick automated setup vs manual setup
- Camera positioning guidelines
- Network configuration
- Performance tuning
- Troubleshooting section

✓ **Mobile App Guide**
- `docs/deployment/mobile-app-deployment.md` (700+ lines)
- Build profiles (development/preview/pilot/production)
- Android deployment (APK for pilot, AAB for store)
- iOS deployment (TestFlight, App Store)
- OTA updates configuration
- Environment configuration
- Testing checklist

✓ **Troubleshooting Guide**
- `docs/deployment/troubleshooting-guide.md` (800+ lines)
- Backend issues (won't start, not accessible, database, FAISS)
- Edge device issues (won't start, no detections, queue, CPU)
- Mobile app issues (connection, login, face registration, WebSocket)
- Database issues (migrations, performance)
- Network issues (connectivity, intermittent)
- Performance issues (slow recognition, high memory)
- Emergency procedures

## Architecture Overview

### Pilot Testing Deployment

```
┌─────────────────────────────────────────────────────────┐
│                    Classroom WiFi Network                │
│                                                           │
│  ┌──────────────┐                                        │
│  │ Raspberry Pi │──────┐                                 │
│  │   (Camera)   │ HTTP │                                 │
│  │  MediaPipe   │      │                                 │
│  └──────────────┘      │                                 │
│                        ▼                                  │
│                 ┌──────────────┐                         │
│                 │    Laptop    │                         │
│                 │   (Backend)  │                         │
│                 │   FastAPI    │                         │
│                 └──────┬───────┘                         │
│                        │                                  │
│  ┌──────────────┐      │                                 │
│  │ Student      │──────┤                                 │
│  │ Mobile Apps  │      │ API + WebSocket                 │
│  └──────────────┘      │                                 │
│                        │                                  │
│  ┌──────────────┐      │                                 │
│  │ Faculty      │──────┘                                 │
│  │ Mobile Apps  │                                        │
│  └──────────────┘                                        │
│                                                           │
└─────────────────────────────────────────────────────────┘
                        │
                        │ Internet
                        ▼
                ┌────────────────┐
                │    Supabase    │
                │  (PostgreSQL)  │
                └────────────────┘
```

## Deployment Workflow

### Phase 1: Backend Deployment (30 minutes)

1. Configure `.env.production`
2. Run `python scripts/validate_env.py`
3. Execute `./scripts/start_production.sh`
4. Verify health: `curl http://localhost:8000/api/v1/health`
5. Test from network: `curl http://<ip>:8000/api/v1/health`

### Phase 2: Edge Device Deployment (45 minutes)

1. Run `./scripts/setup_rpi.sh` (automated)
2. Configure WiFi: `./scripts/wifi_setup.sh`
3. Update `.env` with backend IP
4. Run `python scripts/validate_env.py`
5. Start service: `sudo systemctl start iams-edge`
6. Verify: `./scripts/health_check.sh`

### Phase 3: Mobile App Deployment (30 minutes)

1. Update `eas.json` with backend IP
2. Build APK: `eas build -p android --profile pilot`
3. Distribute APK to testers
4. Test connectivity and core features

### Phase 4: Integration Testing (30 minutes)

1. Register test student face
2. Trigger face recognition
3. Verify attendance record created
4. Check real-time updates (WebSocket)
5. Test early leave detection
6. Verify offline queue handling

## Key Features

### Security
- Strong SECRET_KEY generation guidance
- DEBUG=false enforcement in production
- Non-root user execution (systemd)
- Read-write path restrictions
- CORS configuration guidance

### Reliability
- Auto-restart policies (systemd)
- Resource limits (memory, CPU)
- Health check endpoints
- Graceful shutdown handling
- Backup and restore procedures

### Monitoring
- Comprehensive health checks
- Log error scanning
- Resource usage tracking
- Alert thresholds
- Temperature monitoring (RPi)

### Operational
- Environment validation before start
- Pre-flight checks
- Interactive restore process
- Safety confirmations
- Rollback procedures

## Technical Specifications

### Backend
- **Server:** Uvicorn with multiple workers
- **Workers:** Auto-calculated (2 × CPU + 1)
- **Port:** 8000 (configurable)
- **Logs:** Rotating file logs (10MB, 5 backups)
- **Resource Limits:** 2GB memory (systemd)

### Edge Device
- **Platform:** Raspberry Pi OS (Bullseye+)
- **Camera:** CSI Module v2 or USB webcam
- **Resolution:** 640x480 @ 10 FPS (configurable)
- **Queue:** 500 items max, 5-minute TTL
- **Resource Limits:** 512MB memory, 80% CPU quota

### Mobile App
- **Framework:** React Native + Expo
- **Build System:** EAS (Expo Application Services)
- **Profiles:** development, preview, pilot, production
- **Distribution:** APK (pilot), AAB/IPA (production)

## Success Criteria

### Technical Metrics
- Backend uptime: 95%+ during class hours
- Face detection latency: < 2 seconds
- Face recognition accuracy: > 90%
- API response time: < 500ms
- Mobile app crash rate: < 1%

### Operational Metrics
- Setup time (first deployment): 4-5 hours
- Update time (subsequent): 15-30 minutes
- Recovery time (from backup): < 10 minutes
- Support requests: < 5 per day

### User Experience
- Student registration: < 5 minutes
- Faculty dashboard: Responsive and real-time
- System stability: No manual intervention needed
- User satisfaction: Positive feedback

## Next Steps

### Immediate (Pre-Pilot)
1. Create Supabase project and run migrations
2. Configure all .env files with actual values
3. Test backend startup on deployment laptop
4. Setup Raspberry Pi with automated script
5. Build pilot APK with correct backend IP

### Pilot Testing (Week 1)
1. Deploy in single classroom
2. Onboard 30-50 students
3. Train 2-3 faculty members
4. Monitor system stability
5. Document issues and feedback

### Post-Pilot (Week 2+)
1. Analyze metrics and feedback
2. Fix critical bugs
3. Optimize performance
4. Prepare for multi-room rollout
5. Plan production cloud deployment

## File Locations Reference

### Configuration Templates
```
backend/.env.production.example
edge/.env.example
mobile/.env.production.example
mobile/app.json
mobile/eas.json
```

### Backend Scripts
```
backend/run_production.py
backend/scripts/validate_env.py
backend/scripts/start_production.sh
backend/scripts/stop_production.sh
backend/scripts/monitor.sh
backend/scripts/backup.sh
backend/scripts/restore.sh
```

### Edge Scripts
```
edge/scripts/setup_rpi.sh
edge/scripts/wifi_setup.sh
edge/scripts/health_check.sh
edge/scripts/validate_env.py
```

### Systemd Services
```
backend/iams-backend.service
edge/iams-edge.service
```

### Documentation
```
docs/deployment/README.md
docs/deployment/pilot-deployment-checklist.md
docs/deployment/edge-device-setup.md
docs/deployment/mobile-app-deployment.md
docs/deployment/troubleshooting-guide.md
```

## Support Resources

### Documentation
- Quick Start: `docs/deployment/README.md`
- Pilot Guide: `docs/deployment/pilot-deployment-checklist.md`
- Troubleshooting: `docs/deployment/troubleshooting-guide.md`

### Commands Reference
```bash
# Backend
./scripts/start_production.sh
./scripts/stop_production.sh
./scripts/monitor.sh
./scripts/backup.sh

# Edge Device
./scripts/setup_rpi.sh
./scripts/health_check.sh
sudo systemctl status iams-edge

# Mobile
eas build -p android --profile pilot
eas build:list
```

## Conclusion

All deployment infrastructure is production-ready for pilot testing. The system is designed for:

- **Quick Setup:** 4-5 hours for first deployment
- **Reliability:** Auto-restart, health monitoring, backups
- **Operability:** Clear documentation, troubleshooting guides
- **Scalability:** Ready to expand from pilot to production

The deployment approach prioritizes simplicity for pilot testing while maintaining professional standards for monitoring, backup, and recovery.

**Status: READY FOR PILOT DEPLOYMENT** ✓
