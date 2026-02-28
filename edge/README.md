# IAMS Edge Device - Raspberry Pi Face Detection

Raspberry Pi edge device for continuous face detection and attendance monitoring in the IAMS (Intelligent Attendance Monitoring System).

## Overview

The edge device captures video frames, detects faces using MediaPipe, crops and encodes faces to JPEG, and sends them to the backend for recognition and presence tracking.

### Architecture

```
Raspberry Pi Edge Device
  ├── Camera (picamera2 / OpenCV)
  ├── Face Detector (MediaPipe TFLite)
  ├── Face Processor (crop, resize, JPEG encode)
  ├── HTTP Sender (POST to backend)
  └── Queue Manager (offline queue with retry)

          ↓ HTTP POST

Backend API (/api/v1/face/process)
  ├── Face Recognition (FaceNet + FAISS)
  ├── Presence Tracking (DeepSORT)
  └── Attendance Recording
```

## Hardware Requirements

### Recommended

- **Raspberry Pi 4 Model B (4GB or 8GB RAM)** - Best performance
- **Raspberry Pi Camera Module V2 or V3** - Native support via picamera2
- **16GB microSD card** (Class 10 or better)
- **5V 3A USB-C power supply**
- **Case with camera mount**

### Minimum

- **Raspberry Pi 4 Model B (2GB RAM)** - Acceptable performance
- **USB Webcam (720p)** - Fallback if no Pi Camera
- **16GB microSD card**

### Not Recommended

- Raspberry Pi 3 (too slow for MediaPipe)
- Raspberry Pi Zero (insufficient CPU)

## Software Requirements

- **Raspberry Pi OS Bullseye or later** (64-bit recommended)
- **Python 3.9+**
- **libcamera** (for Pi Camera Module)

## Installation

### 1. Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv git libcamera-dev

# Install picamera2 (for Pi Camera Module)
sudo apt install -y python3-picamera2

# Reboot
sudo reboot
```

### 2. Clone Repository

```bash
cd ~
git clone https://github.com/yourusername/iams.git
cd iams/edge
```

### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Note:** If using Pi Camera Module, uncomment `picamera2` in `requirements.txt`:

```txt
picamera2>=0.3.12
```

### 5. Configure Environment

```bash
cp .env.example .env
nano .env
```

**Required Configuration:**

```bash
# Backend API URL (replace with your backend IP/domain)
BACKEND_URL=http://192.168.1.100:8000

# Room ID (get from backend admin panel)
ROOM_ID=uuid-room-301
```

**Optional Configuration:**

- `CAMERA_INDEX=0` - Camera device index (0 for primary)
- `SCAN_INTERVAL=60` - Scan interval in seconds (60 = 1 minute)
- `DETECTION_CONFIDENCE=0.5` - Face detection threshold (0.0-1.0)
- See `.env.example` for all options

### 6. Test Camera

```bash
# Test Pi Camera Module
libcamera-hello --timeout 5000

# Test USB Webcam
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera FAIL')"
```

### 7. Run Edge Device

```bash
python run.py
```

Expected output:

```
[2024-01-15 10:00:00] [INFO] [edge] ============================================================
[2024-01-15 10:00:00] [INFO] [edge]   IAMS Edge Device - Raspberry Pi Face Detection
[2024-01-15 10:00:00] [INFO] [edge]   Intelligent Attendance Monitoring System
[2024-01-15 10:00:00] [INFO] [edge] ============================================================
[2024-01-15 10:00:00] [INFO] [edge] Initializing IAMS Edge Device...
[2024-01-15 10:00:00] [INFO] [edge] Room ID: uuid-room-301
[2024-01-15 10:00:00] [INFO] [edge] Backend URL: http://192.168.1.100:8000
[2024-01-15 10:00:00] [INFO] [edge] Scan interval: 60s
[2024-01-15 10:00:01] [INFO] [edge] Pi Camera initialized successfully - 640x480 @ 15 FPS
[2024-01-15 10:00:02] [INFO] [edge] MediaPipe Face Detector initialized - confidence=0.5, model=short-range
[2024-01-15 10:00:02] [INFO] [edge] Retry worker started
[2024-01-15 10:00:02] [INFO] [edge] All components initialized successfully
[2024-01-15 10:00:02] [INFO] [edge] Starting continuous scanning loop...
```

## Production Deployment

### Run as Systemd Service

Create service file:

```bash
sudo nano /etc/systemd/system/iams-edge.service
```

Service configuration:

```ini
[Unit]
Description=IAMS Edge Device
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/iams/edge
ExecStart=/home/pi/iams/edge/venv/bin/python run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

