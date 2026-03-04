# Edge Device Setup Guide

Complete guide for setting up IAMS edge device on Raspberry Pi.

## Hardware Requirements

| Component | Specification | Notes |
|-----------|--------------|-------|
| Raspberry Pi | Model 4B (4GB+ RAM) | Model 3B+ also works but slower |
| Camera | Raspberry Pi Camera Module v2 or USB webcam | CSI camera recommended |
| SD Card | 32GB+ Class 10 | Fast card recommended |
| Power Supply | Official 5V/3A USB-C | Stable power critical |
| Case | With cooling | Passive heatsink minimum |
| Network | WiFi or Ethernet | Stable connection required |

## Prerequisites

- Raspberry Pi OS (64-bit Bullseye or later)
- SSH access enabled
- Basic Linux command knowledge
- Backend server accessible on network

## Quick Setup (Automated)

1. **Download setup script to Raspberry Pi:**
   ```bash
   curl -O https://raw.githubusercontent.com/your-repo/iams/main/edge/scripts/setup_rpi.sh
   chmod +x setup_rpi.sh
   ./setup_rpi.sh
   ```

2. **Follow interactive prompts:**
   - System will update packages
   - Install dependencies
   - Setup Python environment
   - Configure .env file
   - Setup systemd service (optional)

3. **Configure backend URL:**
   ```bash
   nano /home/pi/iams-edge/.env
   # Update SERVER_URL to your backend IP
   ```

4. **Start edge device:**
   ```bash
   sudo systemctl start iams-edge
   ```

## Manual Setup

### Step 1: Prepare Raspberry Pi

1. **Flash Raspberry Pi OS:**
   - Use Raspberry Pi Imager
   - Select "Raspberry Pi OS (64-bit)"
   - Configure WiFi and SSH in advanced options
   - Flash to SD card

2. **First boot:**
   ```bash
   ssh pi@raspberrypi.local
   # Default password: raspberry (change immediately)
   ```

3. **Update system:**
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

### Step 2: Install Dependencies

1. **System packages:**
   ```bash
   sudo apt install -y \
       python3 \
       python3-pip \
       python3-venv \
       python3-opencv \
       libopencv-dev \
       libcamera-dev \
       libcamera-tools \
       python3-picamera2 \
       git
   ```

2. **Test camera:**
   ```bash
   libcamera-hello
   # Should display camera feed for 5 seconds
   ```

### Step 3: Setup Application

1. **Create directory:**
   ```bash
   mkdir -p /home/pi/iams-edge
   cd /home/pi/iams-edge
   ```

2. **Copy or clone code:**

   **Option A: From Git**
   ```bash
   git clone https://github.com/your-repo/iams.git .
   cd edge
   ```

   **Option B: Manual copy**
   ```bash
   # Copy edge/ directory from development machine
   scp -r edge/* pi@raspberrypi:/home/pi/iams-edge/
   ```

3. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Step 4: Configure Environment

1. **Create .env file:**
   ```bash
   cp .env.example .env
   nano .env
   ```

2. **Configure settings:**
   ```env
   # Update these values
   SERVER_URL=http://192.168.1.100:8000  # Your backend IP
   CAMERA_INDEX=0
   ROOM_ID=301  # Optional: specific room
   ```

3. **Validate configuration:**
   ```bash
   python scripts/validate_env.py
   ```

### Step 5: Setup WiFi

**Method 1: Using raspi-config (Recommended)**
```bash
sudo raspi-config
# Navigate to: System Options → Wireless LAN
# Enter SSID and password
```

**Method 2: Using helper script**
```bash
./scripts/wifi_setup.sh
```

**Method 3: Manual configuration**
```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

Add network configuration:
```
network={
    ssid="Your-WiFi-Name"
    psk="Your-WiFi-Password"
    key_mgmt=WPA-PSK
}
```

Restart WiFi:
```bash
sudo wpa_cli -i wlan0 reconfigure
```

### Step 6: Test Setup

1. **Run validation:**
   ```bash
   python scripts/validate_env.py
   ```

2. **Test backend connectivity:**
   ```bash
   curl http://192.168.1.100:8000/api/v1/health
   # Should return: {"status":"healthy"}
   ```

3. **Run edge device manually:**
   ```bash
   source venv/bin/activate
   python run.py
   ```

4. **Check logs:**
   ```bash
   tail -f logs/edge.log
   ```

### Step 7: Setup Auto-Start (Systemd)

1. **Copy service file:**
   ```bash
   sudo cp iams-edge.service /etc/systemd/system/
   ```

2. **Update paths in service file (if needed):**
   ```bash
   sudo nano /etc/systemd/system/iams-edge.service
   # Verify WorkingDirectory and ExecStart paths
   ```

3. **Enable and start service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable iams-edge.service
   sudo systemctl start iams-edge.service
   ```

4. **Check status:**
   ```bash
   sudo systemctl status iams-edge
   ```

5. **View logs:**
   ```bash
   sudo journalctl -u iams-edge -f
   ```

## Camera Positioning

### Optimal Setup

