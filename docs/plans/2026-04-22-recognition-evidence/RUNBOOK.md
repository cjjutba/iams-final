# Recognition Evidence — Runbook

Operator-level "how to roll out each phase" + troubleshooting.
Companion to [DESIGN.md](DESIGN.md).

Date: 2026-04-22

---

## One-paragraph summary

Every face-recognition decision on the Mac pipeline is captured as a `recognition_events` row + a pair of JPEG crops (live face + registered face). An admin sees decisions streaming in real time on the live-feed page, can audit any individual attendance row to see the evidence trail, and can pull historical reports across schedules. Crops age out after 30 days; every crop view is audit-logged; nothing leaves the on-prem Mac.

---

## First-time setup additions (fresh clone)

On top of the existing clone steps in [CLAUDE.md §Secrets + first-time setup](../../../CLAUDE.md):

```bash
# 1. Pick up the new env keys in backend/.env.onprem
cat >> backend/.env.onprem <<'EOF'
ENABLE_RECOGNITION_EVIDENCE=true
RECOGNITION_EVIDENCE_CROP_ROOT=/var/lib/iams/crops
RECOGNITION_EVIDENCE_CROP_QUALITY=75
RECOGNITION_EVIDENCE_QUEUE_SIZE=1000
RECOGNITION_EVIDENCE_BATCH_ROWS=50
RECOGNITION_EVIDENCE_BATCH_MS=500
RECOGNITION_CROP_RETENTION_DAYS=30
RECOGNITION_EVENT_RETENTION_DAYS=365
ENABLE_RECOGNITION_EVIDENCE_RETENTION=true
RECOGNITION_EVIDENCE_RETENTION_DRY_RUN=true  # keep true until Phase 5 cutover
RECOGNITION_EVIDENCE_BACKEND=filesystem       # 'minio' after Phase 5
EOF

# 2. Pick up the VPS-side disable flag in backend/.env.vps
cat >> backend/.env.vps <<'EOF'
ENABLE_RECOGNITION_EVIDENCE=false
EOF

# 3. Phase 5 only — generate the MinIO encryption key
python3 -c "import secrets,base64; print('MINIO_ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())" \
    >> scripts/.env.local
```

---

## Daily operations

### Bring the stack up (unchanged from two-app-split runbook)

```bash
./scripts/dev-down.sh
./scripts/onprem-up.sh           # now also mounts iams-crops-onprem volume
./scripts/start-cam-relay.sh
```

Verify the feature is live:

```bash
# A minute after an active session starts + a face is in frame:
docker exec iams-postgres-onprem psql -U postgres -d iams \
    -c "SELECT COUNT(*), MAX(created_at) FROM recognition_events;"

# Crops visible on disk:
docker exec iams-api-gateway-onprem ls "/var/lib/iams/crops/$(date +%Y-%m-%d)/" | head
```

### Watch the live panel

Open `http://192.168.88.17/schedules/<id>/live`. Panel is on the right side of the video (collapsed on narrow viewports — toggle with the icon in the live-feed header).

### Pull an evidence report for a specific student

Admin portal → Schedules → (pick schedule) → click the student's row in the attendance table → slide-up sheet → scroll to "Recognition Evidence" section.

Or by URL: `/recognitions?schedule_id=<uuid>&student_id=<uuid>` (Phase 4).

### Export CSV (Phase 4)

`/recognitions` route → set filters → Export CSV button. File name: `recognition-events-<YYYYMMDD-HHMM>.csv`. Streams directly from Postgres via async generator — no server-side buffering.

---

## Phase rollouts

Each phase is one PR, one deploy, one verification pass.

### Phase 1 — Silent capture

