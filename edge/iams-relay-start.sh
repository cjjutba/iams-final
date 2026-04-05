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
WATCHDOG_INTERVAL=30    # Check every 30 seconds
MIN_TX_BYTES=10000      # Minimum TX bytes per interval (stream should do ~50KB+/s)

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

# Main loop
while true; do
    run_ffmpeg
    echo "IAMS Relay: FFmpeg started (PID ${FFMPEG_PID})"

    # Give FFmpeg time to connect to camera + VPS before watchdog starts
    sleep 20

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
    done

    wait "${FFMPEG_PID}" 2>/dev/null
    EXIT_CODE=$?
    echo "IAMS Relay: FFmpeg exited (code ${EXIT_CODE}), restarting in ${RETRY_DELAY}s..."
    sleep "${RETRY_DELAY}"
done