- **Height:** 2.0-2.5 meters above floor
- **Angle:** 15-30° downward tilt
- **Distance:** Captures faces at 1-3 meters
- **Coverage:** 3-5 meter radius
- **Lighting:** Avoid direct sunlight/backlighting

### Mounting

1. **Use sturdy mount:**
   - Wall bracket or ceiling mount
   - Ensure stable, vibration-free

2. **Cable management:**
   - Power cable secured
   - Network cable (if using Ethernet)
   - Protect cables from damage

3. **Test coverage:**
   - Walk through capture area
   - Verify faces detected at different positions
   - Adjust angle as needed

## Network Configuration

### Finding Backend IP

**On backend laptop (Windows):**
```cmd
ipconfig
# Look for IPv4 Address under WiFi adapter
```

**On backend laptop (Linux/Mac):**
```bash
ifconfig
# or
ip addr show
```

### Port Configuration

- **Backend API:** 8000 (default)
- **WebSocket:** 8000 (same as API)
- **Ensure firewall allows incoming connections**

**Windows Firewall:**
```cmd
netsh advfirewall firewall add rule name="IAMS Backend" dir=in action=allow protocol=TCP localport=8000
```

**Linux Firewall (ufw):**
```bash
sudo ufw allow 8000/tcp
```

### Same Network Requirement

- Backend and edge device must be on same WiFi network
- Check network SSID matches
- Verify both devices can ping each other

```bash
# On edge device
ping <backend-ip>

# On backend
ping <edge-device-ip>
```

## Monitoring and Maintenance

### Health Checks

**Run health check script:**
```bash
./scripts/health_check.sh
```

**Check process status:**
```bash
sudo systemctl status iams-edge
```

**View real-time logs:**
```bash
tail -f logs/edge.log
# or
sudo journalctl -u iams-edge -f
```

### Common Issues

#### Camera Not Detected

```bash
# List video devices
ls -l /dev/video*

# Check permissions
groups pi
# Should include 'video' group

# Add user to video group if missing
sudo usermod -a -G video pi
# Logout and login again
```

#### Cannot Reach Backend

```bash
# Check network connectivity
ping <backend-ip>

# Check backend is running
curl http://<backend-ip>:8000/api/v1/health

# Check firewall on backend
# Windows: Check Windows Defender Firewall
# Linux: sudo ufw status
```

#### High CPU Usage

- Reduce frame rate in .env: `FRAME_RATE=5`
- Increase frame skip: `FRAME_SKIP=2`
- Reduce resolution: `FRAME_WIDTH=320 FRAME_HEIGHT=240`

#### Queue Filling Up

- Indicates backend is unreachable or slow
- Check network connection
- Verify backend is running
- Check backend logs for errors

### Log Rotation

Logs are automatically rotated when they reach 5MB.

**Manual log cleanup:**
```bash
# Clear old logs
cd /home/pi/iams-edge/logs
rm edge.log.1 edge.log.2
```

### Updates

**Update edge device code:**
```bash
cd /home/pi/iams-edge
git pull  # If using Git

# Restart service
sudo systemctl restart iams-edge
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status iams-edge

# Check logs
sudo journalctl -u iams-edge -n 50

# Check Python errors
source venv/bin/activate
python run.py
```

### Camera Errors

```bash
# Test camera directly
libcamera-hello --camera 0

# Check camera is enabled
sudo raspi-config
# Interface Options → Camera → Enable

# Reboot
sudo reboot
```

### Permission Errors

```bash
# Fix ownership
sudo chown -R pi:pi /home/pi/iams-edge

# Fix permissions
chmod +x scripts/*.sh
```

## Security Considerations

1. **Change default password:**
   ```bash
   passwd
   ```

2. **Setup SSH keys:**
   ```bash
   ssh-keygen -t ed25519
   # Copy public key to backend for secure access
   ```

3. **Disable password SSH (optional):**
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

4. **Keep system updated:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

5. **Use strong WiFi password**

## Performance Tuning

### For Raspberry Pi 3B+

```env
FRAME_WIDTH=320
FRAME_HEIGHT=240
FRAME_RATE=5
FRAME_SKIP=2
```

### For Raspberry Pi 4B

```env
FRAME_WIDTH=640
FRAME_HEIGHT=480
FRAME_RATE=10
FRAME_SKIP=1
```

### For Raspberry Pi 5

```env
FRAME_WIDTH=640
FRAME_HEIGHT=480
FRAME_RATE=15
FRAME_SKIP=1
```

## Backup and Recovery

### Backup Configuration

```bash
# Backup .env file
cp /home/pi/iams-edge/.env ~/iams-edge-backup.env

# Backup entire directory
tar -czf ~/iams-edge-backup.tar.gz /home/pi/iams-edge/
```

### Recovery

```bash
# Restore configuration
cp ~/iams-edge-backup.env /home/pi/iams-edge/.env

# Restore full directory
tar -xzf ~/iams-edge-backup.tar.gz -C /
```

## Next Steps

After edge device is set up and running:

1. Verify faces are being detected in logs
2. Check backend logs for incoming face detection requests
3. Test face recognition by registering a face
4. Monitor system for 24 hours to ensure stability
5. Document device location and configuration
