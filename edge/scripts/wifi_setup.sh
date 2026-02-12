#!/bin/bash
# IAMS Edge Device - WiFi Configuration Helper
# This script helps configure WiFi on Raspberry Pi

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "========================================"
echo "IAMS Edge Device - WiFi Configuration"
echo "========================================"
echo ""

# Check if running on Raspberry Pi with WiFi
if ! command -v iwconfig &> /dev/null; then
    echo -e "${RED}❌ WiFi tools not found${NC}"
    echo "Install with: sudo apt-get install wireless-tools"
    exit 1
fi

# Show current WiFi status
echo -e "${BLUE}Current WiFi Status:${NC}"
echo ""
iwconfig 2>/dev/null | grep -A 10 wlan0 || echo "No WiFi interface found"
echo ""

# Show available networks
echo -e "${BLUE}Scanning for WiFi networks...${NC}"
echo ""
sudo iwlist wlan0 scan | grep -E "ESSID|Quality" | head -20
echo ""

# Configuration method
echo "Choose configuration method:"
echo "1. Use raspi-config (recommended)"
echo "2. Edit wpa_supplicant.conf manually"
echo "3. Exit"
echo ""
read -p "Enter choice (1-3): " -n 1 -r
echo ""

case $REPLY in
    1)
        echo "Opening raspi-config..."
        echo "Navigate to: System Options → Wireless LAN"
        sleep 2
        sudo raspi-config
        ;;
    2)
        echo ""
        read -p "Enter WiFi SSID: " SSID
        read -sp "Enter WiFi password: " PASSWORD
        echo ""

        echo ""
        echo "Adding WiFi configuration to wpa_supplicant.conf..."

        sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf > /dev/null <<EOF

network={
    ssid="$SSID"
    psk="$PASSWORD"
    key_mgmt=WPA-PSK
}
EOF

        echo -e "${GREEN}✓${NC} Configuration added"
        echo ""
        echo "Restarting WiFi..."
        sudo wpa_cli -i wlan0 reconfigure
        sleep 3

        # Test connection
        echo ""
        echo "Testing connection..."
        if ping -c 3 8.8.8.8 &> /dev/null; then
            echo -e "${GREEN}✓${NC} Internet connection working"
        else
            echo -e "${YELLOW}⚠️  No internet connection${NC}"
            echo "Check SSID and password"
        fi
        ;;
    3)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Display connection info
echo ""
echo "========================================"
echo "WiFi Configuration"
echo "========================================"
echo ""

# Get IP address
IP_ADDR=$(hostname -I | awk '{print $1}')
if [ -z "$IP_ADDR" ]; then
    echo -e "${YELLOW}⚠️  No IP address assigned${NC}"
else
    echo -e "${GREEN}✓${NC} IP Address: $IP_ADDR"
fi

# Get SSID
CURRENT_SSID=$(iwgetid -r)
if [ -z "$CURRENT_SSID" ]; then
    echo -e "${YELLOW}⚠️  Not connected to WiFi${NC}"
else
    echo -e "${GREEN}✓${NC} Connected to: $CURRENT_SSID"
fi

# Test backend connectivity
echo ""
echo -e "${BLUE}Testing backend connectivity...${NC}"

# Load .env if exists
if [ -f "/home/pi/iams-edge/.env" ]; then
    source /home/pi/iams-edge/.env
fi

if [ -z "$SERVER_URL" ]; then
    read -p "Enter backend server URL (e.g., http://192.168.1.100:8000): " SERVER_URL
fi

if [ ! -z "$SERVER_URL" ]; then
    echo "Testing: $SERVER_URL/api/v1/health"
    if curl -s --connect-timeout 5 "$SERVER_URL/api/v1/health" &> /dev/null; then
        echo -e "${GREEN}✓${NC} Backend is reachable"
    else
        echo -e "${YELLOW}⚠️  Cannot reach backend${NC}"
        echo "Make sure backend is running and accessible"
        echo "Firewall may be blocking connection"
    fi
fi

echo ""
echo "========================================"
echo "Configuration complete!"
echo "========================================"
