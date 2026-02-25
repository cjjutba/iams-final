# Step 1: Prerequisites

Install the following software on the **backend machine** (the laptop/desktop that will run the server).

---

## Required Software

| # | Software | Version | Purpose |
|---|----------|---------|---------|
| 1 | Git | Latest | Clone the repository |
| 2 | Python | 3.11+ | Backend server |
| 3 | Docker Desktop | Latest | PostgreSQL database |
| 4 | Node.js | 18+ | Mobile app build tools |
| 5 | pnpm | Latest | Mobile app package manager |
| 6 | Android Studio | Latest | Android SDK + APK building |
| 7 | FFmpeg | Latest | Live camera streaming |

---

## 1. Install Git

1. Download from https://git-scm.com/downloads
2. Run the installer with default settings
3. Verify installation — open a terminal and run:
   ```
   git --version
   ```
   Expected output: `git version 2.x.x`

---

## 2. Install Python

1. Download Python **3.11 or newer** from https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT:** Check the box that says **"Add Python to PATH"** before clicking Install
4. Verify installation:
   ```
   python --version
   ```
   Expected output: `Python 3.11.x` (or newer)

---

## 3. Install Docker Desktop

1. Download from https://www.docker.com/products/docker-desktop/
2. Run the installer
3. **Restart your computer** if prompted
4. Open Docker Desktop and wait until it says **"Docker is running"** at the bottom left
5. Verify installation:
   ```
   docker --version
   ```
   Expected output: `Docker version 2x.x.x`

---

## 4. Install Node.js

1. Download the **LTS** version from https://nodejs.org/
2. Run the installer with default settings
3. Verify installation:
   ```
   node --version
   ```
   Expected output: `v18.x.x` (or newer)

---

## 5. Install pnpm

1. Open a terminal and run:
   ```
   npm install -g pnpm
   ```
2. Verify installation:
   ```
   pnpm --version
   ```
   Expected output: `9.x.x` (or newer)

---

## 6. Install Android Studio

This is needed to build the Android APK.

1. Download from https://developer.android.com/studio
2. Run the installer — make sure to install the **Android SDK** when asked
3. After installation, open Android Studio:
   - Go to **Settings** (or Preferences) > **SDK Manager**
   - Install **Android SDK Platform 34** (or the latest version)
4. Set the `ANDROID_HOME` environment variable:

   **Windows:**
   - Open Start Menu > search "Environment Variables"
   - Click "Edit the system environment variables" > "Environment Variables"
   - Under User variables, click "New":
     - Variable name: `ANDROID_HOME`
     - Variable value: `C:\Users\<YourUsername>\AppData\Local\Android\Sdk`
   - Edit the `Path` variable and add: `%ANDROID_HOME%\platform-tools`

   **Linux/Mac:**
   ```bash
   echo 'export ANDROID_HOME=$HOME/Android/Sdk' >> ~/.bashrc
   echo 'export PATH=$PATH:$ANDROID_HOME/platform-tools' >> ~/.bashrc
   source ~/.bashrc
   ```

---

## 7. Install FFmpeg

FFmpeg is used for live camera streaming (HLS).

**Windows:**
```
winget install ffmpeg
```

**Linux (Ubuntu/Debian):**
```
sudo apt install ffmpeg
```

**macOS:**
```
brew install ffmpeg
```

Verify installation:
```
ffmpeg -version
```

---

## Checklist

Before proceeding, verify all software is installed:

- [ ] `git --version` works
- [ ] `python --version` shows 3.11+
- [ ] `docker --version` works and Docker Desktop is running
- [ ] `node --version` shows 18+
- [ ] `pnpm --version` works
- [ ] Android Studio installed with Android SDK
- [ ] `ffmpeg -version` works

---

**Next step:** [02 - Clone the Repository](../02-clone-repository/README.md)
