#!/bin/bash
# IAMS Relay startup script — reads env vars and builds FFmpeg command.
# Supports RELAY_MODE=copy (default) or RELAY_MODE=transcode.
#
# Includes:
# - Automatic reconnection on FFmpeg exit
# - Watchdog that kills FFmpeg if the VPS stream goes stale
set -uo pipefail

SOURCE="${CAMERA_RTSP_URL}"
TARGET="${VPS_RTSP_URL}/${ROOM_ID}"
MODE="${RELAY_MODE:-copy}"
RETRY_DELAY=5
WATCHDOG_INTERVAL=30    # Check stream health every 30 seconds
WATCHDOG_TIMEOUT=10     # ffprobe timeout for health check

FFMPEG_PID=""

cleanup() {
    if [ -n "${FFMPEG_PID}" ] && kill -0 "${FFMPEG_PID}" 2>/dev/null; then
        kill "${FFMPEG_PID}" 2>/dev/null
        wait "${FFMPEG_PID}" 2>/dev/null
    fi
}
trap cleanup EXIT

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

# Check if the stream is actually reachable at VPS mediamtx
check_stream_health() {
    # Use ffprobe to verify the stream exists at the target URL
    timeout "${WATCHDOG_TIMEOUT}" ffprobe -v quiet -i "${TARGET}" -show_entries format=duration -of csv=p=0 >/dev/null 2>&1
    return $?
}

# Main loop
while true; do
    run_ffmpeg
    echo "IAMS Relay: FFmpeg started (PID ${FFMPEG_PID})"

    # Wait for FFmpeg to connect and publish (give it time to probe + start)
    sleep 15

    # Watchdog loop — runs while FFmpeg is alive
    while kill -0 "${FFMPEG_PID}" 2>/dev/null; do
        sleep "${WATCHDOG_INTERVAL}"

        # Skip check if FFmpeg already died
        if ! kill -0 "${FFMPEG_PID}" 2>/dev/null; then
            break
        fi

        # Check if stream is actually arriving at VPS
        if ! check_stream_health; then
            echo "IAMS Relay: Watchdog — stream not reachable at VPS, killing FFmpeg"
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
