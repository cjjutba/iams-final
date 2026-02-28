# IAMS Deployment Documentation

Complete documentation for deploying the Intelligent Attendance Monitoring System.

## Overview

This directory contains comprehensive deployment documentation for all IAMS components:
- Backend API (FastAPI)
- Edge Device (Raspberry Pi)
- Mobile Applications (React Native)

## Documentation Structure

### Quick Start

- **[Pilot Deployment Checklist](pilot-deployment-checklist.md)** - Step-by-step checklist for pilot testing deployment
- **[Troubleshooting Guide](troubleshooting-guide.md)** - Common issues and solutions

### Component-Specific Guides

- **[Edge Device Setup](edge-device-setup.md)** - Complete Raspberry Pi setup and configuration
- **[Mobile App Deployment](mobile-app-deployment.md)** - Building and distributing mobile apps

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Classroom WiFi Network                │
│                                                           │
│  ┌──────────────┐      ┌──────────────┐                 │
│  │ Raspberry Pi │──────│    Laptop    │                 │
│  │   (Camera)   │ HTTP │   (Backend)  │                 │
│  │  MediaPipe   │      │   FastAPI    │                 │
│  └──────────────┘      └──────┬───────┘                 │
│                               │                          │
│  ┌──────────────┐             │                          │
│  │ Student      │─────────────┘                          │
│  │ Mobile Apps  │ API + WebSocket                        │
│  └──────────────┘                                        │
│                                                           │
│  ┌──────────────┐                                        │
│  │ Faculty      │─────────────┐                          │
│  │ Mobile Apps  │ API + WebSocket                        │
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

## Deployment Scenarios

### Scenario 1: Pilot Testing (Recommended)

**Use Case:** Testing in 1-2 classrooms with 30-50 students

**Architecture:**
- Backend on laptop (same classroom)
- 1 Raspberry Pi camera
- Students/faculty use own phones
- Supabase cloud database

**Pros:**
- Quick setup (2-3 hours)
- No cloud server needed
- Easy to troubleshoot
- Low cost

**Cons:**
- Limited to same WiFi network
- Laptop must stay on during class
- Not suitable for production

**Guide:** Follow [Pilot Deployment Checklist](pilot-deployment-checklist.md)

### Scenario 2: Production Deployment (Future)

**Use Case:** Multiple classrooms across campus

**Architecture:**
- Backend on cloud VPS or campus server
- Multiple Raspberry Pi cameras (one per room)
- HTTPS/SSL enabled
- Automated backups and monitoring

**Pros:**
- Accessible from anywhere
- Professional deployment
- Scalable to many rooms
- Better reliability

**Cons:**
- Requires cloud server ($10-50/month)
- More complex setup
- SSL certificate needed
- More maintenance

**Guide:** See ../main/deployment.md for cloud deployment

## Quick Reference

### Backend Commands

```bash
# Start production backend
cd backend
./scripts/start_production.sh

# Stop backend
./scripts/stop_production.sh

# Health check
curl http://localhost:8000/api/v1/health

# Monitor system
./scripts/monitor.sh

# Backup
./scripts/backup.sh

# View logs
tail -f logs/app.log
```

### Edge Device Commands

```bash
# SSH to Raspberry Pi
ssh pi@<raspberry-pi-ip>

# Start edge device
sudo systemctl start iams-edge

# Stop edge device
sudo systemctl stop iams-edge

# Check status
sudo systemctl status iams-edge

# View logs
tail -f logs/edge.log

# Health check
./scripts/health_check.sh
```

### Mobile App Commands

```bash
# Build pilot APK
cd mobile
eas build --platform android --profile pilot

# Check build status
eas build:list

# Download APK
eas build:download --platform android --latest
```

## Environment Files

### Backend (.env.production)

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
DATABASE_URL=postgresql://postgres.xxx@aws-0-region.pooler.supabase.com:5432/postgres

# JWT
SECRET_KEY=<generate-strong-key>

# Production settings
DEBUG=false
CORS_ORIGINS=["*"]  # For pilot, restrict in production
```

### Edge Device (.env)

```env
# Backend (update with actual IP)
SERVER_URL=http://192.168.1.100:8000

# Camera
CAMERA_INDEX=0
FRAME_WIDTH=640
FRAME_HEIGHT=480

