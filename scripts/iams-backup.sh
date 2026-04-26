#!/bin/bash
# IAMS — nightly encrypted backup of the on-prem postgres DB.
#
# Triggered by the com.iams.backup launchd agent installed by
# scripts/install-backup.sh. NEVER run manually — see the install script
# header for the operator-side flow.
#
# What it does, in order:
#
#   1. Source secrets from scripts/.env.local (POSTGRES_PASSWORD,
#      IAMS_BACKUP_GPG_PASSPHRASE).
#   2. ``docker exec`` ``pg_dump`` against the running iams-postgres-onprem
#      container (full DB — every table, including the irreplaceable
#      face embeddings + attendance + presence rows).
#   3. Pipe the dump through gzip -9, then through ``gpg --symmetric
#      --cipher-algo AES256``. Plaintext never lands on disk.
#   4. Write the encrypted blob to ${IAMS_BACKUP_DIR}/iams-<timestamp>.sql.gz.gpg
#      (default: ~/iams-backups).
#   5. scp the same file to the VPS as a secondary off-machine copy
#      (best-effort — local copy still produced if the VPS is down).
#   6. Prune both sides of dumps older than IAMS_BACKUP_RETENTION_DAYS
#      (default 14).
#
# Why local + VPS instead of S3/B2:
#   - Zero new infra. The VPS is already managed; SSH already works.
#   - Different physical machine + different country/ISP from the Mac, so
#     a Mac drive / power / fire failure doesn't lose the backup.
#   - Encryption is end-to-end: the VPS holds AES-256 ciphertext, never
#     plaintext PII. If the VPS were ever compromised, dumps are useless
#     without the GPG passphrase (kept in the operator's password
#     manager, not on either machine).
#   - When you want true off-site (B2/S3/Spaces), swap the scp block for
#     an aws s3 cp / b2 upload-file. Same script.
#
# Restore:
#   gpg --decrypt iams-2026-04-26_030000.sql.gz.gpg | gunzip \
#     | docker exec -i iams-postgres-onprem psql -U iams iams
#
# Logs (stdout + stderr): ~/Library/Logs/iams-backup.log
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="${HOME}/Library/Logs/iams-backup.log"

# Logging — append everything to a single log so launchd's StandardOut/
# ErrorPath redirects keep the operator's `tail -f` view stable.
mkdir -p "$(dirname "${LOG_FILE}")"
exec >> "${LOG_FILE}" 2>&1

echo
echo "===== IAMS backup starting: $(date '+%Y-%m-%d %H:%M:%S %Z') ====="

# ── Secrets ───────────────────────────────────────────────────────────
if [ ! -f "${PROJECT_DIR}/scripts/.env.local" ]; then
  echo "FATAL: scripts/.env.local missing. Copy from .env.local.example and"
  echo "       set IAMS_BACKUP_GPG_PASSPHRASE."
  exit 2
fi
# shellcheck disable=SC1091
set -a
. "${PROJECT_DIR}/scripts/.env.local"
set +a

if [ -z "${IAMS_BACKUP_GPG_PASSPHRASE:-}" ]; then
  echo "FATAL: IAMS_BACKUP_GPG_PASSPHRASE is empty. Set it in scripts/.env.local."
  echo "       Pick a strong passphrase and store it in your password manager —"
  echo "       without it, your backups are unrecoverable."
  exit 3
fi

# ── Tooling preconditions ─────────────────────────────────────────────
GPG_BIN="${IAMS_BACKUP_GPG_BIN:-/opt/homebrew/bin/gpg}"
if [ ! -x "${GPG_BIN}" ] && command -v gpg >/dev/null 2>&1; then
  GPG_BIN="$(command -v gpg)"
fi
if [ ! -x "${GPG_BIN}" ]; then
  echo "FATAL: gpg not found at ${GPG_BIN}. Install via 'brew install gnupg'."
  exit 4
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "FATAL: docker CLI not found in PATH. launchd's PATH is minimal —"
  echo "       set IAMS_BACKUP_DOCKER_BIN in scripts/.env.local or symlink"
  echo "       /usr/local/bin/docker."
  exit 5
fi
DOCKER_BIN="${IAMS_BACKUP_DOCKER_BIN:-$(command -v docker)}"

if ! "${DOCKER_BIN}" ps --filter name=iams-postgres-onprem --filter status=running -q | grep -q .; then
  echo "FATAL: iams-postgres-onprem container is not running. Bring up"
  echo "       the on-prem stack first: ./scripts/onprem-up.sh"
  exit 6
fi

