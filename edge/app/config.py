"""RPi Camera Gateway configuration — RTSP relay only."""
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

# VPS mediamtx target
VPS_HOST = os.getenv("VPS_HOST", "167.71.217.44")
VPS_RTSP_URL = f"rtsp://{VPS_HOST}:8554"
ROOM_ID = os.getenv("ROOM_ID", "room-1")