Enable and start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable iams-edge.service
sudo systemctl start iams-edge.service
```

Check status:

```bash
sudo systemctl status iams-edge.service
```

View logs:

```bash
sudo journalctl -u iams-edge.service -f
```

## Queue Management

### Offline Queue Policy

When the backend is unreachable, the edge device queues faces locally:

- **Max queue size:** 500 items
- **TTL:** 5 minutes (stale entries are discarded)
- **Retry interval:** 10 seconds
- **Max retry attempts:** 3 per request

Queue is stored in-memory using `collections.deque`. Monitor queue status in logs:

```
[INFO] Queue size: 15/500
[WARNING] Queue full (500 items), dropped oldest entry
[INFO] Successfully retried entry. Queue size: 14
```

### Handling Queue Full

If queue fills up (500 items):

1. **Check network connection** - Verify backend is reachable
2. **Check backend health** - Ensure backend is running
3. **Increase retry interval** - Reduce retry frequency to avoid overload
4. **Increase TTL** - Keep entries longer (not recommended)
5. **Restart edge device** - Clears queue and retries initialization

## Troubleshooting

### Camera Issues

**Problem:** `Camera initialization failed`

**Solutions:**

1. **Pi Camera Module:**
   ```bash
   # Check camera is detected
   libcamera-hello --list-cameras

   # Enable camera interface
   sudo raspi-config
   # Interface Options → Camera → Enable

   # Reboot
   sudo reboot
   ```

2. **USB Webcam:**
   ```bash
   # List video devices
   ls -l /dev/video*

   # Check device permissions
   sudo usermod -a -G video $USER

   # Reboot
   sudo reboot
   ```

### MediaPipe Issues

**Problem:** `Failed to initialize Face Detector`

**Solutions:**

1. **Install ARM-compatible MediaPipe:**
   ```bash
   pip install --upgrade mediapipe==0.10.8
   ```

2. **Check Python version:**
   ```bash
   python3 --version  # Should be 3.9+
   ```

3. **Install system dependencies:**
   ```bash
   sudo apt install -y libopencv-dev python3-opencv
   ```

### Network Issues

**Problem:** `Backend request error: Connection refused`

**Solutions:**

1. **Check backend is running:**
   ```bash
   curl http://192.168.1.100:8000/
   ```

2. **Check network connectivity:**
   ```bash
   ping 192.168.1.100
   ```

3. **Update BACKEND_URL in .env:**
   ```bash
   nano .env
   # BACKEND_URL=http://192.168.1.100:8000
   ```

4. **Check firewall:**
   ```bash
   # On backend server
   sudo ufw allow 8000
   ```

### Performance Issues

**Problem:** High CPU usage, slow detection

**Solutions:**

1. **Reduce camera FPS:**
   ```bash
   # In .env
   CAMERA_FPS=10  # Reduce from 15 to 10
   ```

2. **Increase scan interval:**
   ```bash
   # In .env
   SCAN_INTERVAL=120  # Increase from 60 to 120 seconds
   ```

3. **Use short-range detection model:**
   ```bash
   # In .env
   DETECTION_MODEL=0  # 0 = short-range (faster)
   ```

4. **Reduce JPEG quality:**
   ```bash
   # In .env
   JPEG_QUALITY=50  # Reduce from 70 to 50
   ```

## Monitoring

### System Metrics

Check CPU and memory usage:

```bash
# CPU temperature
vcgencmd measure_temp

# CPU usage
top -b -n 1 | grep python

# Memory usage
free -h
```

### Edge Device Statistics

Statistics are logged every 10 scans:

```
============================================================
EDGE DEVICE STATISTICS
Scans completed: 10
Total faces detected: 25
Total faces sent: 23
Queue size: 2/500
Queue utilization: 0.4%
Queue stats: enqueued=2, dropped=0, succeeded=0, failed=0
============================================================
```

## API Contract

### POST /api/v1/face/process

Request payload:

```json
{
  "room_id": "uuid-room-301",
  "timestamp": "2024-01-15T10:00:00Z",
  "faces": [
    {
      "image": "base64_encoded_jpeg_data",
      "bbox": [100, 150, 112, 112]
    }
  ]
}
```

Response:

```json
{
  "success": true,
  "data": {
    "processed": 3,
    "matched": [
      {"user_id": "uuid-student-1", "confidence": 0.85},
      {"user_id": "uuid-student-2", "confidence": 0.92}
    ],
    "unmatched": 1
  }
}
```

## Development

### Run Tests

```bash
# Unit tests (if available)
pytest tests/

# Integration tests with camera
python -m app.main --test-mode
```

### Debug Mode

Enable debug logging:

```bash
# In .env
LOG_LEVEL=DEBUG
```

Run with verbose output:

```bash
python run.py 2>&1 | tee edge.log
```

## License

Copyright © 2024 JRMSU IAMS. All rights reserved.

## Support

For issues and questions:
- GitHub: https://github.com/yourusername/iams
- Email: support@yourdomain.com
