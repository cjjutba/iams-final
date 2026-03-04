# IAMS Pilot Deployment Checklist

Complete checklist for deploying IAMS for pilot testing in classroom.

## Pre-Deployment Checklist

### Infrastructure Preparation

- [ ] **Laptop/Server for Backend**
  - [ ] Windows 11 or Linux with Python 3.8+
  - [ ] At least 8GB RAM, 4+ CPU cores
  - [ ] 50GB+ free disk space
  - [ ] WiFi adapter working
  - [ ] Connected to classroom WiFi network

- [ ] **Raspberry Pi for Edge Device**
  - [ ] Raspberry Pi 4B (4GB+ RAM) with Raspberry Pi OS
  - [ ] Camera Module v2 or USB webcam
  - [ ] 32GB+ SD card (Class 10)
  - [ ] Power supply (5V/3A)
  - [ ] Case with cooling
  - [ ] Connected to classroom WiFi network

- [ ] **Network Configuration**
  - [ ] Classroom WiFi SSID and password
  - [ ] Backend laptop has static or predictable IP
  - [ ] Firewall allows port 8000 on backend
  - [ ] All devices can ping each other
  - [ ] Internet connection available (for Supabase)

- [ ] **Supabase Setup**
  - [ ] Supabase project created
  - [ ] Database schema migrated
  - [ ] Seed data loaded (test users)
  - [ ] SUPABASE_URL and keys available
  - [ ] Connection tested from backend

### Software Preparation

- [ ] **Backend Code**
  - [ ] Latest code pulled from repository
  - [ ] Virtual environment created
  - [ ] Dependencies installed (`pip install -r requirements.txt`)
  - [ ] .env.production configured
  - [ ] Environment validation passed
  - [ ] All 148 tests passing
  - [ ] Database migrations applied

- [ ] **Edge Device Code**
  - [ ] Code deployed to Raspberry Pi
  - [ ] Virtual environment created
  - [ ] Dependencies installed
  - [ ] .env configured with backend IP
  - [ ] Camera tested and working
  - [ ] Environment validation passed

- [ ] **Mobile App Build**
  - [ ] eas.json configured with backend IP
  - [ ] APK built successfully
  - [ ] APK tested on test device
  - [ ] Backend connectivity verified
  - [ ] All core features tested

### Documentation & Training

- [ ] **Deployment Documentation**
  - [ ] Printed deployment guide
  - [ ] Network diagram with IPs documented
  - [ ] Troubleshooting guide accessible
  - [ ] Emergency contact information

- [ ] **User Training**
  - [ ] Faculty trained on mobile app usage
  - [ ] Students briefed on face registration
  - [ ] System demonstration completed
  - [ ] Q&A session conducted

## Deployment Day Checklist

### Phase 1: Backend Deployment (30 minutes)

- [ ] **Environment Setup**
  - [ ] Connect laptop to classroom WiFi
  - [ ] Verify IP address (write it down: _____________)
  - [ ] Navigate to backend directory
  - [ ] Activate virtual environment

- [ ] **Configuration Verification**
  - [ ] Run: `python scripts/validate_env.py`
  - [ ] All validations pass
  - [ ] .env.production has correct values
  - [ ] DATABASE_URL points to Supabase pooler

- [ ] **Start Backend**
  - [ ] Create logs directory if missing
  - [ ] Run: `./scripts/start_production.sh`
  - [ ] Backend starts without errors
  - [ ] Health check passes: `curl http://localhost:8000/api/v1/health`
  - [ ] Swagger docs accessible: `http://localhost:8000/api/v1/docs`

- [ ] **Network Testing**
  - [ ] Test from another device: `curl http://<backend-ip>:8000/api/v1/health`
  - [ ] Browser access works from mobile device
  - [ ] CORS configured correctly
  - [ ] WebSocket endpoint accessible

### Phase 2: Edge Device Deployment (45 minutes)

- [ ] **Physical Setup**
  - [ ] Mount Raspberry Pi at optimal position (2-2.5m height)
  - [ ] Angle camera 15-30° downward
  - [ ] Secure power cable
  - [ ] Verify camera has clear view of entry area
  - [ ] Test coverage by walking through detection zone

