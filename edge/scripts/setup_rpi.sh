#!/bin/bash
# IAMS Edge Device - Raspberry Pi Setup Script
# This script automates the setup of a new Raspberry Pi edge device

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
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}⚠️  Not detected as Raspberry Pi${NC}"
    echo "This script is designed for Raspberry Pi OS."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    MODEL=$(cat /proc/device-tree/model)
    echo -e "${GREEN}✓${NC} Device: $MODEL"
fi

# Update system
echo ""
echo -e "${BLUE}Step 1: Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y
echo -e "${GREEN}✓${NC} System updated"

# Install system dependencies
echo ""
echo -e "${BLUE}Step 2: Installing system dependencies...${NC}"
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-opencv \
    libopencv-dev \
    libcap-dev \
    v4l-utils \
    git \
    curl

echo -e "${GREEN}✓${NC} System dependencies installed"

# Install camera dependencies for Raspberry Pi
echo ""
echo -e "${BLUE}Step 3: Installing camera dependencies...${NC}"
sudo apt-get install -y \
    libcamera-dev \
    libcamera-tools \
    python3-picamera2

echo -e "${GREEN}✓${NC} Camera dependencies installed"

# Test camera
echo ""
echo -e "${BLUE}Step 4: Testing camera...${NC}"
if command -v libcamera-hello &> /dev/null; then
    echo "Running camera test (will display for 2 seconds)..."
    timeout 2s libcamera-hello || true
    echo -e "${GREEN}✓${NC} Camera test completed"
else
    echo -e "${YELLOW}⚠️  libcamera-hello not found, skipping camera test${NC}"
fi

# Create application directory
echo ""
echo -e "${BLUE}Step 5: Creating application directory...${NC}"
INSTALL_DIR="/home/pi/iams-edge"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo -e "${GREEN}✓${NC} Application directory: $INSTALL_DIR"

# Clone or copy edge device code
echo ""
echo -e "${BLUE}Step 6: Setting up edge device code...${NC}"
read -p "Clone from Git repository? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter Git repository URL: " GIT_REPO
    git clone "$GIT_REPO" .
    echo -e "${GREEN}✓${NC} Code cloned from repository"
else
    echo "Please copy edge device code to $INSTALL_DIR manually"
    read -p "Press Enter when done..."
fi

# Create virtual environment
echo ""
echo -e "${BLUE}Step 7: Creating Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment created"

# Install Python dependencies
echo ""
echo -e "${BLUE}Step 8: Installing Python dependencies...${NC}"
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${YELLOW}⚠️  requirements.txt not found${NC}"
    echo "Installing basic dependencies..."
    pip install opencv-python mediapipe requests python-dotenv
fi

# Configure environment
echo ""
echo -e "${BLUE}Step 9: Configuring environment...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓${NC} Created .env from .env.example"
    else
        echo "Creating default .env file..."
        cat > .env << EOF
BACKEND_URL=http://192.168.1.100:8000
ROOM_ID=
CAMERA_INDEX=0
CAMERA_WIDTH=640
CAMERA_HEIGHT=480
QUEUE_MAX_SIZE=500
QUEUE_TTL_SECONDS=300
RETRY_INTERVAL_SECONDS=10
LOG_LEVEL=INFO
LOG_FILE=logs/edge.log
EOF
        echo -e "${GREEN}✓${NC} Created default .env file"
    fi

    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env file and set BACKEND_URL${NC}"
    read -p "Enter backend server URL (e.g., http://192.168.1.100:8000): " BACKEND_URL
    sed -i "s|BACKEND_URL=.*|BACKEND_URL=$BACKEND_URL|" .env
    echo -e "${GREEN}✓${NC} BACKEND_URL configured"
else
    echo -e "${GREEN}✓${NC} .env file already exists"
fi

# Create necessary directories
echo ""
echo -e "${BLUE}Step 10: Creating directories...${NC}"
mkdir -p logs
echo -e "${GREEN}✓${NC} Directories created"

# Test configuration
echo ""
echo -e "${BLUE}Step 11: Validating configuration...${NC}"
if [ -f "scripts/validate_env.py" ]; then
    python scripts/validate_env.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Configuration valid"
    else
        echo -e "${YELLOW}⚠️  Configuration validation failed${NC}"
        echo "Please review errors above and fix .env file"
    fi
else
    echo -e "${YELLOW}⚠️  validate_env.py not found, skipping validation${NC}"
fi

# Setup systemd service
echo ""
echo -e "${BLUE}Step 12: Setting up systemd service...${NC}"
read -p "Setup systemd service for auto-start? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "iams-edge.service" ]; then
        # Update paths in service file
        sed "s|/home/pi/iams-edge|$INSTALL_DIR|g" iams-edge.service > /tmp/iams-edge.service

        # Copy service file
        sudo cp /tmp/iams-edge.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable iams-edge.service

        echo -e "${GREEN}✓${NC} Systemd service installed and enabled"
        echo "   Start: sudo systemctl start iams-edge"
        echo "   Stop:  sudo systemctl stop iams-edge"
        echo "   Status: sudo systemctl status iams-edge"
        echo "   Logs: sudo journalctl -u iams-edge -f"
    else
        echo -e "${YELLOW}⚠️  iams-edge.service file not found${NC}"
    fi
fi

# Display WiFi configuration instructions
echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure WiFi (if not already done):"
echo "   sudo raspi-config"
echo "   → System Options → Wireless LAN"
echo ""
echo "2. Verify backend connectivity:"
echo "   ping <backend-ip>"
echo "   curl <backend-url>/api/v1/health"
echo ""
echo "3. Test edge device:"
echo "   source venv/bin/activate"
echo "   python run.py"
echo ""
echo "4. Start service (if systemd configured):"
echo "   sudo systemctl start iams-edge"
echo ""
echo "5. Monitor logs:"
echo "   tail -f logs/edge.log"
echo "   OR"
echo "   sudo journalctl -u iams-edge -f"
echo ""
echo "Installed at: $INSTALL_DIR"
echo "========================================"