# Room (optional)
ROOM_ID=301
```

### Mobile App (eas.json)

```json
{
  "build": {
    "pilot": {
      "env": {
        "API_BASE_URL": "http://192.168.1.100:8000/api/v1",
        "WS_BASE_URL": "ws://192.168.1.100:8000/api/v1/ws"
      }
    }
  }
}
```

## Prerequisites Checklist

### Hardware

- [ ] Laptop with 8GB+ RAM, 4+ CPU cores
- [ ] Raspberry Pi 4B (4GB+ RAM)
- [ ] Camera Module v2 or USB webcam
- [ ] 32GB+ SD card (Class 10)
- [ ] WiFi network (2.4GHz or 5GHz)
- [ ] Power supplies for all devices

### Software

- [ ] Python 3.8+ installed
- [ ] Node.js 18+ and pnpm installed
- [ ] Supabase project created
- [ ] Expo account created
- [ ] Git installed

### Network

- [ ] Classroom WiFi SSID and password
- [ ] Backend laptop has static/predictable IP
- [ ] Firewall allows port 8000
- [ ] All devices can access internet
- [ ] Devices can ping each other

### Accounts

- [ ] Supabase account with project
- [ ] Expo account for building
- [ ] GitHub account (if using repository)

## Deployment Timeline

### Pilot Testing Deployment

| Phase | Duration | Activities |
|-------|----------|------------|
| Preparation | 2 hours | Setup Supabase, configure .env files, install dependencies |
| Backend Deploy | 30 min | Start backend, verify health, test connectivity |
| Edge Deploy | 45 min | Mount camera, configure WiFi, start service |
| Mobile Deploy | 30 min | Build APK, distribute to testers, initial testing |
| Integration Test | 30 min | End-to-end testing, face recognition, real-time updates |
| Documentation | 30 min | Document IPs, create support materials |
| **Total** | **4-5 hours** | First-time deployment |

### Subsequent Deployments

- Backend updates: 10-15 minutes
- Edge device updates: 15-20 minutes
- Mobile app updates: 30 minutes (rebuild time)

## Monitoring and Maintenance

### Daily Checks

- Backend running and accessible
- Edge device detecting faces
- Database connection healthy
- FAISS index loaded
- No critical errors in logs

### Weekly Maintenance

- Review logs for errors
- Check disk space
- Backup FAISS index
- Update documentation
- Gather user feedback

### Monthly Maintenance

- Update dependencies
- Review performance metrics
- Plan improvements
- Train new users
- Document lessons learned

## Support and Troubleshooting

### Common Issues

1. **Backend won't start**
   - Check .env file
   - Verify database connection
   - Check port 8000 available

2. **Edge device not detecting faces**
   - Check camera position
   - Verify camera working
   - Check detection threshold

3. **Mobile app can't connect**
   - Verify correct IP in build
   - Check same WiFi network
   - Test backend from browser

**Full troubleshooting:** [Troubleshooting Guide](troubleshooting-guide.md)

### Getting Help

**Documentation:**
- [Pilot Deployment Checklist](pilot-deployment-checklist.md)
- [Edge Device Setup](edge-device-setup.md)
- [Mobile App Deployment](mobile-app-deployment.md)
- [Troubleshooting Guide](troubleshooting-guide.md)

**Technical Support:**
- GitHub Issues: [Repository URL]
- Email: support@iams.jrmsu.edu.ph
- Emergency: [Phone number]

## Success Criteria

### Technical Metrics

- Backend uptime: 95%+ during class hours
- Face detection latency: < 2 seconds
- Face recognition accuracy: > 90%
- API response time: < 500ms
- Mobile app crash rate: < 1%

### User Experience

- Student registration: < 5 minutes
- Faculty dashboard responsive
- Real-time updates working
- Minimal support requests
- Positive user feedback

## Next Steps After Pilot

1. **Gather Feedback**
   - Survey students and faculty
   - Document issues encountered
   - Identify improvement areas

2. **Optimize System**
   - Fix bugs discovered
   - Improve performance
   - Enhance user experience

3. **Plan Production**
   - Evaluate cloud deployment
   - Plan multi-room rollout
   - Prepare training materials

4. **Scale Up**
   - Deploy to more classrooms
   - Add more edge devices
   - Onboard more users

## File Inventory

### Configuration Templates

- `backend/.env.production.example` - Production environment template
- `edge/.env.example` - Edge device configuration template
- `mobile/.env.production.example` - Mobile app configuration template
- `mobile/app.json` - Expo app configuration
- `mobile/eas.json` - EAS build configuration

### Scripts

**Backend:**
- `backend/run_production.py` - Production server runner
- `backend/scripts/validate_env.py` - Environment validator
- `backend/scripts/start_production.sh` - Start backend
- `backend/scripts/stop_production.sh` - Stop backend
- `backend/scripts/monitor.sh` - Health monitoring
- `backend/scripts/backup.sh` - Backup FAISS and config
- `backend/scripts/restore.sh` - Restore from backup

**Edge Device:**
- `edge/scripts/setup_rpi.sh` - Raspberry Pi setup automation
- `edge/scripts/wifi_setup.sh` - WiFi configuration helper
- `edge/scripts/health_check.sh` - Edge device health check
- `edge/scripts/validate_env.py` - Environment validator

### Systemd Services

- `backend/iams-backend.service` - Backend systemd service
- `edge/iams-edge.service` - Edge device systemd service

### Documentation

- `docs/deployment/README.md` - This file
- `docs/deployment/pilot-deployment-checklist.md` - Pilot deployment guide
- `docs/deployment/edge-device-setup.md` - Raspberry Pi setup guide
- `docs/deployment/mobile-app-deployment.md` - Mobile app build guide
- `docs/deployment/troubleshooting-guide.md` - Troubleshooting guide
- `docs/main/deployment.md` - General deployment overview

## License and Attribution

IAMS - Intelligent Attendance Monitoring System
Copyright (c) 2024 JRMSU

Built with:
- FastAPI (backend)
- React Native (mobile)
- MediaPipe (face detection)
- FaceNet (face recognition)
- Supabase (database)
- Expo (mobile deployment)
