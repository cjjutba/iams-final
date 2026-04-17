#!/bin/bash
# IAMS Relay startup script — reads env vars and builds FFmpeg command.
# Supports RELAY_MODE=copy (default) or RELAY_MODE=transcode.
#
# Includes:
# - Automatic reconnection on FFmpeg exit
# - Watchdog that kills FFmpeg if network TX stops (stream died silently)
set -uo pipefail

SOURCE="${CAMERA_RTSP_URL}"
TARGET="${VPS_RTSP_URL}/${ROOM_ID}"
MODE="${RELAY_MODE:-copy}"
RETRY_DELAY=5
MAX_RETRY_DELAY=60      # Cap backoff at 60 seconds
WATCHDOG_INTERVAL=30    # Check every 30 seconds
MIN_TX_BYTES=10000      # Minimum TX bytes per interval (stream should do ~50KB+/s)
CONSECUTIVE_FAILURES=0

FFMPEG_PID=""

cleanup() {
    if [ -n "${FFMPEG_PID}" ] && kill -0 "${FFMPEG_PID}" 2>/dev/null; then
        kill "${FFMPEG_PID}" 2>/dev/null
        wait "${FFMPEG_PID}" 2>/dev/null
    fi
}
trap cleanup EXIT

get_tx_bytes() {
    cat /sys/class/net/wlan0/statistics/tx_bytes 2>/dev/null || echo "0"
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
    if ping -c 1 -W 2 "${VPS_RTSP_URL#rtsp://}" 2>/dev/null | grep -q "1 received" 2>/dev/null; then
        break
    fi
    # Fallback: just check if we have a default route
    if ip route show default 2>/dev/null | grep -q "default"; then
        break
    fi
    sleep 2
done
echo "IAMS Relay: Network ready"

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

    # If we got past the initial 20s, FFmpeg connected successfully — reset backoff
    if kill -0 "${FFMPEG_PID}" 2>/dev/null; then
        CONSECUTIVE_FAILURES=0
    fi

    PREV_TX=$(get_tx_bytes)

    # Watchdog loop — monitors TX bytes to detect silent stream death
    while kill -0 "${FFMPEG_PID}" 2>/dev/null; do
        sleep "${WATCHDOG_INTERVAL}"

        if ! kill -0 "${FFMPEG_PID}" 2>/dev/null; then
            break
        fi

        CURR_TX=$(get_tx_bytes)
        TX_DIFF=$((CURR_TX - PREV_TX))
        PREV_TX=${CURR_TX}

        if [ "${TX_DIFF}" -lt "${MIN_TX_BYTES}" ]; then
            echo "IAMS Relay: Watchdog — TX stalled (${TX_DIFF} bytes in ${WATCHDOG_INTERVAL}s), restarting"
            kill "${FFMPEG_PID}" 2>/dev/null
            wait "${FFMPEG_PID}" 2>/dev/null
            break
        fi

        # Reset failure count — stream is actively transmitting
        CONSECUTIVE_FAILURES=0
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
