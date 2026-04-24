#!/bin/bash
# IAMS Relay startup script — reads env vars and builds FFmpeg command.
# Supports RELAY_MODE=copy (default) or RELAY_MODE=transcode.
#
# Hardening (2026-04-19) — three independent stall detectors, any one of which
# will force FFmpeg to exit so systemd (+ this script's retry loop) can restart:
#
#   1. FFmpeg `-rw_timeout 15s` on the RTSP output. If a TCP write to mediamtx
#      blocks for >15s, FFmpeg errors out and exits.
#
#   2. Per-socket state check. Every 15s, `ss` is queried for FFmpeg's output
#      socket to VPS:8554. If the state is not ESTAB (e.g. CLOSE-WAIT, which
#      is what silently broke EB227 for 19h on 2026-04-18), we kill FFmpeg.
#      This catches the case where mediamtx sent FIN but FFmpeg's socket layer
#      never noticed.
#
#   3. Per-socket bytes_sent delta. If the TCP socket is ESTAB but FFmpeg
#      isn't actually pushing bytes through it (~50KB+/s expected from a copy
#      passthrough of the Reolink sub stream), kill FFmpeg.
#
# The old wlan0 tx_bytes watchdog was dropped because background traffic (SSH,
# mDNS, NTP) masked stalled streams — exactly how the 19h outage went
# undetected on EB227.
set -uo pipefail

SOURCE="${CAMERA_RTSP_URL}"
MODE="${RELAY_MODE:-copy}"

# Relay target: prefer RELAY_RTSP_URL (new post-2026-04-21 split), fall back to
# RELAY_HOST → VPS_RTSP_URL → VPS_HOST for backward compatibility with
# already-deployed RPi .env files.
if [ -n "${RELAY_RTSP_URL:-}" ]; then
    TARGET_URL="${RELAY_RTSP_URL}"
elif [ -n "${RELAY_HOST:-}" ]; then
    TARGET_URL="rtsp://${RELAY_HOST}:8554"
elif [ -n "${VPS_RTSP_URL:-}" ]; then
    TARGET_URL="${VPS_RTSP_URL}"
elif [ -n "${VPS_HOST:-}" ]; then
    TARGET_URL="rtsp://${VPS_HOST}:8554"
else
    echo "ERROR: no RELAY_HOST / RELAY_RTSP_URL / VPS_HOST / VPS_RTSP_URL set." >&2
    exit 1
fi

TARGET="${TARGET_URL}/${ROOM_ID}"

# Parse host/port for the downstream watchdog `ss -tnpi` probe.
RELAY_HOSTPORT="${TARGET_URL#rtsp://}"
RELAY_HOSTPORT="${RELAY_HOSTPORT%%/*}"
VPS_HOST="${RELAY_HOSTPORT%%:*}"
VPS_PORT="${RELAY_HOSTPORT##*:}"
if [ "${VPS_PORT}" = "${RELAY_HOSTPORT}" ] || [ -z "${VPS_PORT}" ]; then
    VPS_PORT="8554"
fi

RETRY_DELAY=5
MAX_RETRY_DELAY=60                    # Cap backoff at 60 seconds
WATCHDOG_INTERVAL=15                  # Check every 15 seconds
MIN_OUTPUT_BYTES_PER_INTERVAL=5000    # ~333 B/s floor (sub-stream idle scenes
                                      # observed at ~5 KB/s, so this leaves
                                      # plenty of headroom against false kills)
STALL_STRIKES_TO_KILL=2               # Need 2 consecutive low-byte intervals
                                      # (≥30s of no useful TX) before killing
RW_TIMEOUT_USEC=15000000              # 15s — FFmpeg exits if TCP write blocks
CONSECUTIVE_FAILURES=0

FFMPEG_PID=""

cleanup() {
    if [ -n "${FFMPEG_PID}" ] && kill -0 "${FFMPEG_PID}" 2>/dev/null; then
        kill "${FFMPEG_PID}" 2>/dev/null
        wait "${FFMPEG_PID}" 2>/dev/null
    fi
}
trap cleanup EXIT

