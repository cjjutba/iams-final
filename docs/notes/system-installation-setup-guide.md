# IAMS: System Installation & Setup Guide
## Complete Hardware Installation Reference for EB 226 & EB 227

**Version:** 1.0
**Date:** April 3, 2026
**Prepared by:** CJ Jutba
**Institution:** Jose Rizal Memorial State University (JRMSU)
**Program:** Bachelor of Science in Computer Engineering (BSCpE)

---

## Table of Contents

1. [Equipment Inventory](#1-equipment-inventory)
2. [System Overview for Installers](#2-system-overview-for-installers)
3. [Network Topology Diagram](#3-network-topology-diagram)
4. [Step 1: Install the MikroTik Router](#4-step-1-install-the-mikrotik-router)
5. [Step 2: Install the TP-Link Switch](#5-step-2-install-the-tp-link-switch)
6. [Step 3: Run Ethernet Cables](#6-step-3-run-ethernet-cables)
7. [Step 4: Mount and Connect Camera — EB 226 (Reolink RLC-510A/P340)](#7-step-4-mount-and-connect-camera--eb-226)
8. [Step 5: Mount and Connect Camera — EB 227 (Reolink CX810)](#8-step-5-mount-and-connect-camera--eb-227)
9. [Step 6: Configure the Cameras on the Network](#9-step-6-configure-the-cameras-on-the-network)
10. [Step 7: Set Up the Raspberry Pi Units](#10-step-7-set-up-the-raspberry-pi-units)
11. [Step 8: Power On and Verify Connections](#11-step-8-power-on-and-verify-connections)
12. [Complete Wiring Diagram](#12-complete-wiring-diagram)
13. [IP Address Reference Table](#13-ip-address-reference-table)
14. [Credential Reference](#14-credential-reference)
15. [Troubleshooting Guide](#15-troubleshooting-guide)
16. [Maintenance Notes](#16-maintenance-notes)

---

## 1. Equipment Inventory

Before starting installation, verify that all the following equipment and materials are available.

### 1.1 Networking Equipment

| Item | Qty | Model | Purpose |
|------|-----|-------|---------|
| MikroTik Router | 1 | hAP lite (RB941-2nD-TC) | Central router, WiFi access point, DHCP server |
| TP-Link Switch | 1 | 5-Port or 8-Port Gigabit Unmanaged Switch | Wired Ethernet distribution for cameras |
| Ethernet Cable (Cat5e/Cat6) | 4+ | Various lengths (see Section 6) | Network connections |

### 1.2 Cameras

| Item | Qty | Model | Assigned Room |
|------|-----|-------|---------------|
| IP Camera #1 | 1 | Reolink P340 | EB 226 |
| IP Camera #2 | 1 | Reolink CX810 | EB 227 |
| PoE Injector or Power Adapter | 2 | Included with cameras | Camera power supply |
| Mounting screws & anchors | 2 sets | Included with cameras | Ceiling/wall mounting |

### 1.3 Edge Devices (Raspberry Pi)

| Item | Qty | Model | Assigned Room |
|------|-----|-------|---------------|
| Raspberry Pi #1 | 1 | Raspberry Pi 4 (4GB RAM) | EB 226 |
| Raspberry Pi #2 | 1 | Raspberry Pi 4 (2GB RAM) | EB 227 |
| MicroSD Card (pre-configured) | 2 | 64GB | Pre-loaded with Raspberry Pi OS + IAMS relay software |
| USB-C Power Supply | 2 | 5V/3A official RPi PSU | Raspberry Pi power |
| MicroSD Card Reader | 1 | (optional, for re-imaging) | — |

### 1.4 Cabling & Accessories

| Item | Qty | Purpose |
|------|-----|---------|
| Ethernet Cable — Short (0.5m–1m) | 2 | Router-to-switch, switch-to-nearby device |
| Ethernet Cable — Medium (5m–10m) | 2 | Switch-to-camera runs within each room |
| Ethernet Cable — Long (15m–30m) | 1–2 | If router/switch is centrally located between rooms |
| Cable ties / clips | Pack | Tidy cable management along walls/ceiling |
| Power strip / extension cord | 1–2 | Power for router, switch, RPi units |
| Ladder | 1 | Camera mounting (ceiling installation) |
| Drill + drill bits | 1 | Ceiling/wall mounting holes |
| Screwdriver set | 1 | Camera and mount assembly |

### 1.5 Pre-Configured (Already Done — No Setup Needed)

| Item | Status |
|------|--------|
| Cloud VPS (DigitalOcean) | Running at 167.71.217.44 — Backend, mediamtx, database all deployed |
| Android App (APK) | Built and ready for installation on student/faculty phones |
| FAISS Face Index | Initialized on VPS, ready for face registrations |
| RPi MicroSD Cards | Pre-imaged with OS + relay software + systemd service |

---

## 2. System Overview for Installers

### 2.1 What This System Does

IAMS is an automated attendance system. IP cameras in classrooms capture video of students. The video is relayed through Raspberry Pi devices to a cloud server, where AI identifies students by their faces and records attendance automatically. Faculty can view a live feed with student names overlaid on their Android phones.

### 2.2 How the Pieces Connect

```
                         CLASSROOM EB 226                    CLASSROOM EB 227
                    ┌─────────────────────┐             ┌─────────────────────┐
                    │                     │             │                     │
                    │   Reolink P340      │             │   Reolink CX810     │
                    │   (ceiling mount)   │             │   (ceiling mount)   │
                    │        │            │             │        │            │
                    │        │ Ethernet   │             │        │ Ethernet   │
                    └────────┼────────────┘             └────────┼────────────┘
                             │                                   │
                             │          NETWORK CLOSET           │
                             │      (or central location)        │
                             │    ┌─────────────────────┐        │
                             └───>│   TP-Link Switch    │<───────┘
                                  │   (5/8-port)        │
                                  └─────────┬───────────┘
                                            │ Ethernet
                                            │
                                  ┌─────────┴───────────┐
                                  │   MikroTik Router    │
                                  │   hAP lite           │
                                  │   (IAMS-Net WiFi)    │
                                  └─────────┬───────────┘
                                            │
                              ┌─────────────┼─────────────┐
                              │ WiFi        │ WAN          │ WiFi
                              v             v              v
                         RPi EB226    ISP Router      RPi EB227
                        (plugged in   (Internet)     (plugged in
                         anywhere)                    anywhere)
                              │                            │
                              │    ┌──────────────────┐    │
                              └───>│   Cloud VPS      │<───┘
                                   │   (Internet)     │
                                   │   167.71.217.44  │
                                   └──────────────────┘
```

### 2.3 Key Concept: Wired vs. Wireless

| Device | Connection Type | Why |
|--------|----------------|-----|
| IP Cameras | **Wired (Ethernet)** | Cameras need reliable, high-bandwidth connections for continuous video streaming. WiFi can drop frames. |
| MikroTik Router | **Wired (WAN)** + WiFi broadcast | WAN port connects to ISP for internet. Broadcasts IAMS-Net WiFi for RPi units. |
| TP-Link Switch | **Wired (Ethernet)** | Connects cameras to the router via Ethernet. |
| Raspberry Pi units | **Wireless (WiFi)** | Connect to IAMS-Net WiFi. Can be placed anywhere with power and WiFi signal. Plug-and-play. |

---

## 3. Network Topology Diagram

```
                    ┌────────────────────────────────────────────────────────────────┐
                    │                     IAMS LOCAL NETWORK                         │
                    │                     Subnet: 192.168.88.0/24                    │
                    │                                                                │
                    │   ┌──────────────────────────────┐                             │
                    │   │  MikroTik hAP lite           │                             │
                    │   │  IP: 192.168.88.1            │                             │
                    │   │  SSID: IAMS-Net              │                             │
                    │   │  Pass: iamsthesis123         │                             │
                    │   │                              │                             │
                    │   │  ether1 (WAN) ─── ISP Router │───── INTERNET ──── VPS      │
                    │   │  ether2-4 ─────── TP-Link SW │                             │
                    │   │  WiFi ─── RPi x2             │                             │
                    │   └──────────────────────────────┘                             │
                    │                    │                                            │
                    │          ┌─────────┴──────────┐                                │
                    │          │   TP-Link Switch    │                                │
                    │          │   (unmanaged)       │                                │
                    │          └─┬──────────────────┬┘                                │
                    │            │                  │                                 │
                    │    ┌───────┴──────┐   ┌──────┴───────┐                         │
                    │    │ Reolink P340 │   │ Reolink CX810│                         │
                    │    │ 192.168.88.10│   │ 192.168.88.11│                         │
                    │    │ (EB 226)     │   │ (EB 227)     │                         │
                    │    └──────────────┘   └──────────────┘                         │
                    │                                                                │
                    │    ┌──────────────┐   ┌──────────────┐  (WiFi connected)       │
                    │    │ RPi EB226    │   │ RPi EB227    │                         │
                    │    │ 192.168.88.12│   │ 192.168.88.15│                         │
                    │    └──────────────┘   └──────────────┘                         │
                    └────────────────────────────────────────────────────────────────┘
```

---

## 4. Step 1: Install the MikroTik Router

### 4.1 Choose a Location

- Place the MikroTik router in a **central location** between EB 226 and EB 227, ideally in a network closet, office, or on a shelf near a wall outlet.
- The router must be within Ethernet cable reach of the TP-Link switch.
- The router must also be within range of both RPi units over WiFi (the hAP lite covers about 20–30 meters indoors).

### 4.2 Connect the Router

1. **Connect WAN (Internet):**
   - Plug an Ethernet cable from the existing **ISP router** (school's internet source) into **ether1** (the first Ethernet port on the MikroTik, usually labeled "Internet" or "ether1").
   - This gives the IAMS network internet access, which the RPi units need to relay video to the cloud.

2. **Connect LAN (to switch):**
   - Plug an Ethernet cable from any of **ether2, ether3, or ether4** into the **TP-Link switch**.
   - This connects all wired devices (cameras) to the IAMS network.

3. **Power on the router:**
   - Plug in the MikroTik power adapter (micro-USB).
   - Wait about 30–60 seconds for it to boot. The LED lights will stabilize.

### 4.3 Router Configuration (Pre-Configured)

The MikroTik router has already been configured with the following settings. **No configuration changes are needed** — just plug it in:

| Setting | Value |
|---------|-------|
| Router IP | 192.168.88.1 |
| DHCP Range | 192.168.88.100 – 192.168.88.254 |
| WiFi SSID | IAMS-Net |
| WiFi Password | iamsthesis123 |
| WAN (ether1) | DHCP Client (auto-obtains IP from ISP router) |
| LAN (ether2-4) | Bridged, 192.168.88.0/24 subnet |

### 4.4 Verify the Router

After powering on:
1. On a phone or laptop, look for the **IAMS-Net** WiFi network.
2. Connect using password: `iamsthesis123`
3. Open a browser and navigate to `http://192.168.88.1` — you should see the MikroTik WebFig management page.
4. The router is working if you can connect to WiFi and access the management page.

---

## 5. Step 2: Install the TP-Link Switch

### 5.1 Choose a Location

- Place the TP-Link switch **next to the MikroTik router** or in a central location where Ethernet cables from both classrooms can reach it.
- The switch is unmanaged (no configuration needed) — it simply extends the number of available Ethernet ports.

### 5.2 Connect the Switch

1. **Connect to Router:**
   - Plug a short Ethernet cable from **any port on the TP-Link switch** to **ether2 (or ether3/ether4) on the MikroTik router**.

2. **Power on:**
   - Plug in the switch's power adapter.
   - The port LEDs will light up when devices are connected.

3. **Reserve ports for cameras:**
   - **Port 1:** Ethernet cable to EB 226 camera (Reolink P340)
   - **Port 2:** Ethernet cable to EB 227 camera (Reolink CX810)
   - **Port 3:** Uplink to MikroTik router
   - Remaining ports: available for future use

### 5.3 Why a Switch?

The MikroTik hAP lite only has 4 Ethernet ports (1 WAN + 3 LAN). The switch provides additional ports and allows clean cable management. Since the switch is unmanaged, it requires zero configuration — just plug in and go.

---

## 6. Step 3: Run Ethernet Cables

### 6.1 Cable Planning

You need Ethernet cables (Cat5e or Cat6) for the following runs:

| Cable Run | From | To | Estimated Length | Notes |
|-----------|------|----|-----------------|-------|
| **Cable A** | MikroTik ether1 | ISP Router (school internet) | 1m–5m | Depends on ISP router location |
| **Cable B** | MikroTik ether2 | TP-Link Switch (any port) | 0.5m–1m | Short patch cable if co-located |
| **Cable C** | TP-Link Switch (port 1) | Reolink P340 in EB 226 | 5m–30m | Run along ceiling/wall to camera |
| **Cable D** | TP-Link Switch (port 2) | Reolink CX810 in EB 227 | 5m–30m | Run along ceiling/wall to camera |

### 6.2 Cable Routing Best Practices

1. **Measure before cutting** — measure the actual cable path (along walls, through ceiling tiles, around door frames), not straight-line distance. Add 1–2 meters of slack.
2. **Avoid running parallel to power cables** — Ethernet cables near high-voltage power lines can pick up interference. Keep at least 15cm separation, or cross power cables at 90-degree angles.
3. **Use cable clips or ties** — secure cables along walls, ceiling edges, or cable trays for a clean installation. Do not leave cables hanging loose.
4. **Label both ends** — use tape or cable labels to mark each cable (e.g., "EB226-CAM", "EB227-CAM"). This makes troubleshooting much easier later.
5. **Protect cables in high-traffic areas** — use cable covers or conduit where cables cross doorways or walkways.
6. **Test after running** — plug each cable into the switch and a laptop at the other end. If the link LED lights up, the cable is good.

### 6.3 If Rooms Are Far Apart

If EB 226 and EB 227 are far from the central network location:
- Consider placing the switch and router in a hallway closet or office between both rooms.
- Maximum Ethernet cable length is **100 meters** — this should be more than enough for any classroom building.
- For very long runs, consider using pre-terminated Cat6 cable or hiring a low-voltage installer.

### 6.4 Through-Wall Runs

If cables need to pass through walls:
1. Drill a small hole (just large enough for the RJ45 connector, about 15mm).
2. Feed the cable through.
3. Seal around the hole with putty or a wall plate to maintain a clean appearance.
4. Alternatively, run cables through existing cable conduits or ceiling spaces if available.

---

## 7. Step 4: Mount and Connect Camera — EB 226

### Camera: Reolink P340

### 7.1 Choose Mounting Position

- **Location:** Front of the classroom, mounted on the ceiling or high on the front wall, facing the student seating area.
- **Height:** 2.5–3.5 meters from the floor (standard ceiling height is ideal).
- **Angle:** Tilt downward at approximately 15–30 degrees to capture students' faces clearly.
- **Coverage:** The camera should see the majority of student seats. Position it so that most students face toward the camera (i.e., mount it at the front of the room where the teacher stands, facing the students).
- **Avoid:** Mounting directly above a window — strong backlight will wash out faces. Mount away from direct sunlight.

### 7.2 Physical Mounting

1. **Mark drill holes:** Hold the camera mounting bracket against the ceiling/wall at the chosen location. Use a pencil to mark the screw holes.
2. **Drill pilot holes:** Use the drill to make holes at the marked positions. If mounting on concrete, use wall anchors.
3. **Insert anchors:** Push the plastic wall anchors into the drilled holes (if on concrete/masonry).
4. **Attach the mounting bracket:** Screw the bracket into the anchors/holes using the provided screws.
5. **Attach the camera:** Snap or screw the camera body onto the mounting bracket. Adjust the angle so it faces the student seating area.
6. **Hand-tighten:** Once positioned, tighten all adjustment screws so the camera does not shift.

### 7.3 Connect the Camera

1. **Ethernet:** Plug the Ethernet cable (Cable C from Section 6) into the camera's Ethernet port.
2. **Power:** The Reolink P340 supports PoE (Power over Ethernet). If your TP-Link switch supports PoE, the camera will power on from the Ethernet cable alone. **If the switch does NOT support PoE**, use the included PoE injector:
   - Plug the Ethernet cable from the switch into the **"LAN IN"** port of the PoE injector.
   - Plug a short Ethernet cable from the **"PoE OUT"** port of the injector to the camera.
   - Plug the PoE injector's power adapter into a wall outlet near the switch.
3. **Verify power:** The camera should show an IR glow (visible as faint red LEDs in low light) or you should hear a click as it initializes. Wait 1–2 minutes for full boot.

### 7.4 Reolink P340 Specifications (Reference)

| Specification | Value |
|---------------|-------|
| Resolution | 2304 x 1296 (4MP) |
| Frame Rate | Up to 20 fps |
| Video Codec | H.264 |
| Night Vision | IR LEDs (infrared, works in darkness) |
| Network | 100Mbps Ethernet (PoE supported) |
| RTSP Stream | `rtsp://admin:<password>@192.168.88.10:554/h264Preview_01_main` |

---

## 8. Step 5: Mount and Connect Camera — EB 227

### Camera: Reolink CX810

### 8.1 Choose Mounting Position

- Follow the same guidelines as EB 226 (Section 7.1): front of the classroom, ceiling-mounted, facing student seating.
- The CX810 has a wider field of view, so it may cover more of the room from the same position.

### 8.2 Physical Mounting

Follow the same steps as Section 7.2 — drill, anchor, bracket, camera, tighten.

### 8.3 Connect the Camera

1. **Ethernet:** Plug the Ethernet cable (Cable D from Section 6) into the camera's Ethernet port.
2. **Power:** The Reolink CX810 also supports PoE. Same process as Section 7.3 — either PoE switch or PoE injector.
3. **Verify power:** Wait 1–2 minutes for the camera to boot.

### 8.4 Reolink CX810 Specifications (Reference)

| Specification | Value |
|---------------|-------|
| Resolution | 2304 x 1296 (4MP) or higher |
| Frame Rate | Up to 20 fps |
| Video Codec | H.264 |
| Night Vision | ColorX (full-color night vision with spotlight) |
| Network | 100Mbps Ethernet (PoE supported) |
| RTSP Stream | `rtsp://admin:<password>@192.168.88.11:554/h264Preview_01_main` |

---

## 9. Step 6: Configure the Cameras on the Network

### 9.1 Initial Camera Discovery

After both cameras are powered on and connected via Ethernet:

1. **Download the Reolink App** on a phone or the **Reolink Client** on a laptop.
2. Connect your phone/laptop to the **IAMS-Net** WiFi.
3. Open the Reolink App — it will auto-discover cameras on the local network.

### 9.2 Set Static IP Addresses

Each camera must have a fixed (static) IP address so the Raspberry Pi relays always know where to find them.

**Camera 1 — EB 226 (Reolink P340):**

1. In the Reolink App, tap on the discovered camera.
2. Go to **Settings > Network > Network Information**.
3. Change from DHCP to **Static**.
4. Set:
   - IP Address: `192.168.88.10`
   - Subnet Mask: `255.255.255.0`
   - Default Gateway: `192.168.88.1`
   - DNS: `8.8.8.8`
5. Save and wait for the camera to restart.

**Camera 2 — EB 227 (Reolink CX810):**

1. Same process as above.
2. Set:
   - IP Address: `192.168.88.11`
   - Subnet Mask: `255.255.255.0`
   - Default Gateway: `192.168.88.1`
   - DNS: `8.8.8.8`
3. Save and wait for the camera to restart.

### 9.3 Set Camera Passwords

Both cameras should use the same admin password for simplicity:

| Setting | Value |
|---------|-------|
| Username | admin |
| Password | @Iams2026THESIS! |

Set this password during the camera's initial setup wizard in the Reolink App.

### 9.4 Configure Video Stream Settings

For optimal face recognition performance, configure each camera's main stream:

| Setting | Recommended Value |
|---------|-------------------|
| Resolution | 2304 x 1296 (maximum) |
| Frame Rate | 20 fps |
| Bitrate | 4096 kbps (or "High") |
| Encoding | H.264 |
| I-Frame Interval | 1 second (or 20 frames) |

Also configure the sub-stream (lower quality, used as backup):

| Setting | Recommended Value |
|---------|-------------------|
| Resolution | 640 x 360 |
| Frame Rate | 15 fps |
| Encoding | H.264 |

### 9.5 Verify RTSP Access

After configuration, verify that RTSP streams are accessible:

1. Connect a laptop to **IAMS-Net** WiFi.
2. Install **VLC Media Player**.
3. Open VLC > **Media > Open Network Stream**.
4. Enter the RTSP URL for Camera 1:
   ```
   rtsp://admin:%40Iams2026THESIS%21@192.168.88.10:554/h264Preview_01_main
   ```
   (Note: `%40` = `@` and `%21` = `!` — these are URL-encoded special characters in the password)
5. You should see the live camera feed. Repeat for Camera 2:
   ```
   rtsp://admin:%40Iams2026THESIS%21@192.168.88.11:554/h264Preview_01_main
   ```

If both streams display video in VLC, the cameras are correctly configured.

---

## 10. Step 7: Set Up the Raspberry Pi Units

### 10.1 Overview

The Raspberry Pi units are **pre-configured and plug-and-play**. Each MicroSD card has been pre-loaded with:
- Raspberry Pi OS (64-bit)
- FFmpeg (video relay software)
- IAMS relay service (auto-starts on boot)
- WiFi credentials for IAMS-Net

**You do not need to connect a monitor, keyboard, or mouse to the RPi.** Just plug in power and it works.

### 10.2 Set Up RPi #1 (EB 226)

1. **Insert the MicroSD card** labeled "EB226" into the Raspberry Pi 4 (4GB).
2. **Place the RPi** anywhere with:
   - A power outlet (for the USB-C power supply)
   - WiFi signal from the IAMS-Net router
   - Does NOT need to be in the classroom — can be in a nearby office, closet, or corridor as long as WiFi reaches.
3. **Plug in the USB-C power supply.** The RPi will boot automatically.
4. **Wait 1–2 minutes.** The RPi will:
   - Boot into Raspberry Pi OS
   - Connect to IAMS-Net WiFi automatically
   - Start the `iams-relay` systemd service
   - Begin relaying the EB 226 camera stream to the cloud VPS

### 10.3 Set Up RPi #2 (EB 227)

1. **Insert the MicroSD card** labeled "EB227" into the Raspberry Pi 4 (2GB).
2. Follow the same steps as above — place it, plug in power, wait.
3. This RPi relays the EB 227 camera stream to the cloud.

### 10.4 RPi Technical Details (Reference)

| Detail | RPi #1 (EB 226) | RPi #2 (EB 227) |
|--------|------------------|------------------|
| Hostname | iams-eb226 | iams-eb227 |
| Username | iams-eb226 | iams-eb227 |
| Password | 123 | 123 |
| Static IP | 192.168.88.12 | 192.168.88.15 |
| RAM | 4GB | 2GB |
| WiFi Network | IAMS-Net | IAMS-Net |
| Service | iams-relay (auto-start) | iams-relay (auto-start) |
| CPU Usage | ~1–6% (relay only) | ~1–6% (relay only) |

### 10.5 What the RPi Does (Simplified)

The RPi runs a single background process:
1. Connects to the camera's RTSP stream on the local network.
2. Uses FFmpeg to relay (copy, no processing) the stream to the cloud VPS at `rtsp://167.71.217.44:8554`.
3. If the connection drops, it automatically reconnects within seconds.
4. The RPi does **NO** face detection, face recognition, or AI processing — it is a simple video relay.

### 10.6 If You Need to Re-image a MicroSD Card

If a MicroSD card is corrupted or lost:
1. Download **Raspberry Pi Imager** from https://www.raspberrypi.com/software/
2. Flash **Raspberry Pi OS Lite (64-bit)** onto a new MicroSD card.
3. Contact the developer for the IAMS relay setup script, which will install and configure everything automatically:
   ```bash
   bash edge/scripts/deploy-relay.sh eb226   # For EB 226 RPi
   bash edge/scripts/deploy-relay.sh eb227   # For EB 227 RPi
   ```

---

## 11. Step 8: Power On and Verify Connections

### 11.1 Power-On Sequence

Follow this order when powering on the system:

| Step | Device | Action | Wait Time |
|------|--------|--------|-----------|
| 1 | MikroTik Router | Plug in power | 60 seconds |
| 2 | TP-Link Switch | Plug in power | 10 seconds |
| 3 | Cameras (both) | Plug in PoE/power | 2 minutes |
| 4 | Raspberry Pi units (both) | Plug in USB-C | 2 minutes |

### 11.2 Verification Checklist

After all devices are powered on and have had time to boot (about 5 minutes total), verify each component:

#### Router Check
- [ ] Connect to **IAMS-Net** WiFi from a phone — should connect successfully
- [ ] Open `http://192.168.88.1` in a browser — MikroTik admin page loads
- [ ] Internet works (open any website)

#### Camera Check
- [ ] Open the Reolink App — both cameras appear as online
- [ ] Tap each camera — live video feed is visible
- [ ] Verify camera IPs: EB 226 = `192.168.88.10`, EB 227 = `192.168.88.11`

#### Raspberry Pi Check
- [ ] From a laptop connected to IAMS-Net, try to ping the RPi units:
  ```
  ping 192.168.88.12    (RPi EB226 — should respond)
  ping 192.168.88.15    (RPi EB227 — should respond)
  ```
- [ ] (Optional, advanced) SSH into the RPi to check the relay service:
  ```bash
  ssh iams-eb226@192.168.88.12    # Password: 123
  sudo systemctl status iams-relay
  ```
  The service should show as **active (running)**.

#### End-to-End Stream Check
- [ ] Open VLC on a laptop and try the **VPS RTSP stream** (not the local camera):
  ```
  rtsp://167.71.217.44:8554/eb226
  rtsp://167.71.217.44:8554/eb227
  ```
  If you see the classroom video through the VPS, the full pipeline is working:
  Camera → RPi → Cloud VPS → Your screen.

#### Android App Check
- [ ] Install the IAMS app on a phone.
- [ ] Login as a faculty account.
- [ ] Navigate to the Live Feed for EB 226 or EB 227.
- [ ] Verify: live video plays, face bounding boxes appear, attendance scanning works.

---

## 12. Complete Wiring Diagram

```
                              ISP ROUTER (School Internet)
                                     │
                                     │ Ethernet (Cable A)
                                     │
    ┌────────────────────────────────┴────────────────────────────────┐
    │                    MikroTik hAP lite                            │
    │                    (192.168.88.1)                               │
    │                                                                 │
    │   [ether1/WAN]  [ether2]  [ether3]  [ether4]   [WiFi]         │
    │       ▲            │                             │    │        │
    │       │            │                            RPi1  RPi2     │
    │    From ISP        │                           EB226  EB227    │
    └────────────────────┼───────────────────────────────────────────┘
                         │ Ethernet (Cable B)
                         │
    ┌────────────────────┴───────────────────────────────────────────┐
    │                    TP-Link Switch                               │
    │                                                                 │
    │   [Port 1]    [Port 2]    [Port 3]    [Port 4]    [Port 5]    │
    │      │           │           ▲                                  │
    │      │           │           │                                  │
    └──────┼───────────┼───────────┼─────────────────────────────────┘
           │           │           │
           │           │        From MikroTik ether2 (Cable B)
           │           │
   Ethernet (Cable C)  Ethernet (Cable D)
           │           │
           ▼           ▼
    ┌──────────┐  ┌──────────┐
    │ Reolink  │  │ Reolink  │
    │ P340     │  │ CX810    │
    │ EB 226   │  │ EB 227   │
    │ .88.10   │  │ .88.11   │
    └──────────┘  └──────────┘

    WiFi Devices (no cables needed):
    ┌──────────┐  ┌──────────┐
    │ RPi 4    │  │ RPi 4    │
    │ EB 226   │  │ EB 227   │
    │ .88.12   │  │ .88.15   │
    │ 4GB RAM  │  │ 2GB RAM  │
    └──────────┘  └──────────┘
```

### Cable Summary

| Cable | From → To | Type | Length |
|-------|-----------|------|--------|
| **A** | ISP Router → MikroTik ether1 | Ethernet (Cat5e/Cat6) | 1–5m |
| **B** | MikroTik ether2 → TP-Link Switch | Ethernet (Cat5e/Cat6) | 0.5–1m |
| **C** | TP-Link Switch → Reolink P340 (EB 226) | Ethernet (Cat5e/Cat6) | 5–30m |
| **D** | TP-Link Switch → Reolink CX810 (EB 227) | Ethernet (Cat5e/Cat6) | 5–30m |

**Total Ethernet cables needed: 4**

---

## 13. IP Address Reference Table

| Device | IP Address | MAC Address | Connection | Room |
|--------|-----------|-------------|------------|------|
| MikroTik Router | 192.168.88.1 | (on device label) | — | Central |
| Reolink P340 | 192.168.88.10 | EC:71:DB:32:44:C9 | Wired (Ethernet) | EB 226 |
| Reolink CX810 | 192.168.88.11 | (on device label) | Wired (Ethernet) | EB 227 |
| RPi EB226 | 192.168.88.12 | 2C:CF:67:02:0D:FA | WiFi (IAMS-Net) | EB 226 (flexible) |
| RPi EB227 | 192.168.88.15 | D8:3A:DD:AD:A9:92 | WiFi (IAMS-Net) | EB 227 (flexible) |
| Cloud VPS | 167.71.217.44 | — | Internet | DigitalOcean |

---

## 14. Credential Reference

### 14.1 Network Credentials

| Item | Value |
|------|-------|
| WiFi SSID | IAMS-Net |
| WiFi Password | iamsthesis123 |
| MikroTik Admin URL | http://192.168.88.1 |
| MikroTik Admin User | admin |
| MikroTik Admin Password | (set during initial configuration — check with developer) |

### 14.2 Camera Credentials

| Item | Value |
|------|-------|
| Camera Username | admin |
| Camera Password | @Iams2026THESIS! |
| RTSP URL (EB 226 main) | `rtsp://admin:%40Iams2026THESIS%21@192.168.88.10:554/h264Preview_01_main` |
| RTSP URL (EB 226 sub) | `rtsp://admin:%40Iams2026THESIS%21@192.168.88.10:554/h264Preview_01_sub` |
| RTSP URL (EB 227 main) | `rtsp://admin:%40Iams2026THESIS%21@192.168.88.11:554/h264Preview_01_main` |
| RTSP URL (EB 227 sub) | `rtsp://admin:%40Iams2026THESIS%21@192.168.88.11:554/h264Preview_01_sub` |

### 14.3 Raspberry Pi Credentials

| Device | Username | Password | SSH Command |
|--------|----------|----------|-------------|
| RPi EB226 | iams-eb226 | 123 | `ssh iams-eb226@192.168.88.12` |
| RPi EB227 | iams-eb227 | 123 | `ssh iams-eb227@192.168.88.15` |

### 14.4 Cloud VPS

| Item | Value |
|------|-------|
| VPS IP | 167.71.217.44 |
| RTSP Relay URL | rtsp://167.71.217.44:8554 |
| Stream Paths | /eb226, /eb227 |
| Backend API | https://167.71.217.44/api/v1 |

---

## 15. Troubleshooting Guide

### 15.1 Camera Not Showing Video

| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| Camera not found in Reolink App | Not connected to network | Check Ethernet cable is firmly plugged into both camera and switch. Check switch port LED is lit. |
| Camera found but wrong IP | DHCP assigned different IP | Re-configure static IP per Section 9.2 |
| VLC shows "connection failed" for local RTSP | Wrong password in URL | Verify password special characters are URL-encoded (`@` = `%40`, `!` = `%21`) |
| Camera feed is black | Camera still booting | Wait 2 minutes after power-on. Check IR LEDs for signs of life. |
| Camera feed is washed out/too bright | Backlight from window | Reposition camera away from direct sunlight/windows |

### 15.2 Raspberry Pi Not Connecting

| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| Cannot ping RPi (192.168.88.12 or .15) | RPi not connected to WiFi | Ensure the MikroTik router is on and broadcasting IAMS-Net. Move RPi closer to the router. |
| RPi connected but relay not working | iams-relay service stopped | SSH in and run: `sudo systemctl restart iams-relay` |
| RPi not booting | MicroSD card issue | Re-seat the MicroSD card. If still not working, re-image (Section 10.6). |
| RPi has wrong IP | DHCP assigned different IP | Check MikroTik DHCP leases at `http://192.168.88.1` > IP > DHCP Server > Leases |

### 15.3 No Video on VPS / Android App

| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| VPS RTSP stream not working | RPi relay not running | Check RPi is on, connected to WiFi, and relay service is active |
| VPS stream works in VLC but not in app | App pointing to wrong URL | Verify app configuration matches VPS IP and stream paths |
| Intermittent stream drops | WiFi signal too weak for RPi | Move RPi closer to router, or consider adding a WiFi extender |
| Stream has high latency | Network congestion | Check ISP bandwidth. The relay uses ~2–4 Mbps per camera stream. |

### 15.4 Network Issues

| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| No internet on IAMS-Net | WAN cable disconnected | Check Cable A from ISP router to MikroTik ether1 |
| Devices can't see each other | Wrong subnet | Verify all devices are on 192.168.88.x subnet |
| Switch port LED not lit | Bad cable or port | Try a different port or cable. Test cable with another device. |

---

## 16. Maintenance Notes

### 16.1 Daily Operation

- **No daily maintenance required.** The system is designed to run unattended.
- The RPi relay services start automatically on boot.
- If there is a power outage, all devices will resume operation automatically once power is restored (follow the power-on sequence in Section 11.1 if doing a manual restart).

### 16.2 Periodic Checks (Monthly)

- [ ] Verify both camera feeds are clear and properly angled (check via Reolink App)
- [ ] Clean camera lenses with a soft, dry cloth if dusty
- [ ] Check that all Ethernet cables are secure (not loose or damaged)
- [ ] Verify RPi relay services are running (ping test or SSH check)
- [ ] Test the Android app — live feed should work for both rooms

### 16.3 If a Device Needs Replacement

| Device | Replacement Steps |
|--------|-------------------|
| **Camera** | Install new camera, set static IP (same as old), set password, verify RTSP URL format in VLC |
| **Raspberry Pi** | Insert pre-configured MicroSD, plug in power. If new MicroSD needed, run deploy script (Section 10.6) |
| **MikroTik Router** | Reconfigure with same settings (Section 4.3). All devices use static IPs so no DHCP dependency. |
| **TP-Link Switch** | Replace with any unmanaged gigabit switch. No configuration needed. |
| **Ethernet Cable** | Replace with same length Cat5e/Cat6. Test link LED on switch. |

### 16.4 Important Contacts

| Role | Contact | Notes |
|------|---------|-------|
| System Developer | CJ Jutba | For software issues, VPS problems, app updates |
| Network/Hardware | (installer name) | For physical wiring, camera repositioning |

---

## Appendix A: Quick-Start Checklist

For a rapid setup, follow this abbreviated checklist:

- [ ] **1.** Place MikroTik router centrally, connect WAN to ISP router
- [ ] **2.** Place TP-Link switch next to router, connect to router ether2
- [ ] **3.** Run Ethernet cable from switch to EB 226, connect to Reolink P340
- [ ] **4.** Run Ethernet cable from switch to EB 227, connect to Reolink CX810
- [ ] **5.** Power on cameras, set static IPs (192.168.88.10 and .11)
- [ ] **6.** Set camera password: `@Iams2026THESIS!`
- [ ] **7.** Verify camera RTSP streams in VLC
- [ ] **8.** Plug in RPi EB226 (MicroSD labeled EB226) — just power, no config
- [ ] **9.** Plug in RPi EB227 (MicroSD labeled EB227) — just power, no config
- [ ] **10.** Wait 5 minutes, then verify:
  - [ ] Ping both RPi units
  - [ ] Open VPS streams in VLC (`rtsp://167.71.217.44:8554/eb226` and `eb227`)
  - [ ] Open IAMS Android app — live feed works

**System is operational.**

---

## Appendix B: Physical Layout Recommendation

```
                        EB 226 CLASSROOM                         EB 227 CLASSROOM
    ┌──────────────────────────────────────┐    ┌──────────────────────────────────────┐
    │                                      │    │                                      │
    │   ┌──────────────────────────────┐   │    │   ┌──────────────────────────────┐   │
    │   │      WHITEBOARD / FRONT      │   │    │   │      WHITEBOARD / FRONT      │   │
    │   └──────────────────────────────┘   │    │   └──────────────────────────────┘   │
    │                                      │    │                                      │
    │          📷 CAMERA (ceiling)          │    │          📷 CAMERA (ceiling)          │
    │          Reolink P340                │    │          Reolink CX810                │
    │          Facing ↓ toward students    │    │          Facing ↓ toward students    │
    │                                      │    │                                      │
    │   ┌────┐ ┌────┐ ┌────┐ ┌────┐      │    │   ┌────┐ ┌────┐ ┌────┐ ┌────┐      │
    │   │desk│ │desk│ │desk│ │desk│      │    │   │desk│ │desk│ │desk│ │desk│      │
    │   └────┘ └────┘ └────┘ └────┘      │    │   └────┘ └────┘ └────┘ └────┘      │
    │   ┌────┐ ┌────┐ ┌────┐ ┌────┐      │    │   ┌────┐ ┌────┐ ┌────┐ ┌────┐      │
    │   │desk│ │desk│ │desk│ │desk│      │    │   │desk│ │desk│ │desk│ │desk│      │
    │   └────┘ └────┘ └────┘ └────┘      │    │   └────┘ └────┘ └────┘ └────┘      │
    │   ┌────┐ ┌────┐ ┌────┐ ┌────┐      │    │   ┌────┐ ┌────┐ ┌────┐ ┌────┐      │
    │   │desk│ │desk│ │desk│ │desk│      │    │   │desk│ │desk│ │desk│ │desk│      │
    │   └────┘ └────┘ └────┘ └────┘      │    │   └────┘ └────┘ └────┘ └────┘      │
    │                                      │    │                                      │
    │              DOOR                    │    │              DOOR                    │
    └──────────────────────────────────────┘    └──────────────────────────────────────┘

    Camera is mounted at the FRONT of the room, near the ceiling, angled downward
    to capture students' faces as they sit facing the whiteboard/teacher.

    Ethernet cable runs from camera → along ceiling/wall → to switch location.
```

---

*End of Installation Guide*
