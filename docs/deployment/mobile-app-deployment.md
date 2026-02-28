# Mobile App Deployment Guide

Complete guide for building and deploying the IAMS mobile application.

## Overview

The IAMS mobile app is built with React Native and Expo. This guide covers:
- Development builds (for testing)
- Pilot testing builds (APK for Android)
- Production deployment (App Store & Play Store)

## Prerequisites

- Node.js 18+ and pnpm installed
- Expo account (free): https://expo.dev
- EAS CLI installed: `npm install -g eas-cli`
- For iOS: macOS with Xcode, Apple Developer account ($99/year)
- For Android: Android Studio (optional)

## Quick Start (Pilot Testing)

### For Android APK (Recommended for Pilot)

1. **Install EAS CLI:**
   ```bash
   npm install -g eas-cli
   ```

2. **Login to Expo:**
   ```bash
   cd mobile
   eas login
   ```

3. **Configure project:**
   ```bash
   eas build:configure
   ```

4. **Update backend URL in eas.json:**
   ```json
   "pilot": {
     "env": {
       "API_BASE_URL": "http://YOUR_LAPTOP_IP:8000/api/v1",
       "WS_BASE_URL": "ws://YOUR_LAPTOP_IP:8000/api/v1/ws"
     }
   }
   ```

5. **Build APK:**
   ```bash
   eas build --platform android --profile pilot
   ```

6. **Download APK:**
   - Build completes in 10-20 minutes
   - Download from Expo dashboard or CLI link
   - Distribute APK to pilot testers

7. **Install on Android devices:**
   - Transfer APK via USB, email, or cloud storage
   - Enable "Install from unknown sources" on device
   - Install APK

## Development Setup

### Local Development

1. **Install dependencies:**
   ```bash
   cd mobile
   pnpm install
   ```

2. **Update .env file:**
   ```env
   API_BASE_URL=http://192.168.1.100:8000/api/v1
   WS_BASE_URL=ws://192.168.1.100:8000/api/v1/ws
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   ```

3. **Start Expo development server:**
   ```bash
   pnpm start
   ```

4. **Run on device:**
   - Install Expo Go app on your phone
   - Scan QR code from terminal
   - Ensure phone and laptop on same WiFi

### Development Build (Custom Native Code)

For features requiring native code (camera, etc.):

```bash
# Build for Android
eas build --platform android --profile development

# Build for iOS
eas build --platform ios --profile development

# Install on device
# Download development build and install via EAS CLI or dashboard
```

## Build Profiles

### 1. Development Profile

For development with Expo Go or development client.

**eas.json:**
```json
"development": {
  "developmentClient": true,
  "distribution": "internal",
  "android": {
    "buildType": "apk"
  },
  "env": {
    "API_BASE_URL": "http://192.168.1.100:8000/api/v1",
    "WS_BASE_URL": "ws://192.168.1.100:8000/api/v1/ws"
  }
}
```

**Build:**
```bash
eas build --platform android --profile development
```

### 2. Preview Profile

For internal testing without native dependencies.

**Build:**
```bash
eas build --platform android --profile preview
```

### 3. Pilot Profile

For pilot testing in classroom with local backend.

**Before building:**
1. Find backend laptop IP address
2. Update `eas.json` pilot profile with IP
3. Ensure backend allows CORS for mobile app

**Build:**
```bash
eas build --platform android --profile pilot
```

### 4. Production Profile

For App Store and Play Store release.

**Build:**
```bash
# Android (creates AAB for Play Store)
eas build --platform android --profile production

# iOS (creates IPA for App Store)
eas build --platform ios --profile production
```

## Android Deployment

### Pilot Testing (APK)

1. **Build APK:**
   ```bash
   eas build --platform android --profile pilot
   ```

2. **Wait for build:**
   - Monitor progress: `eas build:list`
   - Builds typically take 10-20 minutes
   - You'll receive email when complete

3. **Download APK:**
   ```bash
   # Download via CLI
   eas build:download --platform android --latest

   # Or download from Expo dashboard
   # https://expo.dev
   ```

