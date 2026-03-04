# IAMS System Setup Guide

Complete step-by-step instructions for setting up the Intelligent Attendance Monitoring System (IAMS) on a local network.

> **The entire system runs locally — no internet connection is required after the initial setup.**

---

## Steps

Follow each step in order. Each folder contains a detailed guide.

| Step | Guide | Description |
|------|-------|-------------|
| 01 | [Prerequisites](01-prerequisites/README.md) | Software you need to install first |
| 02 | [Clone the Repository](02-clone-repository/README.md) | Download the IAMS source code |
| 03 | [Set Up the Database](03-setup-database/README.md) | Start PostgreSQL via Docker |
| 04 | [Set Up the Backend](04-setup-backend/README.md) | Python virtual environment and dependencies |
| 05 | [Run Migrations](05-run-migrations/README.md) | Create all database tables |
| 06 | [Seed the Database](06-seed-database/README.md) | Populate initial data (faculty, rooms, schedules) |
| 07 | [Start the Backend Server](07-start-backend/README.md) | Launch the API server |
| 08 | [Set Up the Mobile App](08-setup-mobile-app/README.md) | Install mobile app dependencies |
| 09 | [Build the Android APK](09-build-android-apk/README.md) | Create the APK for student phones |
| 10 | [Connect on Local Network](10-connect-local-network/README.md) | Network architecture and camera setup |
| 11 | [Test Login Credentials](11-test-credentials/README.md) | Default accounts for testing |
| 12 | [Verify the System](12-verify-system/README.md) | Checklist to confirm everything works |
| 13 | [Daily Operation](13-daily-operation/README.md) | How to start/use the system each day |
| 14 | [Shutting Down](14-shutting-down/README.md) | How to properly stop everything |
| 15 | [Troubleshooting](15-troubleshooting/README.md) | Common problems and fixes |

---

## Quick Reference

See [quick-reference.md](quick-reference.md) for a one-page cheat sheet of all commands.

---

## System Overview

```
[Wi-Fi Router] (local network only — no internet needed)
     |
     |--- Laptop (Backend Server)
     |         |--- Docker PostgreSQL (port 5433)
     |         |--- FastAPI Backend (port 8000)
     |         |--- FFmpeg HLS Stream (live camera feed)
     |
     |--- CCTV Camera (Reolink P340)
     |
     |--- Student Phones (Android, connected to same Wi-Fi)
     |--- Faculty Phone (Android, connected to same Wi-Fi)
```
