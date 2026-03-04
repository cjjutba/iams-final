# IAMS Troubleshooting Guide

Comprehensive guide for diagnosing and resolving common issues in IAMS deployment.

## Quick Diagnostics

### System Status Overview

```bash
# Backend
curl http://<backend-ip>:8000/api/v1/health

# Edge Device
ssh pi@<edge-ip>
sudo systemctl status iams-edge

# Check processes
pgrep -f "uvicorn"  # Backend
pgrep -f "python.*run.py"  # Edge
```

## Backend Issues

### Backend Won't Start

**Symptom:** Backend fails to start or exits immediately

**Diagnosis:**
```bash
cd backend
source venv/bin/activate
python scripts/validate_env.py
```

**Common Causes:**

1. **Missing Environment Variables**
   ```
   Error: SUPABASE_URL not set
   ```
   **Solution:** Configure .env file with required variables

2. **Port Already in Use**
   ```
   Error: [Errno 98] Address already in use
   ```
   **Solution:**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   # or
   netstat -tulpn | grep 8000

   # Kill process
   kill -9 <PID>
   ```

3. **Database Connection Failed**
   ```
   Error: Could not connect to database
   ```
   **Solution:**
   - Check DATABASE_URL is correct
   - Verify using pooler URL (not direct)
   - Test connection: `psql $DATABASE_URL -c "SELECT 1"`
   - Check Supabase project status

4. **Missing Dependencies**
   ```
   ModuleNotFoundError: No module named 'fastapi'
   ```
   **Solution:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Permission Errors**
   ```
   PermissionError: [Errno 13] Permission denied: 'logs/app.log'
   ```
   **Solution:**
   ```bash
   mkdir -p logs data/faiss data/uploads
   chmod 755 logs data
   ```

### Backend Running But Not Accessible

**Symptom:** Backend starts but can't connect from other devices

**Diagnosis:**
```bash
# Test from backend machine
curl http://localhost:8000/api/v1/health

# Test from another device
curl http://<backend-ip>:8000/api/v1/health
```

**Common Causes:**

1. **Firewall Blocking Port**

   **Windows:**
   ```cmd
   netsh advfirewall firewall add rule name="IAMS Backend" dir=in action=allow protocol=TCP localport=8000
   ```

   **Linux:**
   ```bash
   sudo ufw allow 8000/tcp
   sudo ufw reload
   ```

2. **Backend Bound to Localhost Only**

   **Solution:** Check uvicorn starts with `host="0.0.0.0"`
   ```python
   # run_production.py
   uvicorn.run(
       "app.main:app",
       host="0.0.0.0",  # Not "127.0.0.1"
       port=8000,
   )
   ```

3. **Wrong IP Address**

   **Find correct IP:**
   ```bash
   # Windows
   ipconfig

   # Linux/Mac
   hostname -I
   ip addr show
   ```

4. **CORS Errors**

   **Symptom:** Mobile app can't connect, browser console shows CORS error

   **Solution:**
   ```env
   # .env.production
   CORS_ORIGINS=["*"]  # For pilot testing
   # or specific origins:
   CORS_ORIGINS=["http://192.168.1.100:8000"]
   ```

### Database Connection Issues

**Symptom:** Backend connects but database queries fail

**Diagnosis:**
```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check connection pool
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity"
```

**Common Causes:**

1. **Using Direct Connection (IPv6)**

   **Problem:** Supabase direct connection requires IPv6

   **Solution:** Use pooler connection:
   ```
   # Wrong (direct, IPv6 only)
   postgresql://postgres.xxx:pass@db.xxx.supabase.co:5432/postgres

   # Correct (pooler, IPv4)
   postgresql://postgres.xxx:pass@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   ```

2. **Connection Pool Exhausted**

   **Symptom:** "Too many connections" error

   **Solution:**
   - Reduce number of uvicorn workers
   - Increase Supabase connection limit
   - Check for connection leaks in code

