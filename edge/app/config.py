"""RPi Camera Gateway configuration."""
import os
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

# Reolink P340 RTSP URLs
CAMERA_IP = os.getenv("CAMERA_IP", "192.168.1.100")
CAMERA_USER = os.getenv("CAMERA_USER", "admin")
CAMERA_PASS = os.getenv("CAMERA_PASS", "password")
_PASS_ENC = quote(CAMERA_PASS, safe="")
RTSP_MAIN = f"rtsp://{CAMERA_USER}:{_PASS_ENC}@{CAMERA_IP}:554/h264Preview_01_main"
RTSP_SUB = f"rtsp://{CAMERA_USER}:{_PASS_ENC}@{CAMERA_IP}:554/h264Preview_01_sub"

# VPS connection
VPS_HOST = os.getenv("VPS_HOST", "167.71.217.44")
VPS_WS_URL = f"ws://{VPS_HOST}/api/v1/ws/edge"
VPS_RTSP_URL = f"rtsp://{VPS_HOST}:8554"
EDGE_API_KEY = os.getenv("EDGE_API_KEY", "edge-secret-key-change-in-production")
ROOM_ID = os.getenv("ROOM_ID", "room-1")

# Frame sampling
SAMPLE_FPS = float(os.getenv("SAMPLE_FPS", "3.0"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85"))

# Offline queue
QUEUE_MAXLEN = 100
QUEUE_TTL_SECONDS = 120
RECONNECT_MAX_DELAY = 30