4. **Distribute to testers:**
   - **Option A: USB Transfer**
     ```bash
     adb install app.apk
     ```

   - **Option B: Cloud Storage**
     - Upload to Google Drive, Dropbox, etc.
     - Share link with testers
     - Testers download and install

   - **Option C: Email**
     - Email APK directly (if < 25MB)
     - Testers download and install

5. **Installation instructions for testers:**
   ```
   1. Download APK to your Android device
   2. Go to Settings → Security → Enable "Install from unknown sources"
   3. Open downloaded APK file
   4. Tap "Install"
   5. Open IAMS app
   6. Ensure connected to same WiFi as backend
   ```

### Production (Play Store)

1. **Create Play Store account:**
   - Sign up at https://play.google.com/console
   - Pay $25 one-time fee

2. **Create app in Play Store Console:**
   - App name: IAMS
   - Default language: English
   - App type: App
   - Category: Education

3. **Setup app content:**
   - Content rating questionnaire
   - Target audience: 18+
   - Privacy policy URL (required)

4. **Build AAB:**
   ```bash
   eas build --platform android --profile production
   ```

5. **Upload to Play Store:**
   ```bash
   eas submit --platform android --profile production
   ```

6. **Complete store listing:**
   - Screenshots (required: phone, tablet)
   - App icon (512x512px)
   - Feature graphic (1024x500px)
   - Description
   - Privacy policy

7. **Submit for review:**
   - Internal testing (recommended first)
   - Closed testing (pilot testers)
   - Production release

## iOS Deployment

### Requirements

- macOS with Xcode
- Apple Developer account ($99/year)
- Code signing certificates

### TestFlight (Beta Testing)

1. **Enroll in Apple Developer Program:**
   - https://developer.apple.com
   - $99/year subscription

2. **Create App ID:**
   - Bundle identifier: `com.jrmsu.iams`
   - Configure capabilities (push notifications, etc.)

3. **Build for iOS:**
   ```bash
   eas build --platform ios --profile production
   ```

4. **Submit to TestFlight:**
   ```bash
   eas submit --platform ios --profile production
   ```

5. **Invite testers:**
   - App Store Connect → TestFlight
   - Add internal testers (up to 100)
   - Add external testers (requires App Review)
   - Share TestFlight link or send invites

6. **Testers install via TestFlight:**
   - Install TestFlight app from App Store
   - Open invitation link
   - Install IAMS app

### App Store (Production)

1. **Complete TestFlight testing**

2. **Create App Store listing:**
   - Screenshots (required: 6.5" and 5.5" displays)
   - App icon (1024x1024px)
   - Description
   - Keywords
   - Privacy policy URL (required)

3. **Submit for review:**
   - App Store Connect → App Store → Submit
   - Review typically takes 24-48 hours

4. **Release:**
   - Manual release (recommended)
   - Automatic release after approval

## Over-the-Air (OTA) Updates

Expo allows pushing updates without rebuilding:

1. **Update JavaScript/React code:**
   ```bash
   cd mobile
   pnpm start
   # Make changes to code
   ```

2. **Publish update:**
   ```bash
   eas update --branch production
   ```

3. **Users receive update:**
   - Update downloads on next app launch
   - No App Store/Play Store approval needed
   - Only works for JavaScript changes (not native code)

**Limitations:**
- Cannot update native code (requires rebuild)
- Cannot change app permissions (requires rebuild)
- Cannot update Expo SDK version (requires rebuild)

## Environment Configuration

### Development

```env
API_BASE_URL=http://192.168.1.100:8000/api/v1
WS_BASE_URL=ws://192.168.1.100:8000/api/v1/ws
```

### Pilot Testing

Update these in `eas.json` before building:

```json
"pilot": {
  "env": {
    "API_BASE_URL": "http://192.168.1.50:8000/api/v1",
    "WS_BASE_URL": "ws://192.168.1.50:8000/api/v1/ws"
  }
}
```

### Production

```json
"production": {
  "env": {
    "API_BASE_URL": "https://api.yourdomain.com/api/v1",
    "WS_BASE_URL": "wss://api.yourdomain.com/api/v1/ws"
  }
}
```

## Network Configuration

