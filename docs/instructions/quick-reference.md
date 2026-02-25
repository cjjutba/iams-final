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
| Build APK (Windows) | `cd mobile\android && gradlew.bat assembleRelease` |
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

**Test Student ID:** `21-A-02177`

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

## Full Reset

```bash
docker compose down -v
docker compose up -d
cd backend
venv\Scripts\activate
alembic upgrade head
python -m scripts.seed_all --no-sim
python run.py
```
