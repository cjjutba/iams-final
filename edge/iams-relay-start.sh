#!/bin/bash
# IAMS Relay startup script — reads env vars and builds FFmpeg command.
# Supports RELAY_MODE=copy (default) or RELAY_MODE=transcode.
#
# Includes automatic reconnection: if FFmpeg exits (broken pipe, camera
# disconnect, etc.) the script restarts it after a short delay, without
# waiting for systemd's slower RestartSec cycle.
set -uo pipefail

SOURCE="${CAMERA_RTSP_URL}"
TARGET="${VPS_RTSP_URL}/${ROOM_ID}"
MODE="${RELAY_MODE:-copy}"
RETRY_DELAY=3

run_ffmpeg() {
    if [ "${MODE}" = "transcode" ]; then
        # Re-encode for cameras with problematic H.264 output (e.g. CX810).
        # Error recovery flags handle the CX810's bursty/corrupt frames:
        #   -err_detect ignore_err   → don't abort on bitstream errors
        #   +discardcorrupt          → silently drop corrupt input packets
        #   -ec deblock              → conceal errors with deblocking filter
        RES="${TRANSCODE_RESOLUTION:-1280x720}"
        BR="${TRANSCODE_BITRATE:-2500k}"
        MAXBR="${TRANSCODE_MAX_BITRATE:-3000k}"
        FPS="${TRANSCODE_FPS:-20}"
        GOP=$(( FPS * 2 ))  # Keyframe every 2 seconds

        echo "IAMS Relay: transcode mode — ${RES} @ ${BR} (max ${MAXBR}), ${FPS}fps"
        /usr/bin/ffmpeg \
            -hide_banner -loglevel warning \
            -fflags +nobuffer+discardcorrupt+genpts \
            -flags low_delay \
            -err_detect ignore_err \
            -probesize 500000 \
            -analyzeduration 500000 \
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
            "${TARGET}"
    else
        echo "IAMS Relay: copy mode (passthrough)"
        /usr/bin/ffmpeg \
            -hide_banner -loglevel warning \
            -fflags +nobuffer+discardcorrupt+genpts \
            -flags low_delay \
            -err_detect ignore_err \
            -probesize 500000 \
            -analyzeduration 500000 \
            -rtsp_transport tcp \
            -use_wallclock_as_timestamps 1 \
            -i "${SOURCE}" \
            -c copy \
            -an \
            -f rtsp \
            -rtsp_transport tcp \
            -muxdelay 0 \
            "${TARGET}"
    fi
}

# Reconnection loop — restarts FFmpeg on exit without waiting for systemd.
# systemd RestartSec is the outer safety net; this inner loop is faster.
while true; do
    run_ffmpeg
    EXIT_CODE=$?
    echo "IAMS Relay: FFmpeg exited with code ${EXIT_CODE}, restarting in ${RETRY_DELAY}s..."
    sleep "${RETRY_DELAY}"
done
