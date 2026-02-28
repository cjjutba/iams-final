#!/bin/bash
# IAMS Edge Device - Health Check Script
# Monitors edge device status and connectivity

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "========================================"
echo "IAMS Edge Device - Health Check"
echo "========================================"
echo ""

EDGE_DIR="/home/pi/iams-edge"
ALL_OK=true

# Check 1: Process running
echo -e "${BLUE}1. Process Status${NC}"
if pgrep -f "python.*run.py" > /dev/null; then
    PID=$(pgrep -f "python.*run.py")
    echo -e "${GREEN}✓${NC} Edge process running (PID: $PID)"
else
    echo -e "${RED}✗${NC} Edge process not running"
    ALL_OK=false
fi
echo ""

# Check 2: Camera access
echo -e "${BLUE}2. Camera Access${NC}"
if [ -e /dev/video0 ]; then
    echo -e "${GREEN}✓${NC} Camera device found (/dev/video0)"
else
    echo -e "${RED}✗${NC} Camera device not found"
    ALL_OK=false
fi
echo ""

# Check 3: Network connectivity
echo -e "${BLUE}3. Network Connectivity${NC}"
if ping -c 1 8.8.8.8 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Internet connection working"
else
    echo -e "${YELLOW}⚠${NC} No internet connection (may be OK for local network)"
fi

IP_ADDR=$(hostname -I | awk '{print $1}')
if [ -z "$IP_ADDR" ]; then
    echo -e "${RED}✗${NC} No IP address assigned"
    ALL_OK=false
else
    echo -e "${GREEN}✓${NC} IP Address: $IP_ADDR"
fi
echo ""

# Check 4: Backend connectivity
echo -e "${BLUE}4. Backend Connectivity${NC}"
if [ -f "$EDGE_DIR/.env" ]; then
    SERVER_URL=$(grep "^SERVER_URL=" "$EDGE_DIR/.env" | cut -d '=' -f2)

    if [ ! -z "$SERVER_URL" ]; then
        echo "Testing: $SERVER_URL/api/v1/health"

        if curl -s --connect-timeout 5 "$SERVER_URL/api/v1/health" &> /dev/null; then
            echo -e "${GREEN}✓${NC} Backend is reachable"
        else
            echo -e "${RED}✗${NC} Cannot reach backend"
            ALL_OK=false
        fi
    else
        echo -e "${YELLOW}⚠${NC} SERVER_URL not configured"
    fi
else
    echo -e "${YELLOW}⚠${NC} .env file not found"
fi
echo ""

# Check 5: Disk space
echo -e "${BLUE}5. Disk Space${NC}"
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✓${NC} Disk usage: ${DISK_USAGE}%"
else
    echo -e "${YELLOW}⚠${NC} Disk usage high: ${DISK_USAGE}%"
fi
echo ""

# Check 6: Memory usage
echo -e "${BLUE}6. Memory Usage${NC}"
MEM_USAGE=$(free | awk 'NR==2 {printf "%.0f", $3/$2*100}')
if [ "$MEM_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✓${NC} Memory usage: ${MEM_USAGE}%"
else
    echo -e "${YELLOW}⚠${NC} Memory usage high: ${MEM_USAGE}%"
fi
echo ""

# Check 7: Temperature (Raspberry Pi specific)
echo -e "${BLUE}7. CPU Temperature${NC}"
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
    TEMP_C=$((TEMP/1000))

    if [ "$TEMP_C" -lt 70 ]; then
        echo -e "${GREEN}✓${NC} CPU temperature: ${TEMP_C}°C"
    elif [ "$TEMP_C" -lt 80 ]; then
        echo -e "${YELLOW}⚠${NC} CPU temperature elevated: ${TEMP_C}°C"
    else
        echo -e "${RED}✗${NC} CPU temperature high: ${TEMP_C}°C"
        ALL_OK=false
    fi
else
    echo -e "${YELLOW}⚠${NC} Temperature sensor not available"
fi
echo ""

# Check 8: Recent logs
echo -e "${BLUE}8. Recent Log Errors${NC}"
if [ -f "$EDGE_DIR/logs/edge.log" ]; then
    ERROR_COUNT=$(tail -100 "$EDGE_DIR/logs/edge.log" | grep -ic "error" || true)

    if [ "$ERROR_COUNT" -eq 0 ]; then
        echo -e "${GREEN}✓${NC} No recent errors in logs"
    else
        echo -e "${YELLOW}⚠${NC} Found $ERROR_COUNT errors in last 100 log lines"
        echo "Recent errors:"
        tail -100 "$EDGE_DIR/logs/edge.log" | grep -i "error" | tail -3
    fi
else
    echo -e "${YELLOW}⚠${NC} Log file not found"
fi
echo ""

# Summary
echo "========================================"
if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}✓ All checks passed${NC}"
    echo "========================================"
    exit 0
else
    echo -e "${YELLOW}⚠ Some checks failed${NC}"
    echo "Review issues above"
    echo "========================================"
    exit 1
fi
