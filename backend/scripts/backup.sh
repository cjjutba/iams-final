#!/bin/bash
# IAMS Backend - Backup Script
# Creates backups of FAISS index and database

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BACKUP_DIR="${BACKUP_DIR:-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-7}"

echo ""
echo "========================================"
echo "IAMS Backend - Backup"
echo "========================================"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup 1: FAISS Index
echo -e "${BLUE}1. Backing up FAISS index...${NC}"
FAISS_PATH="${FAISS_INDEX_PATH:-data/faiss/faces.index}"

if [ -f "$FAISS_PATH" ]; then
    BACKUP_FAISS="$BACKUP_DIR/faces_index_$TIMESTAMP.index"
    cp "$FAISS_PATH" "$BACKUP_FAISS"

    # Compress backup
    gzip "$BACKUP_FAISS"

    BACKUP_SIZE=$(du -h "$BACKUP_FAISS.gz" | cut -f1)
    echo -e "${GREEN}✓${NC} FAISS index backed up: $BACKUP_FAISS.gz ($BACKUP_SIZE)"
else
    echo -e "${YELLOW}⚠${NC} FAISS index not found, skipping"
fi
echo ""

# Backup 2: Database (if local PostgreSQL)
echo -e "${BLUE}2. Backing up database...${NC}"

if [ ! -z "${DATABASE_URL}" ]; then
    # Check if it's a Supabase URL
    if [[ "$DATABASE_URL" == *"supabase.com"* ]]; then
        echo -e "${YELLOW}⚠${NC} Supabase database detected"
        echo "   Supabase provides automatic backups"
        echo "   Daily backups available in Supabase dashboard"
        echo "   To export manually:"
        echo "   1. Go to https://app.supabase.com"
        echo "   2. Select your project"
        echo "   3. Database → Backups → Download"
    else
        # Local PostgreSQL backup
        BACKUP_DB="$BACKUP_DIR/database_$TIMESTAMP.sql"

        if command -v pg_dump &> /dev/null; then
            pg_dump "$DATABASE_URL" > "$BACKUP_DB"
            gzip "$BACKUP_DB"

            BACKUP_SIZE=$(du -h "$BACKUP_DB.gz" | cut -f1)
            echo -e "${GREEN}✓${NC} Database backed up: $BACKUP_DB.gz ($BACKUP_SIZE)"
        else
            echo -e "${YELLOW}⚠${NC} pg_dump not installed, skipping database backup"
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC} DATABASE_URL not set, skipping database backup"
fi
echo ""

# Backup 3: Configuration Files
echo -e "${BLUE}3. Backing up configuration...${NC}"
BACKUP_CONFIG="$BACKUP_DIR/config_$TIMESTAMP.tar.gz"

tar -czf "$BACKUP_CONFIG" \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='logs' \
    .env .env.production alembic.ini 2>/dev/null || true

if [ -f "$BACKUP_CONFIG" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_CONFIG" | cut -f1)
    echo -e "${GREEN}✓${NC} Configuration backed up: $BACKUP_CONFIG ($BACKUP_SIZE)"
else
    echo -e "${YELLOW}⚠${NC} No configuration files found"
fi
echo ""

# Backup 4: Upload Directory (Face Images)
echo -e "${BLUE}4. Backing up uploaded files...${NC}"
UPLOAD_DIR="${UPLOAD_DIR:-data/uploads}"

if [ -d "$UPLOAD_DIR" ]; then
    BACKUP_UPLOADS="$BACKUP_DIR/uploads_$TIMESTAMP.tar.gz"
    tar -czf "$BACKUP_UPLOADS" "$UPLOAD_DIR"

    BACKUP_SIZE=$(du -h "$BACKUP_UPLOADS" | cut -f1)
    echo -e "${GREEN}✓${NC} Uploads backed up: $BACKUP_UPLOADS ($BACKUP_SIZE)"
else
    echo -e "${YELLOW}⚠${NC} Upload directory not found, skipping"
fi
echo ""

# Cleanup: Remove old backups
echo -e "${BLUE}5. Cleaning up old backups...${NC}"
echo "   Retention: $RETENTION_DAYS days"

find "$BACKUP_DIR" -name "*.gz" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete

REMAINING_BACKUPS=$(ls -1 "$BACKUP_DIR" | wc -l)
echo -e "${GREEN}✓${NC} Cleanup complete. $REMAINING_BACKUPS backups remaining"
echo ""

# Summary
echo "========================================"
echo "Backup Complete"
echo "========================================"
echo ""
echo "Backup location: $BACKUP_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""
echo "Backed up:"
echo "  - FAISS index (if exists)"
echo "  - Configuration files"
echo "  - Uploaded files (if exists)"
echo "  - Database (if local PostgreSQL)"
echo ""
echo "To restore:"
echo "  ./scripts/restore.sh $TIMESTAMP"
echo "========================================"
