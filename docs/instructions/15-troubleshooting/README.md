# Step 15: Troubleshooting

Common problems and how to fix them.

---

## Database Issues

### "Cannot connect to database" or "Connection refused"

**Cause:** The PostgreSQL container is not running.

**Fix:**
1. Make sure Docker Desktop is open and running
2. Start the database:
   ```bash
   cd iams
   docker compose up -d
   ```
3. Verify it's running:
   ```bash
   docker ps
   ```
   You should see `iams-postgres` with status "Up"

---

### "Port 5433 already in use"

**Cause:** Another process is using port 5433.

**Fix:**
1. Check what's using the port:
   ```bash
   docker ps -a
   ```
2. If there's an old `iams-postgres` container, remove it:
   ```bash
   docker rm -f iams-postgres
   docker compose up -d
   ```

---

### "Password authentication failed"

**Cause:** Connecting to the wrong PostgreSQL instance (e.g., a native PostgreSQL installation instead of Docker).

**Fix:**
- Make sure `DATABASE_URL` in `backend/.env` uses port **5433** (Docker), not 5432:
  ```
  DATABASE_URL=postgresql://postgres:postgres@localhost:5433/iams
  ```

---

## Backend Server Issues

### "ModuleNotFoundError: No module named 'app'"

**Cause:** You're not in the correct directory or the virtual environment is not activated.

**Fix:**
1. Make sure you're in the `backend/` folder:
   ```bash
   cd backend
   ```
2. Activate the virtual environment:
   ```bash
   venv\Scripts\activate    # Windows
   source venv/bin/activate  # Linux/Mac
   ```
   You should see `(venv)` in your prompt.

---

### "pip install fails" or "torch installation error"

**Fix:** Install PyTorch separately first:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

---

### "alembic upgrade head fails"

**Possible causes:**
1. Database is not running — start it with `docker compose up -d`
2. Wrong database URL — check `DATABASE_URL` in `backend/.env`
3. Already migrated — this is fine, the command is safe to run multiple times

**Debug:** Try connecting manually:
```bash
docker exec -it iams-postgres psql -U postgres -d iams
```
If this works, the database is fine and the issue is in the `.env` configuration.

---

## Mobile App Issues

### "Mobile app can't connect to backend"

**Cause:** Phone and laptop are not on the same network, or firewall is blocking.

**Fix:**
1. Make sure the phone and laptop are on the **same Wi-Fi network**
2. Find your laptop's IP:
   ```bash
   ipconfig          # Windows
   ifconfig           # Linux/Mac
   ```
3. Test from the phone's browser: open `http://<laptop-ip>:8000/docs`
4. If it doesn't load, check the **Windows Firewall**:
   - Allow Python through the firewall (see [Step 10](../10-connect-local-network/README.md))
   - Or temporarily disable the firewall for testing

---

### "Network request failed" in the app

**Cause:** The API URL is wrong or the backend is not running.

**Fix:**
1. Make sure the backend is running (`python run.py`)
2. Check if you need to manually set the IP in `mobile/.env`:
   ```
   EXPO_PUBLIC_API_BASE_URL=http://<laptop-ip>:8000/api/v1
   EXPO_PUBLIC_WS_BASE_URL=ws://<laptop-ip>:8000/api/v1/ws
   ```
3. Restart the mobile app after changing `.env`

---

### "App crashes on startup"

**Fix:**
1. Clear the app cache:
   ```bash
   cd mobile
   pnpm start:clear
   ```
2. If that doesn't work, reinstall dependencies:
   ```bash
   rm -rf node_modules
   pnpm install
   pnpm android
   ```

---

## Camera Issues

### "Camera feed not showing"

**Possible causes:**
1. Camera is offline or on a different network
2. RTSP URL is wrong
3. FFmpeg is not installed

**Fix:**
1. Make sure the camera is powered on and connected to the same Wi-Fi
2. Test the RTSP feed with VLC:
   - Open VLC > Media > Open Network Stream
   - Enter: `rtsp://admin:Iams2026THESIS@192.168.1.100:554/h264Preview_01_sub`
   - If it doesn't play, check the camera's IP address and credentials
3. Verify FFmpeg is installed: `ffmpeg -version`
4. Check the RTSP URL in `backend/.env`:
   ```
   DEFAULT_RTSP_URL=rtsp://admin:Iams2026THESIS@192.168.1.100:554/h264Preview_01_sub
   ```

---

## Face Recognition Issues

### "Face not recognized during attendance"

**Possible causes:**
1. Student hasn't registered their face
2. Poor lighting conditions
3. Student's face is too far from the camera

**Fix:**
1. Verify the student has completed face registration (3-5 photos)
2. Improve classroom lighting
3. Adjust camera position for better coverage
4. If persistent, try lowering the recognition threshold in `backend/.env`:
   ```
   RECOGNITION_THRESHOLD=0.5
   ```
   (Default is 0.6 — lower = more lenient, higher = more strict)

---

## Full Reset (Start From Scratch)

If something is seriously broken and you want to start completely fresh:

```bash
# 1. Stop everything
cd iams
docker compose down -v    # -v removes ALL database data

# 2. Start fresh
docker compose up -d

# 3. Recreate tables
cd backend
venv\Scripts\activate
alembic upgrade head

# 4. Reseed data
python -m scripts.seed_all --no-sim

# 5. Start the server
python run.py
```

**WARNING:** This deletes all users, attendance records, and face registrations. Students will need to register again.

---

## Still Having Issues?

1. Check the backend logs in `backend/logs/app.log`
2. Check Docker logs: `docker logs iams-postgres`
3. Check the API documentation at `http://localhost:8000/docs`
4. Contact the developer for support