3. **Supabase Project Paused**

   **Solution:** Resume project in Supabase dashboard

### FAISS Index Issues

**Symptom:** Face recognition fails or index not loading

**Diagnosis:**
```bash
# Check if index exists
ls -lh data/faiss/faces.index

# Check backend logs
tail -50 logs/app.log | grep -i "faiss"
```

**Common Causes:**

1. **Index File Not Found**

   **Solution:** This is normal for first-time setup. Register first face to create index.

2. **Index Corrupted**

   **Symptom:** Error loading index

   **Solution:**
   ```bash
   # Restore from backup
   ./scripts/restore.sh <timestamp>

   # Or rebuild index (requires all faces re-registered)
   rm data/faiss/faces.index
   # Restart backend
   ```

3. **GPU Not Available**

   **Symptom:** "CUDA not available" warning

   **Solution:** Set `USE_GPU=false` in .env (will use CPU)

## Edge Device Issues

### Edge Device Won't Start

**Diagnosis:**
```bash
ssh pi@<edge-ip>
sudo systemctl status iams-edge
sudo journalctl -u iams-edge -n 50
```

**Common Causes:**

1. **Camera Not Detected**
   ```
   Error: Cannot open camera
   ```
   **Solution:**
   ```bash
   # List video devices
   ls -l /dev/video*

   # Test camera
   libcamera-hello

   # Check permissions
   groups pi  # Should include 'video' group

   # Add to video group if missing
   sudo usermod -a -G video pi
   sudo reboot
   ```

2. **Backend Not Reachable**
   ```
   Error: Connection refused
   ```
   **Solution:**
   ```bash
   # Test network
   ping <backend-ip>

   # Test backend API
   curl http://<backend-ip>:8000/api/v1/health

   # Update SERVER_URL in .env
   nano /home/pi/iams-edge/.env
   ```

3. **Missing Dependencies**
   ```
   ModuleNotFoundError: No module named 'mediapipe'
   ```
   **Solution:**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Edge Device Running But No Detections

**Symptom:** Service running but no faces detected

**Diagnosis:**
```bash
tail -f /home/pi/iams-edge/logs/edge.log
```

**Common Causes:**

1. **Camera Not Positioned Correctly**

   **Solution:**
   - Check camera angle (should be 15-30° downward)
   - Verify camera can see face area
   - Test by standing in front of camera
   - Check logs for detection messages

2. **Detection Threshold Too High**

   **Solution:**
   ```env
   # .env
   MIN_DETECTION_CONFIDENCE=0.3  # Lower threshold
   ```

3. **Poor Lighting**

   **Solution:**
   - Add lighting to area
   - Avoid backlighting
   - Adjust camera exposure settings

4. **Camera Resolution Too Low**

   **Solution:**
   ```env
   FRAME_WIDTH=640
   FRAME_HEIGHT=480
   ```

### Edge Device Queue Filling Up

**Symptom:** Queue size growing, detections not processed

**Diagnosis:**
```bash
tail -f logs/edge.log | grep -i "queue"
```

**Common Causes:**

1. **Backend Unreachable**

   **Solution:**
   - Check backend is running
   - Verify network connectivity
   - Check backend logs for errors

2. **Backend Overloaded**

   **Solution:**
   - Increase backend workers
   - Optimize face recognition performance
   - Check backend resource usage

3. **Network Issues**

   **Solution:**
   - Check WiFi signal strength
   - Reduce network congestion
   - Increase retry interval

### High CPU Usage on Raspberry Pi

**Symptom:** Raspberry Pi running hot, sluggish performance

**Diagnosis:**
```bash
top
# Check CPU usage of python process

# Check temperature
cat /sys/class/thermal/thermal_zone0/temp
# (Value in millidegrees, divide by 1000)
```

**Solutions:**

1. **Reduce Frame Rate**
   ```env
   FRAME_RATE=5  # Lower from 10-15
   ```

2. **Increase Frame Skip**
   ```env
   FRAME_SKIP=2  # Process every other frame
   ```