- [ ] **Network Configuration**
  - [ ] SSH into Raspberry Pi
  - [ ] Verify WiFi connection: `iwconfig`
  - [ ] Test ping to backend: `ping <backend-ip>`
  - [ ] Test backend API: `curl http://<backend-ip>:8000/api/v1/health`

- [ ] **Update Configuration**
  - [ ] Edit .env file: `nano /home/pi/iams-edge/.env`
  - [ ] Set SERVER_URL to backend IP
  - [ ] Set ROOM_ID (if applicable)
  - [ ] Save and exit

- [ ] **Validation and Start**
  - [ ] Run: `python scripts/validate_env.py`
  - [ ] All validations pass
  - [ ] Camera detected
  - [ ] Test camera: `libcamera-hello`
  - [ ] Start edge device: `sudo systemctl start iams-edge`
  - [ ] Check status: `sudo systemctl status iams-edge`
  - [ ] Monitor logs: `tail -f logs/edge.log`

- [ ] **Functional Testing**
  - [ ] Face detection triggers (stand in front of camera)
  - [ ] Backend receives detection requests (check backend logs)
  - [ ] No error messages in edge logs
  - [ ] Queue remains empty (indicates good connectivity)

### Phase 3: Mobile App Distribution (30 minutes)

- [ ] **APK Distribution**
  - [ ] Copy APK to shared drive or USB
  - [ ] Provide installation instructions to users
  - [ ] Help users enable "Install from unknown sources"
  - [ ] Users install APK successfully

- [ ] **Initial Setup Testing**
  - [ ] Users connect to classroom WiFi
  - [ ] App opens without crashing
  - [ ] Login screen displays
  - [ ] Users can reach login endpoint

- [ ] **Student Testing (2-3 test students)**
  - [ ] Student registers account
  - [ ] Email verification (if enabled)
  - [ ] Login successful
  - [ ] Schedule displays correctly
  - [ ] Face registration flow works
  - [ ] 3-5 face images captured successfully
  - [ ] Face embeddings created in backend
  - [ ] FAISS index updated

- [ ] **Faculty Testing (1-2 test faculty)**
  - [ ] Faculty logs in with pre-seeded account
  - [ ] Home screen displays
  - [ ] Schedule shows their classes
  - [ ] Student list displays for their class
  - [ ] Live attendance screen works
  - [ ] WebSocket connection established
  - [ ] Real-time updates received

### Phase 4: Integration Testing (30 minutes)

- [ ] **End-to-End Face Recognition**
  - [ ] Registered student stands in front of camera
  - [ ] Face detected by edge device
  - [ ] Face sent to backend
  - [ ] Face recognized by FAISS
  - [ ] Attendance record created
  - [ ] Faculty app receives notification (WebSocket)
  - [ ] Student app updates attendance status

- [ ] **Continuous Presence Tracking**
  - [ ] Schedule is active (during class time)
  - [ ] Presence scan runs every 60 seconds
  - [ ] Student detected multiple times
  - [ ] Presence logs created
  - [ ] Presence score calculated

- [ ] **Early Leave Detection**
  - [ ] Student leaves detection zone
  - [ ] 3 consecutive scans miss student
  - [ ] Early leave event created
  - [ ] Faculty receives alert
  - [ ] Event logs correctly

- [ ] **Error Handling**
  - [ ] Disconnect backend (test offline queue)
  - [ ] Edge device queues detections
  - [ ] Reconnect backend
  - [ ] Queued detections processed
  - [ ] No data loss

## Post-Deployment Checklist

### Monitoring Setup

- [ ] **Backend Monitoring**
  - [ ] Setup cron job for health monitoring
  - [ ] Test: `./scripts/monitor.sh`
  - [ ] Configure alert thresholds
  - [ ] Document log locations

- [ ] **Edge Device Monitoring**
  - [ ] Test health check: `./scripts/health_check.sh`
  - [ ] Setup auto-restart on failure
  - [ ] Configure log rotation
  - [ ] Document troubleshooting steps

