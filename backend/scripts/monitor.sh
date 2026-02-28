#!/bin/bash
# IAMS Backend - Health Monitoring Script
# Checks backend health and logs metrics

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
LOG_FILE="${LOG_FILE:-logs/monitor.log}"
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEM=80
ALERT_THRESHOLD_DISK=85

# Timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo ""
echo "========================================"
echo "IAMS Backend - Health Monitoring"
echo "$TIMESTAMP"
echo "========================================"
echo ""

ALL_OK=true

# Check 1: API Health Endpoint
echo -e "${BLUE}1. API Health Check${NC}"
HEALTH_RESPONSE=$(curl -s --connect-timeout 5 "$BACKEND_URL/api/v1/health" || echo "")

if [ -z "$HEALTH_RESPONSE" ]; then
    echo -e "${RED}✗${NC} API not responding"
    echo "$TIMESTAMP - API Health: FAILED (no response)" >> "$LOG_FILE"
    ALL_OK=false
else
    STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status' 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} API is healthy"
        echo "$TIMESTAMP - API Health: OK" >> "$LOG_FILE"

        # Check database connection
        DB_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.database' 2>/dev/null || echo "unknown")
        if [ "$DB_STATUS" = "connected" ]; then
            echo -e "${GREEN}✓${NC} Database connected"
        else
            echo -e "${RED}✗${NC} Database connection failed"
            ALL_OK=false
        fi

        # Check FAISS index
        FAISS_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.faiss' 2>/dev/null || echo "unknown")
        if [ "$FAISS_STATUS" = "loaded" ]; then
            echo -e "${GREEN}✓${NC} FAISS index loaded"
        else
            echo -e "${YELLOW}⚠${NC} FAISS index not loaded (normal if no faces registered)"
        fi
    else
        echo -e "${RED}✗${NC} API unhealthy: $STATUS"
        echo "$TIMESTAMP - API Health: FAILED ($STATUS)" >> "$LOG_FILE"
        ALL_OK=false
    fi
fi
echo ""

# Check 2: Process Status
echo -e "${BLUE}2. Process Status${NC}"
if pgrep -f "uvicorn.*app.main:app" > /dev/null; then
    PIDS=$(pgrep -f "uvicorn.*app.main:app" | tr '\n' ' ')
    WORKER_COUNT=$(pgrep -f "uvicorn.*app.main:app" | wc -l)
    echo -e "${GREEN}✓${NC} Backend running ($WORKER_COUNT workers, PIDs: $PIDS)"
    echo "$TIMESTAMP - Process Status: OK ($WORKER_COUNT workers)" >> "$LOG_FILE"
else
    echo -e "${RED}✗${NC} Backend process not running"
    echo "$TIMESTAMP - Process Status: FAILED (not running)" >> "$LOG_FILE"
    ALL_OK=false
fi
echo ""

# Check 3: CPU Usage
echo -e "${BLUE}3. CPU Usage${NC}"
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}' | cut -d'.' -f1)
if [ "$CPU_USAGE" -lt "$ALERT_THRESHOLD_CPU" ]; then
    echo -e "${GREEN}✓${NC} CPU usage: ${CPU_USAGE}%"
    echo "$TIMESTAMP - CPU Usage: OK (${CPU_USAGE}%)" >> "$LOG_FILE"
else
    echo -e "${YELLOW}⚠${NC} CPU usage high: ${CPU_USAGE}%"
    echo "$TIMESTAMP - CPU Usage: HIGH (${CPU_USAGE}%)" >> "$LOG_FILE"
fi
echo ""

# Check 4: Memory Usage
echo -e "${BLUE}4. Memory Usage${NC}"
MEM_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
MEM_USED=$(free -h | grep Mem | awk '{print $3}')
MEM_TOTAL=$(free -h | grep Mem | awk '{print $2}')

if [ "$MEM_USAGE" -lt "$ALERT_THRESHOLD_MEM" ]; then
    echo -e "${GREEN}✓${NC} Memory usage: ${MEM_USAGE}% ($MEM_USED / $MEM_TOTAL)"
    echo "$TIMESTAMP - Memory Usage: OK (${MEM_USAGE}%)" >> "$LOG_FILE"
else
    echo -e "${YELLOW}⚠${NC} Memory usage high: ${MEM_USAGE}% ($MEM_USED / $MEM_TOTAL)"
    echo "$TIMESTAMP - Memory Usage: HIGH (${MEM_USAGE}%)" >> "$LOG_FILE"
fi
echo ""

# Check 5: Disk Space
echo -e "${BLUE}5. Disk Space${NC}"
DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
DISK_USED=$(df -h . | awk 'NR==2 {print $3}')
DISK_TOTAL=$(df -h . | awk 'NR==2 {print $2}')