3. **Reduce Resolution**
   ```env
   FRAME_WIDTH=320
   FRAME_HEIGHT=240
   ```

4. **Improve Cooling**
   - Add heatsink
   - Add fan
   - Improve airflow

## Mobile App Issues

### Can't Connect to Backend

**Symptom:** App shows connection errors, can't login

**Diagnosis:**
1. Open device browser
2. Navigate to: `http://<backend-ip>:8000/api/v1/health`
3. Should see JSON response

**Common Causes:**

1. **Wrong Backend IP in Build**

   **Solution:**
   - Rebuild APK with correct IP
   - Update eas.json
   - Build: `eas build -p android --profile pilot`

2. **Not on Same Network**

   **Solution:**
   - Connect mobile device to same WiFi as backend
   - Verify WiFi SSID matches

3. **Firewall Blocking**

   **Solution:** Allow port 8000 on backend

4. **VPN Interfering**

   **Solution:** Disable VPN on mobile device

### Login Fails

**Symptom:** Credentials correct but login fails

**Diagnosis:**
```bash
# Check backend logs
tail -f logs/app.log | grep -i "login"

# Test login via curl
curl -X POST http://<backend-ip>:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

**Common Causes:**

1. **User Doesn't Exist**

   **Solution:**
   - Verify user in database
   - Check seed data was loaded
   - Register new user

2. **Wrong Password**

   **Solution:** Reset password via forgot password flow

3. **JWT Secret Mismatch**

   **Solution:** Ensure backend SECRET_KEY hasn't changed

### Face Registration Fails

**Symptom:** Can't capture face images or registration fails

**Common Causes:**

1. **Camera Permission Denied**

   **Solution:**
   - Grant camera permission in device settings
   - Reinstall app if permission was denied

2. **Poor Lighting**

   **Solution:** Move to well-lit area

3. **Face Not Detected**

   **Solution:**
   - Look directly at camera
   - Remove glasses/mask if needed
   - Ensure adequate lighting

4. **Backend Processing Error**

   **Solution:** Check backend logs for face processing errors

### WebSocket Not Connecting

**Symptom:** Real-time updates not working

**Diagnosis:**
```javascript
// Check browser console for WebSocket errors
// WS URL should be: ws://<backend-ip>:8000/api/v1/ws/<user-id>
```

**Common Causes:**

1. **Wrong WebSocket URL**

   **Solution:**
   - Check WS_BASE_URL in mobile .env
   - Should match backend IP
   - Should be `ws://` not `http://`

2. **Backend Not Supporting WebSocket**

   **Solution:** Verify backend has WebSocket router registered

3. **Network Proxy/Firewall**

   **Solution:** WebSocket requires direct connection, no proxy

## Database Issues

### Migrations Fail

**Symptom:** Alembic migration errors

**Diagnosis:**
```bash
cd backend
alembic current  # Check current version
alembic history  # View migration history
```

**Common Causes:**

1. **Migration Already Applied**

   **Solution:** Check alembic_version table in database

2. **Schema Conflict**

   **Solution:**
   - Backup database
   - Resolve conflicts manually
   - Update migration script

3. **Connection Error**

   **Solution:** Verify DATABASE_URL correct

### Database Performance Issues

**Symptom:** Slow queries, timeouts

**Diagnosis:**
```sql
-- Check long-running queries
SELECT * FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start;

-- Check table sizes
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Solutions:**

1. **Add Indexes**
   ```sql
   CREATE INDEX idx_attendance_user_id ON attendance_records(user_id);
   CREATE INDEX idx_attendance_schedule_id ON attendance_records(schedule_id);
   ```

2. **Vacuum Database**
   ```sql
   VACUUM ANALYZE;
   ```

3. **Upgrade Supabase Plan** (if connection limit reached)

## Network Issues

### Devices Can't See Each Other

**Diagnosis:**
```bash
# From mobile device or edge device
ping <backend-ip>

