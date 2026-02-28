#!/bin/bash
# IAMS Backend - Production Startup Script
# This script starts the backend in production mode with proper checks

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "IAMS Backend - Production Startup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ Do not run as root!${NC}"
    echo "Create a dedicated user (e.g., 'iams') and run as that user."
    exit 1
fi

# Navigate to backend directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

echo -e "${GREEN}✓${NC} Working directory: $BACKEND_DIR"

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo -e "${YELLOW}⚠️  .env.production not found, using .env${NC}"
    if [ ! -f ".env" ]; then
        echo -e "${RED}❌ No .env file found!${NC}"
        echo "Copy .env.production.example to .env.production and configure it."
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} Using .env.production"
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Create it with: python3 -m venv venv"
    exit 1
fi

echo -e "${GREEN}✓${NC} Virtual environment exists"

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Check if dependencies are installed
echo ""
echo "Checking dependencies..."
python -c "import fastapi, uvicorn, sqlalchemy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Dependencies not installed!${NC}"
    echo "Install them with: pip install -r requirements.txt"
    exit 1
fi
echo -e "${GREEN}✓${NC} Dependencies installed"

# Validate environment configuration
echo ""
echo "Validating environment configuration..."
python scripts/validate_env.py
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Environment validation failed!${NC}"
    exit 1
fi

# Create necessary directories
echo ""
echo "Creating necessary directories..."
mkdir -p data/faiss data/uploads/faces logs
echo -e "${GREEN}✓${NC} Directories created"

# Check if FAISS index exists
if [ ! -f "data/faiss/faces.index" ]; then
    echo -e "${YELLOW}⚠️  FAISS index not found${NC}"
    echo "   This is normal for first-time setup."
    echo "   Index will be created when first face is registered."
fi

# Check database connection
echo ""
echo "Testing database connection..."
python -c "from app.database import check_db_connection; check_db_connection()" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Database connection failed!${NC}"
    echo "Check your DATABASE_URL in .env.production"
    exit 1
fi
echo -e "${GREEN}✓${NC} Database connection successful"

# Display startup info
echo ""
echo "========================================"
echo "Starting production server..."
echo "========================================"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start server
python run_production.py
