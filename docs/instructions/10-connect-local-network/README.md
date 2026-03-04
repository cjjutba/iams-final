# Step 10: Connect Everything on the Local Network

All devices must be on the **same Wi-Fi network** for the system to work. No internet connection is required.

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Wi-Fi Router                            │
│                  (local network only)                       │
└──────┬──────────────┬────────────────┬─────────────────────┘
       │              │                │
       │              │                │
  ┌────▼────┐   ┌─────▼──────┐   ┌────▼─────────────────┐
  │ Laptop  │   │   Camera   │   │   Student/Faculty    │
  │ Server  │   │  (CCTV)    │   │   Android Phones     │
  │         │   │            │   │                      │
  │ Backend │   │ Reolink    │   │ IAMS App installed   │
  │ :8000   │   │ P340       │   │ via APK              │
  │         │   │            │   │                      │
  │ Docker  │   │ RTSP Feed  │   │ Connects to backend  │
  │ PG:5433 │   │ :554       │   │ via Wi-Fi            │
  └─────────┘   └────────────┘   └──────────────────────┘
```

---

## Requirements

1. **All devices** on the **same Wi-Fi network**
2. The laptop running the backend must have a **known IP address**
3. The CCTV camera must be accessible via RTSP on the same network

---

## Step 10.1: Find the laptop's IP address

This is the IP address that all phones and the camera will connect to.

**Windows:**
```bash
ipconfig
```
Look for the **"IPv4 Address"** under your **Wi-Fi adapter**:
```
Wireless LAN adapter Wi-Fi:
   IPv4 Address. . . . . . . . . . . : 192.168.1.3
```

**Linux/Mac:**
```bash
ifconfig
```
or
```bash
ip addr show wlan0
```

> Write this IP down — you'll need it if the mobile app can't auto-detect.

---

## Step 10.2: Verify phone can reach the backend

On a student/faculty phone connected to the same Wi-Fi:

1. Open the phone's web browser (Chrome)
2. Go to: `http://<laptop-ip>:8000/docs`
   - Example: `http://192.168.1.3:8000/docs`
3. You should see the Swagger API documentation page

If it doesn't load, see [Troubleshooting > Mobile app can't connect](../15-troubleshooting/README.md).

---

## Step 10.3: Set up the CCTV Camera

### Camera: Reolink P340

1. Connect the camera to the **same Wi-Fi network** as the laptop
2. Note the camera's IP address (default: `192.168.1.100`)
   - Check your router's admin page or use the Reolink app to find the IP
3. The RTSP URL is pre-configured in `backend/.env`:
   ```
   DEFAULT_RTSP_URL=rtsp://admin:Iams2026THESIS@192.168.1.100:554/h264Preview_01_sub
   ```

### If your camera has a different IP or password

Edit `backend/.env` and update:
```
DEFAULT_RTSP_URL=rtsp://<username>:<password>@<camera-ip>:554/h264Preview_01_sub
```

### Test the camera feed

Before using it with IAMS, test the camera with VLC media player:
1. Open VLC
2. Go to **Media > Open Network Stream**
3. Enter the RTSP URL: `rtsp://admin:Iams2026THESIS@192.168.1.100:554/h264Preview_01_sub`
4. Click "Play"
5. You should see the live camera feed

---

## Step 10.4: Windows Firewall

If phones can't connect to the backend, you may need to allow Python through the firewall:

1. Open **Start Menu** > search **"Windows Firewall"**
2. Click **"Allow an app or feature through Windows Defender Firewall"**
3. Click **"Change settings"** > **"Allow another app"**
4. Click **"Browse"** and navigate to your Python executable:
   ```
   C:\Projects\iams\backend\venv\Scripts\python.exe
   ```
5. Click **"Add"**
6. Make sure both **Private** and **Public** checkboxes are checked
7. Click **"OK"**

Alternatively, allow port 8000:
1. Open **Windows Firewall with Advanced Security**
2. Click **Inbound Rules > New Rule**
3. Select **Port** > **TCP** > **Specific local ports: 8000**
4. Select **Allow the connection**
5. Give it a name: "IAMS Backend"

---

## Network Diagram (Example IPs)

| Device | IP Address | Port | Purpose |
|--------|-----------|------|---------|
| Laptop (Backend) | 192.168.1.3 | 8000 | API server |
| Laptop (Docker PG) | localhost | 5433 | Database |
| CCTV Camera | 192.168.1.100 | 554 | RTSP video stream |
| Student Phone #1 | 192.168.1.20 | — | IAMS mobile app |
| Student Phone #2 | 192.168.1.21 | — | IAMS mobile app |
| Faculty Phone | 192.168.1.15 | — | IAMS mobile app |

> Your actual IP addresses will be different — these are examples.

---

**Next step:** [11 - Test Login Credentials](../11-test-credentials/README.md)
