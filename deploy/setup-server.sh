#!/bin/bash
# =============================================================================
# IAMS VPS Setup Script
# Run this ONCE on a fresh DigitalOcean droplet
# Usage: ssh root@167.71.217.44 'bash -s' < deploy/setup-server.sh
# =============================================================================

set -euo pipefail

echo "=========================================="
echo "  IAMS Server Setup - DigitalOcean VPS"
echo "=========================================="

# Update system (non-interactive to avoid config prompts)
echo "[1/5] Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get upgrade -y -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

# Install Docker
echo "[2/5] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker installed: $(docker --version)"
else
    echo "Docker already installed: $(docker --version)"
fi

# Install Docker Compose plugin
echo "[3/5] Verifying Docker Compose..."
if docker compose version &> /dev/null; then
    echo "Docker Compose available: $(docker compose version)"
else
    apt-get install -y -qq docker-compose-plugin
    echo "Docker Compose installed: $(docker compose version)"
fi

# Create project directory
echo "[4/5] Creating project directory..."
mkdir -p /opt/iams
cd /opt/iams

# Configure firewall
echo "[5/5] Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8000/tcp  # Direct backend access (for testing)
    echo "y" | ufw enable || true
    echo "Firewall configured"
fi

echo ""
echo "=========================================="
echo "  Server setup complete!"
echo "  Project directory: /opt/iams"
echo "=========================================="
echo ""
echo "Next step: Run the deploy script from your MacBook:"
echo "  ./deploy/deploy.sh"