```bash
# 1. Merge the Phase 1 PR into feat/local-compute-split
git checkout feat/local-compute-split
git merge --ff-only <phase-1-pr-sha>

# 2. Apply the migration
docker exec iams-api-gateway-onprem alembic upgrade head

# 3. Restart api-gateway to pick up the new writer
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway-onprem

# 4. Verify (Table §1.7 from DESIGN.md)
docker exec iams-postgres-onprem psql -U postgres -d iams \
    -c "SELECT COUNT(*) FROM recognition_events;"

# 5. Let it bake for 24 hours before Phase 2 — you want a full day of data
#    to sanity-check volume and threshold distribution.
docker exec iams-postgres-onprem psql -U postgres -d iams \
    -c "SELECT matched, COUNT(*), AVG(similarity), MIN(similarity), MAX(similarity)
        FROM recognition_events
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY matched;"
```

Expected: the `matched=true` set has mean similarity well above `RECOGNITION_THRESHOLD=0.3`; the `matched=false` set sits below it. If `matched=true` mean is within 0.05 of threshold, do NOT proceed to Phase 2 — retune `RECOGNITION_THRESHOLD` first.

### Phase 2 — Live panel

```bash
git merge --ff-only <phase-2-pr-sha>

# Frontend rebuild via the iams-admin-build-onprem sidecar runs on compose up
docker compose -f deploy/docker-compose.onprem.yml up -d --force-recreate admin-build-onprem

# Nginx picks up the new bundle automatically (volume-shared)

# Verify: open http://192.168.88.17/schedules/<id>/live → panel appears on the right
```

No backend migration; no restart needed beyond the admin rebuild.

### Phase 3 — Per-student evidence

```bash
git merge --ff-only <phase-3-pr-sha>
docker compose -f deploy/docker-compose.onprem.yml up -d --force-recreate admin-build-onprem

# Verify: open a schedule → click a student row → the sheet includes
#   "Recognition Evidence" with histogram + timeline + peak match.
```

### Phase 4 — Global page + retention

```bash
git merge --ff-only <phase-4-pr-sha>
docker compose -f deploy/docker-compose.onprem.yml up -d --force-recreate admin-build-onprem api-gateway-onprem

# IMPORTANT: retention starts in DRY RUN. Let it run for 3 days, confirm the
# "would delete" counts look sensible, THEN flip dry-run off.

# Day 1-3: observe
docker logs iams-api-gateway-onprem 2>&1 | grep 'retention' | tail

# Day 4: flip off
sed -i '' 's/RECOGNITION_EVIDENCE_RETENTION_DRY_RUN=true/RECOGNITION_EVIDENCE_RETENTION_DRY_RUN=false/' \
    backend/.env.onprem
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway-onprem
```

### Phase 5 — Enterprise hardening (MinIO + audit + signed URLs)

```bash
# 1. Add MinIO to the stack
git merge --ff-only <phase-5-pr-sha>
./scripts/onprem-up.sh     # brings up iams-minio-onprem

# 2. Apply the access-audit migration
docker exec iams-api-gateway-onprem alembic upgrade head

# 3. Online migration of existing crops
docker exec iams-api-gateway-onprem python -m scripts.migrate_crops_to_minio
# Progress is printed every 500 objects. Safe to Ctrl-C and re-run — idempotent.

# 4. Flip the backend
sed -i '' 's/RECOGNITION_EVIDENCE_BACKEND=filesystem/RECOGNITION_EVIDENCE_BACKEND=minio/' \
    backend/.env.onprem
docker compose -f deploy/docker-compose.onprem.yml restart api-gateway-onprem

# 5. Verify nothing references the filesystem anymore
docker exec iams-postgres-onprem psql -U postgres -d iams \
    -c "SELECT COUNT(*) FROM recognition_events
        WHERE live_crop_ref NOT LIKE 'minio://%'
           OR (registered_crop_ref IS NOT NULL AND registered_crop_ref NOT LIKE 'minio://%');"
# Expect 0. If non-zero, re-run step 3 — migration is idempotent and will catch the stragglers.

# 6. Reap the filesystem volume
docker compose -f deploy/docker-compose.onprem.yml down
docker volume rm iams_iams-crops-onprem
./scripts/onprem-up.sh
```

---

## Troubleshooting

### Events not being captured

