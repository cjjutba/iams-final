#!/bin/bash
# =============================================================================
# Dev Stream — simulate RPi relay for local development
#
# Pushes a video source to local mediamtx via RTSP, mimicking exactly
# what the RPi FFmpeg relay does in production. The backend pulls from
# mediamtx for recognition, WebRTC serves video to mobile — same pipeline.
#
# Usage:
#   bash backend/scripts/dev-stream.sh webcam    # MacBook camera
#   bash backend/scripts/dev-stream.sh camera    # Reolink (same WiFi)
#   bash backend/scripts/dev-stream.sh video     # Loop a test video file
#   bash backend/scripts/dev-stream.sh           # Default: webcam
#
# Prerequisites:
#   - Backend running (python run.py) — it auto-starts mediamtx
#   - FFmpeg installed (brew install ffmpeg)
# =============================================================================

set -euo pipefail

# Room ID — must match a schedule's room_id in the database
ROOM_ID="${ROOM_ID:-36168673-34de-4c64-8ace-c6b72cbaba3f}"

# Local mediamtx RTSP endpoint (backend starts this automatically)
MEDIAMTX_URL="rtsp://localhost:8554"

# Reolink camera (when on the same WiFi network)
CAMERA_RTSP_URL="${CAMERA_RTSP_URL:-rtsp://admin:Iams2026THESIS@192.168.1.100:554/h264Preview_01_sub}"

# Test video file (for 'video' mode)
TEST_VIDEO="${TEST_VIDEO:-}"

MODE="${1:-webcam}"

echo "========================================"
echo "  IAMS Dev Stream"
echo "  Mode: ${MODE}"
echo "  Target: ${MEDIAMTX_URL}/${ROOM_ID}"
echo "========================================"

case "${MODE}" in
  webcam)
    echo ""
    echo "Streaming MacBook camera to local mediamtx..."
    echo "Press Ctrl+C to stop."
    echo ""

    # List available devices (for reference)
    # ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep -E "^\[" || true

    ffmpeg \
      -hide_banner -loglevel warning \
      -f avfoundation \
      -framerate 15 \
      -video_size 640x480 \
      -i "0" \
      -c:v libx264 \
      -preset ultrafast \
      -tune zerolatency \
      -g 30 \
      -an \
      -f rtsp \
      -rtsp_transport tcp \
      "${MEDIAMTX_URL}/${ROOM_ID}"
    ;;

  camera)
    echo ""
    echo "Relaying Reolink camera to local mediamtx..."
    echo "Make sure you're on the same WiFi as the camera (192.168.1.x)."
    echo "Press Ctrl+C to stop."
    echo ""

    # Same command as the RPi relay (production)
    ffmpeg \
      -hide_banner -loglevel warning \
      -rtsp_transport tcp \
      -use_wallclock_as_timestamps 1 \
      -i "${CAMERA_RTSP_URL}" \
      -c copy \
      -an \
      -f rtsp \
      -rtsp_transport tcp \
      "${MEDIAMTX_URL}/${ROOM_ID}"
    ;;

  video)
    if [ -z "${TEST_VIDEO}" ]; then
      echo ""
      echo "ERROR: No video file specified."
      echo "Usage: TEST_VIDEO=path/to/video.mp4 bash backend/scripts/dev-stream.sh video"
      echo ""
      exit 1
    fi

    if [ ! -f "${TEST_VIDEO}" ]; then
      echo "ERROR: Video file not found: ${TEST_VIDEO}"
      exit 1
    fi

    echo ""
    echo "Looping video file to local mediamtx..."
    echo "File: ${TEST_VIDEO}"
    echo "Press Ctrl+C to stop."
    echo ""

    ffmpeg \
      -hide_banner -loglevel warning \
      -stream_loop -1 \
      -re \
      -i "${TEST_VIDEO}" \
      -c:v libx264 \
      -preset ultrafast \
      -tune zerolatency \
      -g 30 \
      -an \
      -f rtsp \
      -rtsp_transport tcp \
      "${MEDIAMTX_URL}/${ROOM_ID}"
    ;;

  *)
    echo "Unknown mode: ${MODE}"
    echo ""
    echo "Usage: bash backend/scripts/dev-stream.sh [webcam|camera|video]"
    echo ""
    echo "  webcam  — MacBook camera (default)"
    echo "  camera  — Reolink camera (requires same WiFi)"
    echo "  video   — Loop a test video file (set TEST_VIDEO=path)"
    echo ""
    exit 1
    ;;
esac
