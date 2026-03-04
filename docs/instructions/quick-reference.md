# Quick Reference Card

One-page cheat sheet for all common IAMS commands.

---

## Startup (in order)

```bash
# 1. Open Docker Desktop first, then:

# 2. Start database
cd iams
docker compose up -d

# 3. Start backend (new terminal)
cd backend
venv\Scripts\activate          # Windows
python run.py
```

---

## Shutdown (in order)

```bash
# 1. Stop backend
Ctrl+C

# 2. Stop database
cd iams
docker compose down
```

---

## Common Commands

| Action | Command |
|--------|---------|
| Start database | `docker compose up -d` |
| Stop database | `docker compose down` |
| Stop database + delete data | `docker compose down -v` |
| Check database status | `docker ps` |
| Start backend | `cd backend && venv\Scripts\activate && python run.py` |
| Run migrations | `cd backend && alembic upgrade head` |
| Seed data (no simulation) | `cd backend && python -m scripts.seed_all --no-sim` |
| Seed data (with simulation) | `cd backend && python -m scripts.seed_all` |
| Run tests | `cd backend && pytest` |
| Validate config | `cd backend && python -m scripts.validate_env` |
| Install mobile deps | `cd mobile && pnpm install` |
| Run mobile app (dev) | `cd mobile && pnpm android` |
| Run on emulator only | `cd mobile && pnpm android --device emulator-5554` |
| Run on real device only | `cd mobile && pnpm android --device <serial>` |
| List connected devices | `adb devices` |
| Build APK (Mac) | `cd mobile/android && ./gradlew assembleRelease` |
| Find laptop IP | `ipconfig` (Windows) / `ifconfig` (Mac/Linux) |
| Connect to DB | `docker exec -it iams-postgres psql -U postgres -d iams` |
| View DB logs | `docker logs iams-postgres` |
| View backend logs | Check `backend/logs/app.log` |

---

## URLs

| URL | Purpose |
|-----|---------|
| http://localhost:8000/api/v1/health | Health check |
| http://localhost:8000/docs | API documentation (Swagger) |
| http://localhost:8000/redoc | API documentation (ReDoc) |

---

## Login Credentials

| Role | Email | Password |
|------|-------|----------|
| Faculty | faculty@gmail.com | password123 |
| Student | (register via app) | (set during registration) |

**Test Student IDs:** `21-A-02177` (Christian Jerald Jutba), `21-A-01234` (Juhazelle Espela)

---

## Database Connection

| Field | Value |
|-------|-------|
| Host | localhost |
| Port | 5433 |
| Database | iams |
| Username | postgres |
| Password | postgres |

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/.env` | Backend configuration (database URL, secrets, camera URL) |
| `mobile/.env` | Mobile app configuration (API URL override) |
| `docker-compose.yml` | PostgreSQL Docker configuration |
| `backend/logs/app.log` | Backend server logs |

---

## Dual-Device Testing (Emulator + Real Device)

Run the faculty portal on an Android emulator and student portal on a real device simultaneously:

1. Start the backend: `cd backend && python run.py` (binds to `0.0.0.0:8000`)
2. Connect your real Android device via USB and enable USB debugging
3. Start the emulator from Android Studio (e.g. `Medium_Phone_API_36`)
4. Verify both are visible: `adb devices`
5. Run Metro: `cd mobile && pnpm start`
6. Press `a` to install on all connected Android devices

The app auto-detects the device type:
- **Emulator** → connects via `10.0.2.2:8000` (maps to host localhost)
- **Real device** → connects via your Mac's LAN IP (auto-detected from Metro)

Check Metro logs for: `[IAMS Config] Platform=android emulator=true/false ...`

---

## Full Reset

```bash
docker compose down -v
docker compose up -d
cd backend
source venv/bin/activate
alembic upgrade head
python -m scripts.seed_all --no-sim
python run.py
```
