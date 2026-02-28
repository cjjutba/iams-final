# Step 9: Build the Android APK

Build a standalone APK file that can be installed on student phones without needing a development setup.

---

## Prerequisites

- Mobile app dependencies installed (Step 8)
- Android Studio + Android SDK installed (Step 1)
- `ANDROID_HOME` environment variable set (Step 1)

---

## Option A: Build with Gradle (Recommended)

### Step 1: Navigate to the Android folder

**Windows:**
```bash
cd mobile\android
```

**Linux/Mac:**
```bash
cd mobile/android
```

### Step 2: Build the APK

**Windows:**
```bash
gradlew.bat assembleRelease
```

**Linux/Mac:**
```bash
./gradlew assembleRelease
```

The build takes a few minutes. When finished, the APK is at:

```
mobile/android/app/build/outputs/apk/release/app-release.apk
```

---

## Option B: Build via Expo (Development Build)

If you're testing with a USB cable connected:

```bash
cd mobile
pnpm android
```

This installs the app directly on the connected phone.

---

## Distributing the APK to Students

Since the system runs on a local network, students install the APK using one of these methods:

### Method 1: Direct File Transfer (Simplest)
1. Copy the `app-release.apk` file to a USB drive or share via Bluetooth
2. Students open the APK file on their phone
3. Tap "Install"

### Method 2: Share via Local Network
1. Place the APK in a shared folder accessible on the local network
2. Students download from their phone's browser

### Method 3: QR Code
1. Host the APK on the backend server or a simple HTTP server
2. Generate a QR code pointing to the download URL
3. Students scan the QR code to download

---

## Enable Installation from Unknown Sources

Students need to allow installing apps from outside the Play Store:

### Android 8.0+
1. When they try to install the APK, Android will prompt:
   **"For your security, your phone is not allowed to install unknown apps from this source"**
2. Tap **"Settings"**
3. Toggle on **"Allow from this source"**
4. Go back and tap **"Install"**

### Older Android
1. Go to **Settings > Security**
2. Enable **"Unknown Sources"**

---

## APK File Size

The APK is approximately **30-50 MB** depending on the build configuration. This is a one-time download — once installed, the app works entirely over the local network.

---

**Next step:** [10 - Connect on Local Network](../10-connect-local-network/README.md)
