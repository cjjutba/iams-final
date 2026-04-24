# Two-App Split — Runbook

**Branch:** `feat/local-compute-split` (post 2026-04-22 split)
**Reads:** [DESIGN.md](DESIGN.md), [../2026-04-21-local-compute-split/RUNBOOK.md](../2026-04-21-local-compute-split/RUNBOOK.md)

This is the operational addendum. It assumes you've already done the
[on-prem first-time setup](../2026-04-21-local-compute-split/RUNBOOK.md#first-time-setup)
(Mac docker stack running, MikroTik DHCP reservation, RPi pointed at the Mac).

---

## What changed (one paragraph)

There are now **two Android APKs**, two backend deployment profiles, and one
admin portal:

- **`com.iams.app.student`** — install on student phones. Points at the on-prem Mac (IAMS-Net only). Includes face registration, daily schedule, attendance history.
- **`com.iams.app.faculty`** — install on faculty phones. Points at the public VPS (works anywhere). Login → today's classes → tap to watch the live stream. No detection overlay, no manual entry, no analytics.
- **VPS** runs the same backend image but with `ENABLE_*=false` for everything except auth + schedules + rooms + health. Postgres holds only faculty + schedules + rooms — no students, no faces.
- **Admin portal** is unchanged from the 2026-04-21 plan: served by the on-prem Mac, full-feature attendance monitoring, accessible only on IAMS-Net.

---

## First-time setup additions

If you set up `feat/local-compute-split` per the previous runbook, you have steps 1-8 done. Add:

### 9. Create `backend/.env.vps`

On YOUR LAPTOP (the source repo — `.env.vps` is gitignored, lives only locally + on the VPS):

```bash
cp backend/.env.vps.example backend/.env.vps
$EDITOR backend/.env.vps
#   SECRET_KEY        — fresh, DIFFERENT from .env.onprem and .env.production:
#                        python -c "import secrets; print(secrets.token_urlsafe(48))"
#   POSTGRES_PASSWORD — strong; you'll also export it in the shell that runs
#                        deploy.sh (compose substitutes it into DATABASE_URL)
```

### 10. First VPS deploy with the new mode

```bash
export POSTGRES_PASSWORD=<the strong password from step 9>
bash deploy/deploy.sh vps
```

What this does:
- rsyncs `docker-compose.vps.yml`, `nginx.vps.conf`, `mediamtx.relay.yml`, the backend code, and `backend/.env.vps`.
- on the VPS: `down`s any running `docker-compose.prod.yml` or `docker-compose.relay.yml`, then `up -d --build`s the vps stack (postgres + api-gateway + mediamtx + coturn + nginx + dozzle).
- runs `python -m scripts.seed_vps_minimal` inside the api-gateway container.
- curls `/api/v1/health` and prints the result.

If you only want the video relay without an API (thesis-fallback): `bash deploy/deploy.sh relay`.

### 11. Verify the VPS profile

```bash
curl -fsS http://167.71.217.44/api/v1/health         # 200, "redis": "disabled", "faiss": "disabled"
curl http://167.71.217.44/api/v1/face/register       # 404 — face router off
curl -X POST http://167.71.217.44/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"faculty.eb226@gmail.com","password":"password123"}'
# 200 + JWT
```

### 12. Build + install both APKs

```bash
cd android
./gradlew :app-student:clean :app-student:installDebug
./gradlew :app-faculty:clean :app-faculty:installDebug
```

Both APKs install side-by-side (different `applicationId`s). On the launcher:
**IAMS Student** + **IAMS Faculty**.

If you upgrade FROM the legacy single APK (`com.iams.app`), uninstall it once
before installing the new pair — they have different `applicationId`s so Android
treats the legacy APK as a third, unrelated install.

### 13. Switch student app between modes (unchanged)

```bash
./scripts/switch-env.sh local         # Student → Mac LAN IP : 8000 (dev stack)
./scripts/switch-env.sh onprem        # Student → Mac LAN IP : 80 (prod nginx on Mac)
./scripts/switch-env.sh production    # Student → 167.71.217.44 : 80 (rollback / fallback)
./scripts/switch-env.sh status        # Show current mode + faculty fixed line

# After every switch, rebuild only the student APK:
cd android && ./gradlew :app-student:clean :app-student:installDebug
```

The faculty APK is **unaffected** by switch-env. Its build config keys
(`IAMS_FACULTY_*`) are pinned to the VPS and never mutated. Rebuild the faculty
APK only when you change faculty source code or the VPS faculty creds.

---

## Daily operations

### Start of day (campus)

```bash
./scripts/onprem-up.sh           # Mac stack
# (VPS is always up, no daily restart needed)
```

### Re-seed the VPS after a schedule change

The VPS seed is a static snapshot. If you add / edit / remove a schedule in
[backend/scripts/seed_data.py](../../../backend/scripts/seed_data.py), re-deploy:

```bash
bash deploy/deploy.sh vps         # re-syncs code + re-runs seed_vps_minimal
```

For local-only seed updates (no VPS change):

```bash
docker exec iams-api-gateway-onprem python -m scripts.seed_data
```

### Stop the VPS thin API for a demo

```bash
ssh root@167.71.217.44 'cd /opt/iams/deploy && docker compose -f docker-compose.vps.yml stop api-gateway postgres'
```

mediamtx + coturn + nginx keep running, so video still works. Faculty APK
login + schedule load will fail until you `start`.

```bash
ssh root@167.71.217.44 'cd /opt/iams/deploy && docker compose -f docker-compose.vps.yml start api-gateway postgres'
```

---

## Troubleshooting

### Faculty APK: "Network error" at login

1. Faculty APK ALWAYS hits `http://167.71.217.44/api/v1/auth/login`. Check the device has internet.
2. Check the VPS thin API is up:
   ```bash
   curl http://167.71.217.44/api/v1/health
   ```
3. Check the api-gateway-vps container is healthy:
   ```bash
   ssh root@167.71.217.44 'docker compose -f /opt/iams/deploy/docker-compose.vps.yml ps'
   ```

### Faculty APK: Login OK, schedule list empty

The seed didn't run (or seeded against the wrong faculty email). Re-seed:

```bash
ssh root@167.71.217.44 'docker exec iams-api-gateway-vps python -m scripts.seed_vps_minimal'
```

### Faculty APK: Schedule loads, but live feed says "Stream unavailable"

The mediamtx push from the on-prem Mac is broken. Verify the VPS sees the
pushed stream:

```bash
ssh root@167.71.217.44 'docker exec iams-mediamtx curl -s http://localhost:9997/v3/paths/list | python3 -m json.tool'
```

If empty: the on-prem Mac's `runOnReady` ffmpeg isn't running. Check:

```bash
docker logs iams-mediamtx-onprem 2>&1 | grep -iE 'runOnReady|ffmpeg|fail'
```

### Student APK: Backend unreachable

Student APK is IAMS-Net-only. Phone must be on the same WiFi as the Mac. Check:

```bash
./scripts/switch-env.sh status         # mode is correct
ipconfig getifaddr en0                 # current Mac LAN IP matches gradle.properties
```

If the IP changed, re-run `./scripts/switch-env.sh onprem` (auto-detects) and
rebuild: `./gradlew :app-student:clean :app-student:installDebug`.

### "Both APKs were installed before — now Faculty APK won't update"

Different `applicationId` from the legacy single APK. Uninstall both:

```
adb uninstall com.iams.app.student
adb uninstall com.iams.app.faculty
adb uninstall com.iams.app           # legacy, if present
```

Then re-install. This is one-time per device.

### VPS thin API logs ML / FAISS errors at startup

Means a `ENABLE_*` flag wasn't picked up. The compose file pins them as
`environment:` overrides — check that `backend/.env.vps` doesn't override
them back to true and that the container actually mounted the env file:

```bash
ssh root@167.71.217.44 'docker exec iams-api-gateway-vps env | grep ENABLE_'
```

Expected output: every `ENABLE_*` is `false` except auth/users/rooms/schedules
(which aren't flagged).

---

## Rollback

If anything goes wrong:

```bash
# 1. VPS back to legacy full stack
bash deploy/deploy.sh full

# 2. Android back to single APK
git checkout feat/cloud-based -- android/
cd android && ./gradlew clean installDebug

# 3. Uninstall the new APKs (keep the legacy one)
adb uninstall com.iams.app.student
adb uninstall com.iams.app.faculty
```

This restores the pre-2026-04-22 world. The legacy single APK + full VPS
stack ARE preserved in git history (`feat/cloud-based` branch) and on the
VPS volume, respectively.