- [ ] **Mobile App Monitoring**
  - [ ] Verify error reporting works
  - [ ] Check Expo dashboard for crashes
  - [ ] Monitor user feedback channels

### Backup Setup

- [ ] **Backend Backups**
  - [ ] Test backup script: `./scripts/backup.sh`
  - [ ] Schedule daily backups (cron)
  - [ ] Verify backup location accessible
  - [ ] Document retention policy

- [ ] **FAISS Index Backups**
  - [ ] Manual backup created
  - [ ] Backup location documented
  - [ ] Test restore procedure

- [ ] **Database Backups**
  - [ ] Verify Supabase auto-backup enabled
  - [ ] Document manual backup procedure
  - [ ] Test restore procedure (non-production data)

### Documentation

- [ ] **System Documentation**
  - [ ] Network diagram updated with actual IPs
  - [ ] Backend URL documented
  - [ ] Edge device IP documented
  - [ ] Room ID mappings documented

- [ ] **User Documentation**
  - [ ] Quick start guide for students
  - [ ] Quick start guide for faculty
  - [ ] FAQ document created
  - [ ] Support contact information provided

- [ ] **Operational Documentation**
  - [ ] Daily checklist created
  - [ ] Incident response plan documented
  - [ ] Escalation contacts listed
  - [ ] Maintenance schedule documented

## Pilot Operation Checklist (Daily)

### Morning Startup

- [ ] Check backend is running
- [ ] Check edge device is running
- [ ] Verify camera feed working
- [ ] Test face recognition with known user
- [ ] Check schedules for the day

### During Operation

- [ ] Monitor backend logs for errors
- [ ] Check edge device queue status
- [ ] Verify attendance records being created
- [ ] Respond to user issues promptly
- [ ] Document any issues or bugs

### Evening Shutdown (if applicable)

- [ ] Backup FAISS index
- [ ] Check logs for errors
- [ ] Document day's observations
- [ ] Note any system improvements needed
- [ ] Plan fixes for next day

## Success Criteria

### Technical Success

- [ ] 95%+ uptime during class hours
- [ ] Face detection latency < 2 seconds
- [ ] Face recognition accuracy > 90%
- [ ] No data loss incidents
- [ ] Backend handles 50+ concurrent users
- [ ] Edge device runs 8+ hours without restart

### User Experience Success

- [ ] Students can register in < 5 minutes
- [ ] Faculty can view attendance in real-time
- [ ] Mobile app is responsive and stable
- [ ] < 5 support requests per day
- [ ] Positive feedback from majority of users

### Operational Success

- [ ] System operates without manual intervention
- [ ] Issues resolved within 1 hour
- [ ] All incidents documented
- [ ] Team familiar with troubleshooting
- [ ] Monitoring provides early warning

## Rollback Procedure

If critical issues occur:

1. **Stop Edge Device**
   ```bash
   sudo systemctl stop iams-edge
   ```

2. **Stop Backend**
   ```bash
   ./scripts/stop_production.sh
   ```

3. **Restore from Backup (if needed)**
   ```bash
   ./scripts/restore.sh <timestamp>
   ```

4. **Notify Users**
   - Send message to pilot group
   - Explain issue and timeline
   - Provide manual attendance alternative

5. **Document Issue**
   - What happened
   - What was affected
   - How it was resolved
   - How to prevent in future

## Contact Information

**Technical Lead:** _____________
**Phone:** _____________
**Email:** _____________

**System Administrator:** _____________
**Phone:** _____________
**Email:** _____________

**Backup Contact:** _____________
**Phone:** _____________
**Email:** _____________

## Notes Section

Use this space to document actual deployment details:

**Backend IP:** _____________
**Edge Device IP:** _____________
**Room ID:** _____________
**WiFi SSID:** _____________
**Deployment Date:** _____________
**Pilot Duration:** _____________
**Number of Students:** _____________
**Number of Faculty:** _____________

**Issues Encountered:**
-
-
-

**Lessons Learned:**
-
-
-

**Next Steps:**
-
-
-
