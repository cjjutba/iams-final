#!/bin/bash
# =============================================================================
# IAMS — Build local debug APKs for the admin landing page
#
# Builds both Android modules (:app-student + :app-faculty) as DEBUG APKs and
# copies them to admin/public/iams-student.apk + admin/public/iams-faculty.apk.
#
# Once these files exist:
#   - Vite dev (http://localhost:5173/) → public-dir middleware serves them
#     directly. The /iams-*.apk proxy bypass in admin/vite.config.ts skips the
#     VPS fallback when the local file is present, so the Download buttons on
#     the landing page give you the freshest local build.
#   - On-prem nginx (http://192.168.88.17/) → after a `vite build --mode
#     onprem` (the admin-build sidecar runs this on `onprem-up.sh`), the
#     APKs land in the dist that nginx serves. The on-prem nginx config uses
#     try_files for /iams-*.apk, so it picks up the local file before falling
#     through to the VPS proxy.
#
# Usage:
#   ./scripts/build-local-apks.sh             # build both (debug)
#   ./scripts/build-local-apks.sh student     # only student APK
#   ./scripts/build-local-apks.sh faculty     # only faculty APK
#
# Notes:
#   - Debug APKs are unsigned with the dev keystore; install via
#     `Settings → Allow unknown apps`. They install over each other (same
#     applicationIds as release: com.iams.app.student / com.iams.app.faculty).
#   - The output files are gitignored; nothing is committed.
#   - Production deploys (Vercel + VPS) use signed RELEASE APKs from the
#     `Build & Release APKs` GitHub Actions workflow — this script does NOT
#     replace that pipeline; it's purely for the local-dev download flow.
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID_DIR="${PROJECT_DIR}/android"
PUBLIC_DIR="${PROJECT_DIR}/admin/public"

mkdir -p "${PUBLIC_DIR}"

WHICH="${1:-both}"
case "${WHICH}" in
    both|student|faculty) ;;
    *)
        echo "ERROR: unknown target '${WHICH}'. Use 'both', 'student', or 'faculty'." >&2
        exit 2
        ;;
esac

build_module() {
    local module="$1"               # app-student | app-faculty
    local out_name="$2"             # iams-student.apk | iams-faculty.apk

    local apk_src="${ANDROID_DIR}/${module}/build/outputs/apk/debug/${module}-debug.apk"
    local apk_dst="${PUBLIC_DIR}/${out_name}"

    echo ""
    echo "  → Building :${module}:assembleDebug ..."
    ( cd "${ANDROID_DIR}" && ./gradlew ":${module}:assembleDebug" --console=plain )

    if [ ! -f "${apk_src}" ]; then
        echo "ERROR: expected APK not found at ${apk_src}" >&2
        ls -la "${ANDROID_DIR}/${module}/build/outputs/apk/debug/" 2>/dev/null || true
        exit 3
    fi

    cp -f "${apk_src}" "${apk_dst}"
    local size_bytes
    size_bytes=$(stat -f%z "${apk_dst}" 2>/dev/null || stat -c%s "${apk_dst}")
    local size_mib=$(( size_bytes / 1024 / 1024 ))
    echo "    OK: ${apk_dst}  (${size_mib} MiB)"
}

echo "========================================"
echo "  IAMS — Local APK build (debug)"
echo "  Output: ${PUBLIC_DIR}"
echo "========================================"

if [ "${WHICH}" = "both" ] || [ "${WHICH}" = "student" ]; then
    build_module "app-student" "iams-student.apk"
fi

if [ "${WHICH}" = "both" ] || [ "${WHICH}" = "faculty" ]; then
    build_module "app-faculty" "iams-faculty.apk"
fi

echo ""
echo "========================================"
echo "  Local APKs ready."
echo "========================================"
echo ""
echo "  Reload http://localhost:5173/ — Download buttons now serve local builds."
echo ""
echo "  To revert to the VPS production APKs, just delete the files:"
echo "    rm ${PUBLIC_DIR}/iams-student.apk ${PUBLIC_DIR}/iams-faculty.apk"
echo ""
