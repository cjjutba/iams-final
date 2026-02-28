# Step 8: Set Up the Mobile App

The mobile app is built with React Native (Expo) and runs on Android phones. It's used by both students (registration, attendance) and faculty (dashboard, live feed, attendance management).

---

## Prerequisites

- Node.js 18+ installed (Step 1)
- pnpm installed (Step 1)

---

## Step 8.1: Open a new terminal

Keep the backend server running in its terminal. Open a **new terminal** for the mobile app.

---

## Step 8.2: Navigate to the mobile folder

```bash
cd mobile
```

---

## Step 8.3: Install dependencies

```bash
pnpm install
```

This downloads all JavaScript packages the mobile app needs. First time takes a few minutes.

---

## Step 8.4: Network Configuration (Auto-Detected)

The mobile app **automatically detects** the backend server IP address from your development machine. In most cases, you don't need to configure anything.

### If auto-detection doesn't work

If the mobile app can't connect to the backend, you can manually set the IP:

1. Find your laptop's IP address:

   **Windows:**
   ```bash
   ipconfig
   ```
   Look for **"IPv4 Address"** under your Wi-Fi adapter (e.g., `192.168.1.3`)

   **Linux/Mac:**
   ```bash
   ifconfig
   ```
   or
   ```bash
   ip addr show
   ```

2. Open the file `mobile/.env`

3. Uncomment and edit these lines:
   ```
   EXPO_PUBLIC_API_BASE_URL=http://192.168.1.3:8000/api/v1
   EXPO_PUBLIC_WS_BASE_URL=ws://192.168.1.3:8000/api/v1/ws
   ```
   Replace `192.168.1.3` with your actual laptop IP address.

---

## Step 8.5: Run the app in development mode (optional)

If you want to test the app during development:

1. Connect your Android phone via USB cable
2. Enable **USB Debugging** on your phone:
   - Go to Settings > About Phone > tap "Build Number" 7 times
   - Go to Settings > Developer Options > enable "USB Debugging"
3. Run:
   ```bash
   pnpm android
   ```

This builds and installs the development version directly on your phone.

---

## What You Just Set Up

- **React Native (Expo)** — Cross-platform mobile framework
- **React Navigation** — Screen navigation (tabs, stacks)
- **Zustand** — State management
- **Axios** — HTTP client for API calls
- **expo-camera** — Camera access for face registration
- **expo-video** — Video player for live camera feed

---

**Next step:** [09 - Build the Android APK](../09-build-android-apk/README.md)