1. Is the feature on?
   ```bash
   docker exec iams-api-gateway-onprem env | grep RECOGNITION_EVIDENCE
   ```
   `ENABLE_RECOGNITION_EVIDENCE=true` + `ENABLE_ML=true` both required.

2. Is the session actually recognizing faces (not just seeing boxes)?
   ```bash
   docker logs iams-api-gateway-onprem 2>&1 | grep 'Track.*recognized'
   ```

3. Is the writer queue full?
   ```bash
   docker exec iams-api-gateway-onprem curl -s http://localhost:8000/metrics \
       | grep iams_recognition_events
   ```
   Look for `..._dropped_total > 0`. If so: inspect DB I/O + disk I/O (crops land on same volume).

### Crops on disk but not in DB

The writer lost a DB batch (transient Postgres outage). Crops are orphaned but harmless — the nightly retention job reaps them. If you need to force-reconcile:

```bash
docker exec iams-api-gateway-onprem python -m scripts.reap_orphan_crops
```

### DB rows but no crops on disk

The writer lost a crop I/O batch. Rows are valid, the UI just shows a broken image. Forward fix: set up alerting on `iams_recognition_crop_write_failed_total`. Historical fix: no recovery possible (data is gone); set `live_crop_ref = null` on affected rows so the UI shows a "crop unavailable" placeholder.

### Live panel not updating

1. WS connected?
   Devtools → Network → WS → `/api/v1/ws/attendance/<id>` → frames flowing.
2. Message type filter working?
   Devtools → Console → `localStorage.setItem('iams.debug.ws', '1')` — logs every incoming WS message.
3. Session actually live?
   Hit `GET /api/v1/presence/sessions/active` — schedule_id should be in the list.

### Retention deleted too much

If DRY_RUN was off and you realize too late:
- Rows: unrecoverable (no soft-delete by design — crops are PII and soft-delete leaks).
- Crops: unrecoverable.

Preventive: always start a retention flip with DRY_RUN=true for at least 3 days. The runbook rollout for Phase 4 enforces this.

### MinIO migration stalled

`scripts/migrate_crops_to_minio.py` is idempotent — re-run it. It queries rows `WHERE live_crop_ref NOT LIKE 'minio://%'` and skips ones already migrated. If it hangs on a specific file:

```bash
# Check the offender
docker exec iams-api-gateway-onprem ls -la /var/lib/iams/crops/<date>/ | grep <uuid>

# Skip it explicitly
docker exec iams-api-gateway-onprem python -m scripts.migrate_crops_to_minio --skip <uuid>
```

---

## Rollback

See [DESIGN.md §Rollback](DESIGN.md#rollback). Summary:

| Phase | Rollback |
|---|---|
| 1 | `ENABLE_RECOGNITION_EVIDENCE=false` + restart. No migration undo needed. |
| 2 | `git revert` the panel mount in `live.tsx`. Backend keeps firing WS messages; UI ignores them. |
| 3 | `git revert` the `AttendanceDetailSheet` diff. |
| 4 | `ENABLE_RECOGNITION_EVIDENCE_RETENTION=false` + `git revert` the `/recognitions` route. |
| 5 | `RECOGNITION_EVIDENCE_BACKEND=filesystem`, run the reverse migration script, drop MinIO service. |

Each phase is independently reversible. Rollback depth = how many phases you undo (always from newest).

---

## Operational SLOs (production-ready targets)

Not enforced by code — these are what the runbook operator should keep in mind:

- **Event capture lag**: p95 < 2 s from FAISS decision to visible WS message.
- **Event drop rate**: < 0.1% under normal load.
- **Pipeline fps regression**: 0% — if you see any, the writer is blocking. Check the queue metric.
- **Crop storage growth**: ≤ 1 GB per classroom-month at 30-day retention.
- **Crop view audit gap**: every crop fetch logs. If `SELECT COUNT(*) FROM recognition_access_audit WHERE viewed_at > NOW() - INTERVAL '1 hour'` is 0 and the panel is actively loading crops, the audit middleware is broken — fix before shipping any change.
