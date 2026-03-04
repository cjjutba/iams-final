#!/bin/bash
# IAMS Edge Device - Raspberry Pi Setup Script
# Tested on: Raspberry Pi 4/5 + Raspberry Pi OS (64-bit Bookworm) + Python 3.11
#
# Usage:
#   chmod +x scripts/setup_rpi.sh
#   ./scripts/setup_rpi.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "========================================"
echo "IAMS Edge Device Setup for Raspberry Pi"
echo "========================================"
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    MODEL=$(cat /proc/device-tree/model)
    echo -e "${GREEN}[OK]${NC} Device: $MODEL"
else
    echo -e "${YELLOW}[WARN]${NC} Not detected as Raspberry Pi"
    echo "This script is designed for Raspberry Pi OS (64-bit)."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check architecture
ARCH=$(uname -m)
echo -e "${GREEN}[OK]${NC} Architecture: $ARCH"
if [[ "$ARCH" != "aarch64" ]]; then
    echo -e "${YELLOW}[WARN]${NC} Expected aarch64 (64-bit). Got: $ARCH"
    echo "MediaPipe requires 64-bit Raspberry Pi OS."
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}[OK]${NC} Python: $PYTHON_VERSION"

# ============================================
# Step 1: Update system
# ============================================
echo ""
echo -e "${BLUE}Step 1: Updating system packages...${NC}"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
echo -e "${GREEN}[OK]${NC} System updated"

# ============================================
# Step 2: Install system dependencies
# ============================================
echo ""
echo -e "${BLUE}Step 2: Installing system dependencies...${NC}"
sudo apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libopencv-dev \
    libcap-dev \
    v4l-utils \
    git \
    curl \
    ffmpeg

echo -e "${GREEN}[OK]${NC} System dependencies installed"

# ============================================
# Step 3: Create virtual environment
# ============================================
echo ""
echo -e "${BLUE}Step 3: Setting up Python virtual environment...${NC}"

EDGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$EDGE_DIR"
echo "  Working directory: $EDGE_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}[OK]${NC} Virtual environment created"
else
    echo -e "${GREEN}[OK]${NC} Virtual environment already exists"
fi

source venv/bin/activate

# Upgrade pip
pip install --upgrade pip -q

# ============================================
# Step 4: Install Python dependencies
# ============================================
echo ""
echo -e "${BLUE}Step 4: Installing Python dependencies...${NC}"

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}[OK]${NC} Dependencies installed"
else
    echo -e "${RED}[ERROR]${NC} requirements.txt not found in $EDGE_DIR"
    exit 1
fi

# ============================================
# Step 5: Configure environment
# ============================================
echo ""
echo -e "${BLUE}Step 5: Configuring environment (.env)...${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}[OK]${NC} Created .env from .env.example"
    else
        echo -e "${RED}[ERROR]${NC} .env.example not found"
        exit 1
    fi

    echo ""
    echo -e "${YELLOW}Configure your .env file:${NC}"

    # Backend URL
    read -p "  Backend URL [http://192.168.1.10:8000]: " BACKEND_URL
    BACKEND_URL=${BACKEND_URL:-http://192.168.1.10:8000}
    sed -i "s|^BACKEND_URL=.*|BACKEND_URL=$BACKEND_URL|" .env

    # Room ID
    read -p "  Room ID (from Supabase rooms table): " ROOM_ID
    if [ -n "$ROOM_ID" ]; then
        sed -i "s|^ROOM_ID=.*|ROOM_ID=$ROOM_ID|" .env
    fi

    # Camera source
    echo ""
    echo "  Camera source options:"
    echo "    1) rtsp  - IP camera (Reolink P340)"
    echo "    2) usb   - USB webcam"
    echo "    3) auto  - Auto-detect"
    read -p "  Camera source [1]: " CAM_CHOICE
    case "$CAM_CHOICE" in
        2) CAM_SOURCE="usb" ;;
        3) CAM_SOURCE="auto" ;;
        *) CAM_SOURCE="rtsp" ;;
    esac
    sed -i "s|^CAMERA_SOURCE=.*|CAMERA_SOURCE=$CAM_SOURCE|" .env

    # RTSP URL
    if [ "$CAM_SOURCE" = "rtsp" ] || [ "$CAM_SOURCE" = "auto" ]; then
        read -p "  RTSP URL [rtsp://admin:password@192.168.1.100:554/h264Preview_01_main]: " RTSP_URL
        if [ -n "$RTSP_URL" ]; then
            sed -i "s|^RTSP_URL=.*|RTSP_URL=$RTSP_URL|" .env
        fi
    fi

    # Detection model
    echo ""
    echo "  Detection model:"
    echo "    0) Short-range (up to 2m) - close-up USB/Pi cameras"
    echo "    1) Full-range (up to 5m) - IP cameras mounted far"
    read -p "  Detection model [1]: " DET_MODEL
    DET_MODEL=${DET_MODEL:-1}
    sed -i "s|^DETECTION_MODEL=.*|DETECTION_MODEL=$DET_MODEL|" .env

    echo -e "${GREEN}[OK]${NC} Environment configured"