### Same WiFi Network (Pilot)

1. **Find backend IP:**
   ```bash
   # Windows
   ipconfig

   # Mac/Linux
   ifconfig
   # or
   ip addr show
   ```

2. **Update eas.json with backend IP**

3. **Ensure backend allows CORS:**
   ```env
   # backend/.env.production
   CORS_ORIGINS=["*"]  # For pilot testing only
   ```

4. **Test connectivity:**
   ```bash
   # From mobile device browser
   http://192.168.1.100:8000/api/v1/health
   ```

### HTTPS/Production

1. **Setup SSL on backend** (see backend deployment guide)

2. **Update mobile app URLs:**
   ```env
   API_BASE_URL=https://api.yourdomain.com/api/v1
   WS_BASE_URL=wss://api.yourdomain.com/api/v1/ws
   ```

3. **Update CORS:**
   ```env
   CORS_ORIGINS=["https://yourdomain.com"]
   ```

## Build Variants

### Android Build Types

| Build Type | Use Case | Distribution |
|------------|----------|--------------|
| APK | Pilot testing, direct install | Direct download |
| AAB | Play Store production | Google Play Store only |

### Build Commands

```bash
# APK (pilot testing)
eas build -p android --profile pilot

# AAB (production)
eas build -p android --profile production

# iOS (TestFlight/App Store)
eas build -p ios --profile production
```

## Testing Checklist

Before distributing to pilot testers:

- [ ] Backend is accessible on network
- [ ] Mobile app connects to backend API
- [ ] WebSocket connection works
- [ ] Login works (student and faculty)
- [ ] Face registration works
- [ ] Schedule display works
- [ ] Attendance records display
- [ ] Notifications receive
- [ ] Settings work
- [ ] Logout works
- [ ] App doesn't crash on common actions

## Troubleshooting

### Build Fails

```bash
# View build logs
eas build:list
eas build:view --id <build-id>

# Common issues:
# - Missing credentials (run: eas credentials)
# - Invalid app.json configuration
# - Native dependency conflicts
```

### Can't Connect to Backend

1. **Check IP address:**
   - Ensure correct backend IP in eas.json
   - Verify backend is running: `curl http://<ip>:8000/api/v1/health`

2. **Check network:**
   - Both devices on same WiFi
   - No VPN interfering
   - Firewall allows port 8000

3. **Check CORS:**
   - Backend allows mobile app origin
   - Check backend logs for CORS errors

### Android Installation Failed

1. **"App not installed" error:**
   - Enable "Install from unknown sources"
   - Check storage space
   - Uninstall old version first

2. **"Parse error":**
   - APK corrupted during download
   - Re-download APK
   - Transfer via USB instead

### iOS TestFlight Issues

1. **Build not appearing:**
   - Wait 10-15 minutes for processing
   - Check App Store Connect for errors

2. **Testers can't install:**
   - Check TestFlight invitation sent
   - Verify tester accepted invitation
   - Check device compatibility

## Monitoring

### Expo Dashboard

- Build history: https://expo.dev/builds
- Update deployments: https://expo.dev/updates
- Error tracking: https://expo.dev/crashes

### Analytics (Optional)

Consider adding:
- Sentry for error tracking
- Mixpanel for usage analytics
- Firebase Analytics for engagement

## Release Checklist

- [ ] Update version in app.json
- [ ] Update version in eas.json
- [ ] Test all features on development build
- [ ] Update environment variables for production
- [ ] Build and test APK/IPA
- [ ] Prepare store assets (screenshots, descriptions)
- [ ] Submit to App Store/Play Store
- [ ] Monitor for crashes after release
- [ ] Prepare rollback plan

## Rollback Plan

### OTA Update Rollback

```bash
# Publish previous version
eas update --branch production --message "Rollback to v1.0.0"
```

### App Store/Play Store Rollback

- **Android:** Create new release with previous version
- **iOS:** Request App Store to restore previous version (contact Apple)

## Next Steps

After successful deployment:

1. Monitor crash reports
2. Gather feedback from pilot testers
3. Fix critical bugs
4. Plan feature updates
5. Submit to production stores (if pilot successful)
