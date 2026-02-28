#!/bin/bash
# IAMS Backend - Restore Script
# Restores backups of FAISS index, database, and configuration

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BACKUP_DIR="${BACKUP_DIR:-backups}"

echo ""
echo "========================================"
echo "IAMS Backend - Restore from Backup"
echo "========================================"
echo ""

# Check if timestamp provided
if [ -z "$1" ]; then
    echo "Available backups:"
    echo ""
    ls -lh "$BACKUP_DIR" | grep -E "\.gz|\.tar\.gz" | tail -10
    echo ""
    echo "Usage: $0 <timestamp>"
    echo "Example: $0 20240207_143025"
    exit 1
fi

TIMESTAMP=$1

echo "Restoring from timestamp: $TIMESTAMP"
echo ""

# Warning
echo -e "${RED}WARNING: This will overwrite current data!${NC}"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

echo ""

# Restore 1: FAISS Index
echo -e "${BLUE}1. Restoring FAISS index...${NC}"
BACKUP_FAISS="$BACKUP_DIR/faces_index_$TIMESTAMP.index.gz"

if [ -f "$BACKUP_FAISS" ]; then
    FAISS_PATH="${FAISS_INDEX_PATH:-data/faiss/faces.index}"

    # Backup current index (just in case)
    if [ -f "$FAISS_PATH" ]; then
        cp "$FAISS_PATH" "$FAISS_PATH.before_restore"
        echo "   Current index backed up to: $FAISS_PATH.before_restore"
    fi

    # Restore
    gunzip -c "$BACKUP_FAISS" > "$FAISS_PATH"
    echo -e "${GREEN}✓${NC} FAISS index restored"
else
    echo -e "${YELLOW}⚠${NC} FAISS backup not found: $BACKUP_FAISS"
fi
echo ""

# Restore 2: Database
echo -e "${BLUE}2. Restoring database...${NC}"
BACKUP_DB="$BACKUP_DIR/database_$TIMESTAMP.sql.gz"

if [ -f "$BACKUP_DB" ]; then
    if [ ! -z "${DATABASE_URL}" ]; then
        echo -e "${RED}WARNING: This will overwrite the current database!${NC}"
        read -p "Continue with database restore? (yes/no): " DB_CONFIRM

        if [ "$DB_CONFIRM" = "yes" ]; then
            if command -v psql &> /dev/null; then
                # Drop existing tables (optional)
                read -p "Drop existing tables first? (yes/no): " DROP_CONFIRM

                if [ "$DROP_CONFIRM" = "yes" ]; then
                    echo "   Dropping existing tables..."
                    # This is database-specific, adjust as needed
                    psql "$DATABASE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
                fi

                # Restore
                gunzip -c "$BACKUP_DB" | psql "$DATABASE_URL"
                echo -e "${GREEN}✓${NC} Database restored"
            else
                echo -e "${RED}✗${NC} psql not installed, cannot restore database"
            fi
        else
            echo "   Skipping database restore"
        fi
    else
        echo -e "${YELLOW}⚠${NC} DATABASE_URL not set"
    fi
else
    echo -e "${YELLOW}⚠${NC} Database backup not found: $BACKUP_DB"
    echo "   Note: Supabase databases are backed up automatically"
    echo "   Restore from Supabase dashboard if needed"
fi
echo ""

# Restore 3: Configuration
echo -e "${BLUE}3. Restoring configuration...${NC}"
BACKUP_CONFIG="$BACKUP_DIR/config_$TIMESTAMP.tar.gz"

if [ -f "$BACKUP_CONFIG" ]; then
    read -p "Restore configuration files? This will overwrite .env files (yes/no): " CONFIG_CONFIRM

    if [ "$CONFIG_CONFIRM" = "yes" ]; then
        tar -xzf "$BACKUP_CONFIG"
        echo -e "${GREEN}✓${NC} Configuration restored"
    else
        echo "   Skipping configuration restore"
    fi
else
    echo -e "${YELLOW}⚠${NC} Configuration backup not found: $BACKUP_CONFIG"
fi
echo ""

# Restore 4: Uploads
echo -e "${BLUE}4. Restoring uploaded files...${NC}"
BACKUP_UPLOADS="$BACKUP_DIR/uploads_$TIMESTAMP.tar.gz"

if [ -f "$BACKUP_UPLOADS" ]; then
    read -p "Restore uploaded files? (yes/no): " UPLOADS_CONFIRM

    if [ "$UPLOADS_CONFIRM" = "yes" ]; then
        tar -xzf "$BACKUP_UPLOADS"
        echo -e "${GREEN}✓${NC} Uploads restored"
    else
        echo "   Skipping uploads restore"
    fi
else
    echo -e "${YELLOW}⚠${NC} Uploads backup not found: $BACKUP_UPLOADS"
fi
echo ""

# Restart service
echo -e "${BLUE}5. Restart backend service...${NC}"
read -p "Restart backend service now? (yes/no): " RESTART_CONFIRM

if [ "$RESTART_CONFIRM" = "yes" ]; then
    if systemctl is-active --quiet iams-backend.service 2>/dev/null; then
        echo "   Restarting systemd service..."
        sudo systemctl restart iams-backend.service
        echo -e "${GREEN}✓${NC} Service restarted"
    else
        echo -e "${YELLOW}⚠${NC} Service not running via systemd"
        echo "   Please restart manually"
    fi
else
    echo "   Please restart backend manually when ready"
fi
echo ""

# Summary
echo "========================================"
echo "Restore Complete"
echo "========================================"
echo ""
echo "Restored from: $TIMESTAMP"
echo ""
echo "Next steps:"
echo "1. Verify FAISS index loaded correctly"
echo "2. Test database connectivity"
echo "3. Check application logs"
echo "4. Test face recognition"
echo ""
echo "If issues occur, restore from:"
echo "  FAISS: $FAISS_PATH.before_restore"
echo "========================================"