# Returns 0 (healthy) if FFmpeg's output socket to VPS:PORT is in ESTAB state,
# 1 otherwise. Non-ESTAB states include CLOSE-WAIT, FIN-WAIT-*, LAST-ACK, and
# "socket not found" — all of which mean the publish is broken.
check_output_socket_estab() {
    local state
    state=$(ss -tnp state all 2>/dev/null \
            | awk -v pid="pid=${FFMPEG_PID}," -v port=":${VPS_PORT}" '
                $0 ~ pid && $5 ~ port"$" { print $1; exit }')
    [ "${state}" = "ESTAB" ]
}

# Emits the TCP_INFO bytes_sent counter for FFmpeg's output socket, or "0" if
# the socket can't be located. Used to detect ESTAB-but-stalled writes.
get_output_bytes_sent() {
    ss -tnpi state all 2>/dev/null \
        | awk -v pid="pid=${FFMPEG_PID}," -v port=":${VPS_PORT}" '
            $0 ~ pid && $5 ~ port"$" { found=1; next }
            found {
                n = match($0, /bytes_sent:[0-9]+/)
                if (n > 0) {
                    print substr($0, RSTART+11, RLENGTH-11)
                    exit
                }
            }
            END { if (!found) print "0" }'
}

run_ffmpeg() {
    if [ "${MODE}" = "transcode" ]; then
        RES="${TRANSCODE_RESOLUTION:-1280x720}"
        BR="${TRANSCODE_BITRATE:-2500k}"
        MAXBR="${TRANSCODE_MAX_BITRATE:-3000k}"
        FPS="${TRANSCODE_FPS:-20}"
        GOP=$(( FPS * 2 ))

        echo "IAMS Relay: transcode mode — ${RES} @ ${BR} (max ${MAXBR}), ${FPS}fps"
        /usr/bin/ffmpeg \
            -hide_banner -loglevel warning \
            -fflags +nobuffer+discardcorrupt+genpts \
            -flags low_delay \
            -err_detect ignore_err \
            -probesize 1000000 \
            -analyzeduration 1000000 \
            -rtsp_transport tcp \
            -use_wallclock_as_timestamps 1 \
            -i "${SOURCE}" \
            -c:v libx264 \
            -preset ultrafast \
            -tune zerolatency \
            -profile:v baseline \
            -b:v "${BR}" \
            -maxrate "${MAXBR}" \
            -bufsize 1500k \
            -s "${RES}" \
            -r "${FPS}" \
            -g "${GOP}" \
            -an \
            -rw_timeout "${RW_TIMEOUT_USEC}" \
            -f rtsp \
            -rtsp_transport tcp \
            -muxdelay 0 \
            "${TARGET}" &
    else
        echo "IAMS Relay: copy mode (passthrough)"
        /usr/bin/ffmpeg \
            -hide_banner -loglevel warning \
            -fflags +nobuffer+discardcorrupt+genpts \
            -flags low_delay \
            -err_detect ignore_err \
            -probesize 1000000 \
            -analyzeduration 1000000 \
            -rtsp_transport tcp \
            -use_wallclock_as_timestamps 1 \
            -i "${SOURCE}" \
            -c copy \
            -an \
            -rw_timeout "${RW_TIMEOUT_USEC}" \
            -f rtsp \
            -rtsp_transport tcp \
            -muxdelay 0 \
            "${TARGET}" &
    fi
    FFMPEG_PID=$!
}

# Wait for network to be fully up (WiFi may take a few seconds after boot)
echo "IAMS Relay: Waiting for network..."
for i in $(seq 1 30); do
    if ping -c 1 -W 2 "${VPS_HOST}" 2>/dev/null | grep -q "1 received" 2>/dev/null; then
        break
    fi
    if ip route show default 2>/dev/null | grep -q "default"; then
        break
    fi
    sleep 2
done
echo "IAMS Relay: Network ready (VPS ${VPS_HOST}:${VPS_PORT})"

# Truncate log file if it's over 10MB to prevent filling the SD card
LOG_FILE="${HOME}/iams-relay.log"
if [ -f "${LOG_FILE}" ]; then
    LOG_SIZE=$(stat -c%s "${LOG_FILE}" 2>/dev/null || stat -f%z "${LOG_FILE}" 2>/dev/null || echo "0")
    if [ "${LOG_SIZE}" -gt 10485760 ]; then
        tail -1000 "${LOG_FILE}" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "${LOG_FILE}"
        echo "IAMS Relay: Log truncated (was ${LOG_SIZE} bytes)"
    fi
fi

# Main loop with exponential backoff
while true; do
    run_ffmpeg
    echo "IAMS Relay: FFmpeg started (PID ${FFMPEG_PID})"

    # Give FFmpeg time to connect to camera + VPS before watchdog starts
    sleep 20

    if kill -0 "${FFMPEG_PID}" 2>/dev/null; then
        CONSECUTIVE_FAILURES=0
    fi

    PREV_SENT=$(get_output_bytes_sent)
    STALL_STRIKES=0

    # Watchdog — precise per-socket health check
    while kill -0 "${FFMPEG_PID}" 2>/dev/null; do
        sleep "${WATCHDOG_INTERVAL}"

        if ! kill -0 "${FFMPEG_PID}" 2>/dev/null; then
            break
        fi

        # Check 1: output socket must be ESTAB (catches CLOSE-WAIT stalls
        # like the EB227 19h outage on 2026-04-18). Fires immediately — any
        # non-ESTAB state on the publish socket is never recoverable.
        if ! check_output_socket_estab; then
            echo "IAMS Relay: Watchdog — output socket to ${VPS_HOST}:${VPS_PORT} not ESTAB, restarting FFmpeg"
            kill "${FFMPEG_PID}" 2>/dev/null
            wait "${FFMPEG_PID}" 2>/dev/null
            break
        fi

        # Check 2: bytes_sent must advance (catches ESTAB-but-no-data stalls).
        # Requires STALL_STRIKES_TO_KILL consecutive low intervals before
        # firing, so brief I-frame gaps don't cause false kills.
        CURR_SENT=$(get_output_bytes_sent)
        SENT_DIFF=$(( CURR_SENT - PREV_SENT ))
        PREV_SENT=${CURR_SENT}

        if [ "${SENT_DIFF}" -lt "${MIN_OUTPUT_BYTES_PER_INTERVAL}" ]; then
            STALL_STRIKES=$(( STALL_STRIKES + 1 ))
            echo "IAMS Relay: Watchdog — low TX (${SENT_DIFF} bytes in ${WATCHDOG_INTERVAL}s), strike ${STALL_STRIKES}/${STALL_STRIKES_TO_KILL}"
            if [ "${STALL_STRIKES}" -ge "${STALL_STRIKES_TO_KILL}" ]; then
                echo "IAMS Relay: Watchdog — output TX stalled, restarting FFmpeg"
                kill "${FFMPEG_PID}" 2>/dev/null
                wait "${FFMPEG_PID}" 2>/dev/null
                break
            fi
        else
            STALL_STRIKES=0
        fi
    done

    wait "${FFMPEG_PID}" 2>/dev/null
    EXIT_CODE=$?
    CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))

    # Exponential backoff: 5s, 10s, 20s, 40s, capped at 60s
    CURRENT_DELAY=$((RETRY_DELAY * (2 ** (CONSECUTIVE_FAILURES - 1))))
    if [ "${CURRENT_DELAY}" -gt "${MAX_RETRY_DELAY}" ]; then
        CURRENT_DELAY=${MAX_RETRY_DELAY}
    fi

    echo "IAMS Relay: FFmpeg exited (code ${EXIT_CODE}), attempt ${CONSECUTIVE_FAILURES}, retrying in ${CURRENT_DELAY}s..."
    sleep "${CURRENT_DELAY}"
done