# ── Local dump ────────────────────────────────────────────────────────
BACKUP_DIR="${IAMS_BACKUP_DIR:-${HOME}/iams-backups}"
mkdir -p "${BACKUP_DIR}"

TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"
DUMP_FILE="${BACKUP_DIR}/iams-${TIMESTAMP}.sql.gz.gpg"
DUMP_TMP="${DUMP_FILE}.tmp"

echo "[1/4] Dumping iams-postgres-onprem → gzip → gpg → ${DUMP_FILE}"

# pg_dump runs inside the container as the iams user. ``--no-owner``
# and ``--no-acl`` strip role grants so the dump can be restored into
# a fresh DB on a different machine without ALTER ROLE failures.
# ``--clean --if-exists`` is intentionally omitted: a restore is rare
# enough that the operator should opt in to drops manually.
#
# Pipeline: pg_dump → gzip → gpg. ``set -o pipefail`` (top of script)
# means a failure in any stage propagates. Plaintext exists only in
# the kernel's pipe buffers — never on disk.
if ! "${DOCKER_BIN}" exec -i iams-postgres-onprem pg_dump \
        --username=iams \
        --dbname=iams \
        --format=plain \
        --no-owner \
        --no-acl \
      | gzip -9 \
      | "${GPG_BIN}" --batch --yes --quiet \
            --pinentry-mode loopback \
            --symmetric --cipher-algo AES256 \
            --passphrase "${IAMS_BACKUP_GPG_PASSPHRASE}" \
            -o "${DUMP_TMP}"; then
  echo "ERROR: dump pipeline failed. Removing partial output."
  rm -f "${DUMP_TMP}"
  exit 7
fi

# Atomic rename so a half-written file is never visible to scp / pruner.
mv "${DUMP_TMP}" "${DUMP_FILE}"

if [ ! -s "${DUMP_FILE}" ]; then
  echo "ERROR: encrypted dump is empty — refusing to claim success."
  rm -f "${DUMP_FILE}"
  exit 8
fi

DUMP_SIZE="$(du -h "${DUMP_FILE}" | cut -f1)"
echo "  Local dump complete: ${DUMP_FILE} (${DUMP_SIZE})"

# ── Off-site copy (best-effort) ───────────────────────────────────────
VPS_HOST="${IAMS_BACKUP_VPS_HOST:-root@167.71.217.44}"
VPS_DIR="${IAMS_BACKUP_VPS_DIR:-/var/backups/iams}"
SSH_OPTS="-o ConnectTimeout=10 -o ServerAliveInterval=15 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

echo "[2/4] Pushing off-site copy → ${VPS_HOST}:${VPS_DIR}/"
# shellcheck disable=SC2086
if ssh ${SSH_OPTS} "${VPS_HOST}" "mkdir -p ${VPS_DIR}" 2>/dev/null; then
  # shellcheck disable=SC2086
  if scp ${SSH_OPTS} "${DUMP_FILE}" "${VPS_HOST}:${VPS_DIR}/"; then
    echo "  Off-site copy uploaded."
  else
    echo "  WARN: scp failed — local copy still exists at ${DUMP_FILE}."
  fi
else
  echo "  WARN: VPS unreachable (${VPS_HOST}). Off-site copy SKIPPED."
  echo "        Local copy is at ${DUMP_FILE} — try again next run."
fi

# ── Retention ─────────────────────────────────────────────────────────
RETENTION_DAYS="${IAMS_BACKUP_RETENTION_DAYS:-14}"

echo "[3/4] Pruning local dumps older than ${RETENTION_DAYS} days"
# -mtime is in 24h units. ``-mtime +N`` matches ``modified more than N×24h ago``.
PRUNED_LOCAL=$(find "${BACKUP_DIR}" -maxdepth 1 -name 'iams-*.sql.gz.gpg' -mtime +${RETENTION_DAYS} -print -delete | wc -l | tr -d ' ')
echo "  Pruned ${PRUNED_LOCAL} local file(s)."

echo "[4/4] Pruning VPS dumps older than ${RETENTION_DAYS} days"
# shellcheck disable=SC2086
if ssh ${SSH_OPTS} "${VPS_HOST}" \
      "find ${VPS_DIR} -maxdepth 1 -name 'iams-*.sql.gz.gpg' -mtime +${RETENTION_DAYS} -print -delete 2>/dev/null | wc -l" 2>/dev/null \
   | tr -d ' \n' | { read -r n || true; echo "  Pruned ${n:-0} VPS file(s)."; }; then
  :
else
  echo "  WARN: VPS prune failed — non-fatal."
fi

echo "===== IAMS backup completed: $(date '+%Y-%m-%d %H:%M:%S %Z') ====="