if [ "$DISK_USAGE" -lt "$ALERT_THRESHOLD_DISK" ]; then
    echo -e "${GREEN}✓${NC} Disk usage: ${DISK_USAGE}% ($DISK_USED / $DISK_TOTAL)"
    echo "$TIMESTAMP - Disk Usage: OK (${DISK_USAGE}%)" >> "$LOG_FILE"
else
    echo -e "${RED}✗${NC} Disk usage critical: ${DISK_USAGE}% ($DISK_USED / $DISK_TOTAL)"
    echo "$TIMESTAMP - Disk Usage: CRITICAL (${DISK_USAGE}%)" >> "$LOG_FILE"
    ALL_OK=false
fi
echo ""

# Check 6: Log File Errors
echo -e "${BLUE}6. Recent Errors in Logs${NC}"
if [ -f "logs/app.log" ]; then
    ERROR_COUNT=$(tail -100 logs/app.log | grep -ic "error" || true)
    CRITICAL_COUNT=$(tail -100 logs/app.log | grep -ic "critical" || true)

    if [ "$ERROR_COUNT" -eq 0 ] && [ "$CRITICAL_COUNT" -eq 0 ]; then
        echo -e "${GREEN}✓${NC} No errors in last 100 log lines"
        echo "$TIMESTAMP - Log Errors: OK (0 errors)" >> "$LOG_FILE"
    else
        echo -e "${YELLOW}⚠${NC} Found $ERROR_COUNT errors, $CRITICAL_COUNT critical in last 100 lines"
        echo "$TIMESTAMP - Log Errors: $ERROR_COUNT errors, $CRITICAL_COUNT critical" >> "$LOG_FILE"

        if [ "$ERROR_COUNT" -gt 0 ]; then
            echo "Recent errors:"
            tail -100 logs/app.log | grep -i "error" | tail -3
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC} Log file not found"
fi
echo ""

# Check 7: Database Connection Pool
echo -e "${BLUE}7. Database Connection Pool${NC}"
if command -v psql &> /dev/null; then
    # Attempt to get connection count (requires DATABASE_URL)
    if [ ! -z "${DATABASE_URL}" ]; then
        CONN_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();" 2>/dev/null || echo "0")
        echo -e "${GREEN}✓${NC} Active connections: $CONN_COUNT"
        echo "$TIMESTAMP - DB Connections: $CONN_COUNT" >> "$LOG_FILE"
    else
        echo -e "${YELLOW}⚠${NC} DATABASE_URL not set, cannot check connections"
    fi
else
    echo -e "${YELLOW}⚠${NC} psql not installed, cannot check database connections"
fi
echo ""

# Check 8: FAISS Index Size
echo -e "${BLUE}8. FAISS Index Status${NC}"
FAISS_PATH="${FAISS_INDEX_PATH:-data/faiss/faces.index}"
if [ -f "$FAISS_PATH" ]; then
    FAISS_SIZE=$(du -h "$FAISS_PATH" | cut -f1)
    FAISS_MODIFIED=$(stat -c %y "$FAISS_PATH" 2>/dev/null || stat -f %Sm "$FAISS_PATH" 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓${NC} FAISS index exists: $FAISS_SIZE (modified: $FAISS_MODIFIED)"
    echo "$TIMESTAMP - FAISS Index: OK ($FAISS_SIZE)" >> "$LOG_FILE"
else
    echo -e "${YELLOW}⚠${NC} FAISS index not found (normal if no faces registered)"
    echo "$TIMESTAMP - FAISS Index: Not found" >> "$LOG_FILE"
fi
echo ""

# Check 9: Network Connectivity
echo -e "${BLUE}9. Network Connectivity${NC}"
if ping -c 1 8.8.8.8 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Internet connection working"
    echo "$TIMESTAMP - Network: OK" >> "$LOG_FILE"
else
    echo -e "${YELLOW}⚠${NC} No internet connection (may be OK for local network)"
    echo "$TIMESTAMP - Network: No internet" >> "$LOG_FILE"
fi

# Test Supabase connectivity
if [ ! -z "${SUPABASE_URL}" ]; then
    if curl -s --connect-timeout 5 "${SUPABASE_URL}/rest/v1/" &> /dev/null; then
        echo -e "${GREEN}✓${NC} Supabase reachable"
    else
        echo -e "${RED}✗${NC} Cannot reach Supabase"
        ALL_OK=false
    fi
fi
echo ""

# Summary
echo "========================================"
if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}✓ All checks passed${NC}"
    echo "$TIMESTAMP - Overall Status: HEALTHY" >> "$LOG_FILE"
    exit 0
else
    echo -e "${YELLOW}⚠ Some checks failed${NC}"
    echo "$TIMESTAMP - Overall Status: UNHEALTHY" >> "$LOG_FILE"
    exit 1
fi
