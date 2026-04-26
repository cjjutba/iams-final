# IAMS On-Prem Deployment — Runbook

**Branch:** `feat/local-compute-split`
**Target host:** MacBook Pro M5 (24 GB RAM, Apple Silicon, macOS) on IAMS-Net
**Mode:** `onprem` (third mode alongside `local` and `production` — see `scripts/switch-env.sh`)

This runbook covers first-time setup, daily operation, and common recovery scenarios for the on-prem Mac that now runs the IAMS backend + admin portal on the school LAN.

---

## Architecture recap

```
Reolink → RPi (FFmpeg copy relay)
            │ RTSP push → rtsp://<MAC_IP>:8554/<streamKey>
            v
     Mac (Docker Desktop, IAMS-Net, static IP):
       ├ mediamtx       (ingest + WebRTC + runOnReady push to VPS)
       ├ api-gateway    (FastAPI + SCRFD + ArcFace + FAISS, CPU-only)
       ├ postgres + redis
       └ nginx          (serves admin portal static + proxies /api /ws /whep)

     VPS (167.71.217.44, public):
       └ mediamtx relay (accepts push from Mac, serves public WebRTC to mobile app)
```

---

## First-time setup

### 1. Docker runtime

Any of these work on macOS Apple Silicon. Pick one; all run the same images.

**Option A — Docker Desktop** (default, well-known):
- Install from https://www.docker.com/products/docker-desktop/
- In Preferences → Resources, allocate ≥ 16 GB RAM and ≥ 6 CPUs (we have 24 GB total on M5).

**Option B — OrbStack** (faster on Apple Silicon, free for personal use):
- `brew install --cask orbstack` or from https://orbstack.dev
- `docker` CLI auto-wires to OrbStack's engine.

GPU passthrough is **not available** on either — the Apple Neural Engine / Metal don't reach the Linux VM containers run in. `USE_GPU=false` is the committed default; CPU inference on M5 handles 10 fps SCRFD + ArcFace comfortably.

### 2. Clone + environment

```bash
cd ~/Projects
git clone <repo> iams && cd iams

# On-prem backend env (gitignored; fill real secrets):
cp backend/.env.onprem.example backend/.env.onprem
$EDITOR backend/.env.onprem
#   SECRET_KEY    (python -c "import secrets; print(secrets.token_urlsafe(48))")
#   POSTGRES_PASSWORD      (any strong string — set it in your shell too)
#   RESEND_API_KEY         (optional; set EMAIL_ENABLED=true if using)
```

### 3. MikroTik DHCP reservation

So the Android APK and admin portal URLs keep working across Mac reboots:

1. Log into the MikroTik admin UI.
2. Find the Mac's current IAMS-Net IP + MAC address in DHCP Server → Leases.
3. Right-click → **Make Static** (or manually add a reservation).
4. Note the pinned IP — you'll need it for step 4.

**No IP pinning** = the Mac may drop onto a different DHCP lease after a reboot, and your Android builds (which have BACKEND_HOST baked in at compile time) point at an IP nothing is listening on.

### 4. Switch configs to onprem mode

```bash
./scripts/switch-env.sh onprem
./scripts/switch-env.sh status
# → ONPREM (Mac LAN IP: 192.168.88.x:80 via nginx)
```

This rewrites:
- `android/gradle.properties` → REST/WS host = Mac IP : 80 ; video stream host = VPS.
- `admin/.env.production` → relative URLs (proxied by local nginx).
- `admin/vite.config.ts` → proxy targets Mac for `npm run dev` iteration.

### 5. Start the stack

```bash
./scripts/onprem-up.sh
```

First boot takes ~3–5 minutes:
1. `postgres` + `redis` start immediately.
2. `api-gateway` builds the backend image (~60 s on M5), loads InsightFace models.
3. `admin-build` sidecar runs `npm ci && npm run build -- --mode onprem` (~90 s).
4. `nginx` starts after api-gateway is healthy AND admin-build exits cleanly.

Verify:
```bash
curl -fsS http://localhost/api/v1/health    # 200 OK
open http://<MAC_IP>/                       # admin portal from any LAN browser
```

### 6. Seed the database (first boot only)

```bash
docker exec iams-api-gateway-onprem python -m scripts.seed_data
```

This populates ~180 students, faculty accounts, admin, rooms, and the full schedule set. Safe to re-run — the script wipes first.

### 7. Point the RPi at the Mac

On the RPi (SSH in):
```bash
cd /opt/iams/edge   # (or wherever the edge is deployed)
nvim .env
#   RELAY_HOST=<MAC_LAN_IP>   (was VPS_HOST=167.71.217.44)
sudo systemctl restart iams-edge-relay.service
```

Verify from the Mac:
```bash
docker exec iams-mediamtx-onprem curl -s http://localhost:9997/v3/paths/list \
  | python3 -m json.tool
# Should show the RPi-pushed path, e.g. {"items":[{"name":"eb226","source":...}]}
```

### 8. Android APK

```bash
cd android && ./gradlew clean installDebug
```

**Always use `clean`** when switching modes — see `memory/lessons.md` 2026-04-18 (stale BuildConfig bug).

---

## Daily operations

### Start of day
```bash
./scripts/onprem-up.sh
```
(Idempotent — safe to run even if containers are already up.)

### Disable Mac sleep during school hours
Docker containers stop when the Mac sleeps. Keep it awake while docked on AC:

**System Settings → Battery → Power Adapter:**
- "Prevent automatic sleeping when the display is off" → **On**
- "Turn display off after" → Never (or "Only on battery")