# From backend
ping <edge-ip>
```

**Common Causes:**

1. **Different Networks**

   **Solution:** Ensure all devices on same WiFi SSID

2. **AP Isolation Enabled**

   **Symptom:** Devices can reach internet but not each other

   **Solution:** Disable AP Isolation in router settings

3. **Firewall Rules**

   **Solution:** Configure firewall to allow local network

### Intermittent Connectivity

**Symptom:** Connections drop randomly

**Diagnosis:**
```bash
# Check WiFi signal strength
iwconfig  # On Linux

# Ping with timestamp
ping -D <backend-ip>
```

**Solutions:**

1. **Improve WiFi Signal**
   - Move closer to router
   - Use WiFi extender
   - Switch to 2.4GHz (better range)

2. **Reduce Network Congestion**
   - Limit other users on network
   - Use QoS on router

3. **Increase Retry Settings**
   ```env
   # Edge device .env
   RETRY_INTERVAL_SECONDS=5
   CONNECTION_TIMEOUT=15
   ```

## Performance Issues

### Slow Face Recognition

**Symptom:** Recognition takes > 3 seconds

**Diagnosis:**
```bash
# Check backend logs for timing
tail -f logs/app.log | grep -i "recognition"

# Check CPU usage
top
```

**Solutions:**

1. **Enable GPU** (if available)
   ```env
   USE_GPU=true
   ```

2. **Reduce FAISS Index Size**
   - Remove old/inactive users
   - Rebuild index regularly

3. **Increase Backend Resources**
   - More CPU cores
   - More RAM
   - Add GPU

4. **Optimize Workers**
   ```python
   # run_production.py
   workers = 4  # Tune based on CPU cores
   ```

### High Memory Usage

**Symptom:** Backend using > 2GB RAM

**Diagnosis:**
```bash
free -h
top -o %MEM
```

**Solutions:**

1. **Reduce Workers**
   - Fewer uvicorn workers
   - Each worker loads full model

2. **Implement Model Caching**
   - Share FaceNet model across workers
   - Use Redis for caching

3. **Add Memory Limits**
   ```ini
   # systemd service
   MemoryLimit=2G
   ```

## Emergency Procedures

### Complete System Failure

**Steps:**

1. **Stop All Services**
   ```bash
   # Backend
   ./scripts/stop_production.sh

   # Edge device
   ssh pi@<edge-ip>
   sudo systemctl stop iams-edge
   ```

2. **Backup Current State**
   ```bash
   ./scripts/backup.sh
   ```

3. **Restore from Last Known Good Backup**
   ```bash
   ./scripts/restore.sh <timestamp>
   ```

4. **Restart Services**
   ```bash
   ./scripts/start_production.sh
   sudo systemctl start iams-edge
   ```

5. **Verify Functionality**
   - Test backend health
   - Test face recognition
   - Test mobile app connectivity

### Data Loss Prevention

**If data loss suspected:**

1. **Stop all writes immediately**
2. **Backup current state**
3. **Check Supabase dashboard for point-in-time restore**
4. **Contact Supabase support if needed**

## Getting Help

### Collect Diagnostic Information

Before requesting help, collect:

```bash
# Backend info
curl http://localhost:8000/api/v1/health > health.json
tail -100 logs/app.log > backend-logs.txt
./scripts/monitor.sh > monitor-output.txt

# Edge device info
ssh pi@<edge-ip> "tail -100 logs/edge.log" > edge-logs.txt
ssh pi@<edge-ip> "./scripts/health_check.sh" > edge-health.txt

# System info
uname -a > system-info.txt
free -h >> system-info.txt
df -h >> system-info.txt
```

### Support Channels

1. **GitHub Issues:** [Repository URL]
2. **Email:** support@iams.jrmsu.edu.ph
3. **Emergency Contact:** [Phone number]

Include in support request:
- Clear description of issue
- Steps to reproduce
- Diagnostic logs
- Environment details (OS, Python version, etc.)
- When issue started occurring
