"""RPi Camera Gateway configuration — RTSP relay only."""
import os
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

# Reolink RTSP URLs
CAMERA_IP = os.getenv("CAMERA_IP", "192.168.1.100")
CAMERA_USER = os.getenv("CAMERA_USER", "admin")
CAMERA_PASS = os.getenv("CAMERA_PASS", "password")
_PASS_ENC = quote(CAMERA_PASS, safe="")
RTSP_MAIN = f"rtsp://{CAMERA_USER}:{_PASS_ENC}@{CAMERA_IP}:554/h264Preview_01_main"

# VPS mediamtx target
VPS_HOST = os.getenv("VPS_HOST", "167.71.217.44")
VPS_RTSP_URL = f"rtsp://{VPS_HOST}:8554"
ROOM_ID = os.getenv("ROOM_ID", "room-1")

# Transcode mode: "copy" (passthrough) or "transcode" (re-encode on RPi).
# Use "transcode" for cameras like the CX810 that produce bursty/problematic
# H.264 streams even with identical settings.
RELAY_MODE = os.getenv("RELAY_MODE", "copy")

# Transcode settings (only used when RELAY_MODE=transcode)
TRANSCODE_RESOLUTION = os.getenv("TRANSCODE_RESOLUTION", "1280x720")
TRANSCODE_BITRATE = os.getenv("TRANSCODE_BITRATE", "2500k")
TRANSCODE_MAX_BITRATE = os.getenv("TRANSCODE_MAX_BITRATE", "3000k")
TRANSCODE_FPS = os.getenv("TRANSCODE_FPS", "20")