Or during a class run, from terminal:
```bash
caffeinate -dims &           # prevents sleep until you kill it
# ...class ends...
kill %1
```

### Stop the stack
```bash
./scripts/onprem-down.sh
# or to wipe volumes (DB, FAISS, admin build):
./scripts/onprem-down.sh --purge
```

### Switch between `local` (dev) and `onprem` (prod)

The two stacks use **different Docker Compose files, different postgres credentials, and different named volumes**, so they can coexist but shouldn't both be running on port 80 / 8000 / 8554 at the same time.

```bash
# From local dev to onprem:
./scripts/dev-down.sh
./scripts/switch-env.sh onprem
./scripts/onprem-up.sh
cd android && ./gradlew clean installDebug

# From onprem back to local dev:
./scripts/onprem-down.sh
./scripts/switch-env.sh local
./scripts/dev-up.sh
cd admin && npm run dev    # separate terminal
cd android && ./gradlew clean installDebug
```

### View logs
```bash
# All services:
docker compose -f deploy/docker-compose.onprem.yml logs -f

# Just the backend:
docker compose -f deploy/docker-compose.onprem.yml logs -f api-gateway

# Via Dozzle (browser): http://localhost:9998/
```

### Rebuild admin portal after code changes
The admin-build sidecar only runs on `up` (first time + any rebuild). To rebuild in place without restarting everything else:

```bash
docker compose -f deploy/docker-compose.onprem.yml up -d --build admin-build
docker compose -f deploy/docker-compose.onprem.yml restart nginx
```

Or simpler — just re-run `./scripts/onprem-up.sh` and let `--build` handle it.

---

## Recovery scenarios

### Mac's LAN IP changed

Symptoms: Android + remote admin portal users can't reach the Mac after a reboot.

Fixes:
1. Check MikroTik DHCP — is the Mac still reserved to the expected IP?
2. If yes, run `./scripts/onprem-up.sh` — it detects the current IP and patches mediamtx + env.
3. If no (IP really changed), re-run `./scripts/switch-env.sh onprem` to bake the new IP into the Android + admin configs, then `cd android && ./gradlew clean installDebug` to push a fresh APK.

### Mac → VPS push not working

Symptoms: Mobile app shows "Stream unavailable" on the faculty live feed.

Check:
```bash
docker logs iams-mediamtx-onprem 2>&1 | grep -iE 'runOnReady|ffmpeg|fail'
ssh root@167.71.217.44 'docker exec iams-mediamtx curl -s http://localhost:9997/v3/paths/list | python3 -m json.tool'
```
The VPS should list the same path name the RPi pushed to the Mac (e.g. `eb226`).

Common causes:
- School firewall blocking outbound TCP 8554. Test with `nc -vz 167.71.217.44 8554` from the Mac.
- VPS mediamtx not running. `ssh root@167.71.217.44 'docker ps'` should show `iams-mediamtx`. If not, `bash deploy/deploy.sh relay`.

### admin-build sidecar hangs

Symptoms: nginx never starts; `docker compose ps` shows `admin-build` running for > 5 min.

```bash
docker compose -f deploy/docker-compose.onprem.yml logs admin-build
# Usually npm ci is downloading slowly. Let it finish or:
docker compose -f deploy/docker-compose.onprem.yml up -d --build admin-build
```

### Reset everything

Full wipe + rebuild:
```bash
./scripts/onprem-down.sh --purge      # drops volumes
./scripts/onprem-up.sh                # rebuild from scratch
docker exec iams-api-gateway-onprem python -m scripts.seed_data
```

### Fall back to legacy VPS-everything

If the on-prem stack is broken during a live demo and you need the old single-VPS setup back **right now**:

```bash
./scripts/switch-env.sh production
bash deploy/deploy.sh full            # legacy full-stack deploy
cd android && ./gradlew clean installDebug
```

---

## Monitoring cheatsheet

| What | Where |
|---|---|
| Backend health | `curl http://localhost/api/v1/health` |
| mediamtx paths (local) | `docker exec iams-mediamtx-onprem curl -s http://localhost:9997/v3/paths/list` |
| mediamtx paths (VPS) | `ssh root@167.71.217.44 'docker exec iams-mediamtx curl -s http://localhost:9997/v3/paths/list'` |
| All container logs | `http://localhost:9998/` (Dozzle) |
| Postgres shell | `docker exec -it iams-postgres-onprem psql -U iams -d iams` |
| Redis shell | `docker exec -it iams-redis-onprem redis-cli` |
| Admin portal URL | `http://<MAC_IP>/` (LAN only) |
| VPS public stream | `http://167.71.217.44:8889/<streamKey>/whep` |

---

## Post-thesis: moving to dedicated hardware

The MacBook goes home every evening → IAMS is school-hours-only. For a real deployment:

- **Any mini-PC with 16+ GB RAM and a 10 Gen+ CPU works.** Intel NUC, Beelink, MeLE, refurb Lenovo ThinkCentre Tiny — ₱8k–15k budget.
- Install Ubuntu Server 22.04 LTS → Docker Engine (via `get.docker.com`) → same `deploy/docker-compose.onprem.yml` (substitute host.docker.internal → actual Docker bridge IP if needed).
- If going Linux + NVIDIA: flip `USE_GPU=true` and uncomment the GPU stanza in the compose file to use `onnxruntime-gpu` (~3× throughput for the same pipeline).
- MikroTik DHCP reservation, auto-start via systemd, headless operation — mini-PC stays at school, no "goes home with owner" fragility.