else
    echo -e "${GREEN}[OK]${NC} .env file already exists"
fi

# ============================================
# Step 6: Create directories
# ============================================
echo ""
echo -e "${BLUE}Step 6: Creating directories...${NC}"
mkdir -p logs
mkdir -p app/.models
echo -e "${GREEN}[OK]${NC} Directories created"

# ============================================
# Step 7: Test network connectivity
# ============================================
echo ""
echo -e "${BLUE}Step 7: Testing network connectivity...${NC}"

# Extract backend host from .env
BACKEND_URL=$(grep "^BACKEND_URL=" .env | cut -d'=' -f2)
BACKEND_HOST=$(echo "$BACKEND_URL" | sed -E 's|https?://([^:/]+).*|\1|')

if [ -n "$BACKEND_HOST" ]; then
    if ping -c 1 -W 2 "$BACKEND_HOST" > /dev/null 2>&1; then
        echo -e "${GREEN}[OK]${NC} Backend host reachable: $BACKEND_HOST"
    else
        echo -e "${YELLOW}[WARN]${NC} Cannot reach backend: $BACKEND_HOST"
        echo "  Make sure the backend server is running and on the same network"
    fi
fi

# Test RTSP camera
RTSP_URL=$(grep "^RTSP_URL=" .env | cut -d'=' -f2)
if [ -n "$RTSP_URL" ]; then
    RTSP_HOST=$(echo "$RTSP_URL" | sed -E 's|rtsp://[^@]*@([^:/]+).*|\1|')
    if [ -n "$RTSP_HOST" ]; then
        if ping -c 1 -W 2 "$RTSP_HOST" > /dev/null 2>&1; then
            echo -e "${GREEN}[OK]${NC} Camera reachable: $RTSP_HOST"
        else
            echo -e "${YELLOW}[WARN]${NC} Cannot reach camera: $RTSP_HOST"
            echo "  Make sure the camera and RPi are on the same network"
        fi
    fi
fi

# ============================================
# Step 8: Quick test
# ============================================
echo ""
echo -e "${BLUE}Step 8: Running quick import test...${NC}"

python3 -c "
import sys
print(f'  Python: {sys.version}')

import numpy as np
print(f'  numpy: {np.__version__}')

import cv2
print(f'  opencv: {cv2.__version__}')

import mediapipe as mp
print(f'  mediapipe: {mp.__version__}')

import httpx
print(f'  httpx: {httpx.__version__}')

print('  All imports successful!')
" 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}[OK]${NC} All imports successful"
else
    echo -e "${RED}[ERROR]${NC} Import test failed — check dependency installation"
fi

# ============================================
# Step 9 (optional): Setup systemd service
# ============================================
echo ""
read -p "Setup systemd service for auto-start on boot? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/iams-edge.service"

    sudo tee "$SERVICE_FILE" > /dev/null << SVCEOF
[Unit]
Description=IAMS Edge Device - Face Detection
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$EDGE_DIR
ExecStart=$EDGE_DIR/venv/bin/python run.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

    sudo systemctl daemon-reload
    sudo systemctl enable iams-edge.service

    echo -e "${GREEN}[OK]${NC} Systemd service installed and enabled"
    echo "  Start:  sudo systemctl start iams-edge"
    echo "  Stop:   sudo systemctl stop iams-edge"
    echo "  Status: sudo systemctl status iams-edge"
    echo "  Logs:   sudo journalctl -u iams-edge -f"
fi

# ============================================
# Done
# ============================================
echo ""
echo "========================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================"
echo ""
echo "To run the edge device:"
echo "  cd $EDGE_DIR"
echo "  source venv/bin/activate"
echo "  python run.py"
echo ""
echo "To test camera + face detection first:"
echo "  python tools/test_camera.py --rtsp \"<your-rtsp-url>\" --detect"
echo ""
echo "========================================"
