# Step-by-Step Development Guide

## Phase Overview

| Phase | Duration | Focus |
|-------|----------|-------|
| 1 | Week 1 | Setup environment |
| 2 | Week 2 | Face detection on RPi |
| 3 | Week 3 | Backend API foundation |
| 4 | Week 4 | Face recognition |
| 5 | Week 5 | Tracking and presence |
| 6 | Week 6-7 | Mobile app core |
| 7 | Week 8 | Mobile app features |
| 8 | Week 9-10 | Integration and testing |
| 9 | Week 10 | Hardware enclosure |
| 10 | Week 11-12 | Documentation and polish |

---

## Phase 1: Environment Setup

### Laptop Setup

| Step | Task | Verification |
|------|------|--------------|
| 1.1 | Install Python 3.11 | `python --version` shows 3.11 |
| 1.2 | Install CUDA 11.8 | `nvcc --version` works |
| 1.3 | Create Supabase project | Supabase project exists; note URL and anon key |
| 1.4 | (Optional) Install PostgreSQL 16 locally | `psql --version` works if not using Supabase only |
| 1.5 | Install VS Code | Editor opens |
| 1.6 | Install Git | `git --version` works |

### Raspberry Pi Setup

| Step | Task | Verification |
|------|------|--------------|
| 1.7 | Flash Raspberry Pi OS Lite | Boots to terminal |
| 1.8 | Enable SSH | Can SSH from laptop |
| 1.9 | Connect to WiFi | Has IP address |
| 1.10 | Install Python 3.11 | `python3 --version` shows 3.11 |
| 1.11 | Connect camera | `libcamera-hello` shows preview |

### Mobile Setup (React Native)

| Step | Task | Verification |
|------|------|--------------|
| 1.12 | Install Node.js 20+ | `node --version` works |
| 1.13 | Install React Native CLI / Expo | `npx react-native --version` or Expo CLI |
| 1.14 | Setup Android Studio / Xcode | Emulator or device runs |
| 1.15 | Create React Native project | App runs on emulator |

---

## Phase 2: Face Detection on RPi

| Step | Task | Verification |
|------|------|--------------|
| 2.1 | Create edge project folder | Folder structure ready |
| 2.2 | Install dependencies | All packages installed |
| 2.3 | Write camera capture module | Frames captured at 15 FPS |
| 2.4 | Integrate MediaPipe detection | Boxes drawn on faces |
| 2.5 | Add crop and compress logic | 112x112 JPEG output |
| 2.6 | Write HTTP sender module | Can POST to test endpoint |
| 2.7 | Implement queue policy (see implementation.md) | Queues when server down, retries |
| 2.8 | Test full edge pipeline | Detects and crops faces |

---

## Phase 3: Backend API Foundation

| Step | Task | Verification |
|------|------|--------------|
| 3.1 | Create backend project folder | Folder structure ready |
| 3.2 | Install dependencies | All packages installed |
| 3.3 | Setup FastAPI app | Server starts on port 8000 |
| 3.4 | Connect backend to Supabase (Postgres + Auth) | Connection works |
| 3.5 | Create User / profile model in Supabase | Tables created |
| 3.6 | Create auth schemas | Pydantic models work |
| 3.7 | Build student register flow (verify ID → account → face) | Can create student |
| 3.8 | Build login (Supabase Auth or custom JWT) | Returns JWT token |
| 3.9 | Add JWT verification middleware | Protected routes work |
| 3.10 | (Optional) Alembic or Supabase migrations | Migrations run |

---

## Phase 4: Face Recognition

| Step | Task | Verification |
|------|------|--------------|
| 4.1 | Install PyTorch + CUDA | `torch.cuda.is_available()` is True |
| 4.2 | Load FaceNet model | Model loads on GPU |
| 4.3 | Write embedding generator | Returns 512-dim vector |
| 4.4 | Setup FAISS index | Index created |
| 4.5 | Implement FAISS lifecycle (add/remove/rebuild) | See implementation.md |
| 4.6 | Build face register endpoint | Saves embedding to FAISS |
| 4.7 | Build face recognize endpoint | Returns matched user |
| 4.8 | Build face/process endpoint (Edge API contract) | See api-reference.md |
| 4.9 | Test RPi to laptop flow | Face sent and recognized |

---

## Phase 5: Tracking and Presence

| Step | Task | Verification |
|------|------|--------------|
| 5.1 | Create Schedule model | Table created |
| 5.2 | Create Attendance model | Table created |
| 5.3 | Create PresenceLog model | Table created |
| 5.4 | Build schedule endpoints | CRUD works |
| 5.5 | Implement schedule/session semantics | See implementation.md |
| 5.6 | Integrate DeepSORT (server-side) | Tracks faces across frames |
| 5.7 | Write presence tracking service | Logs each scan |
| 5.8 | Write early leave detection | Flags after 3 misses |
| 5.9 | Create EarlyLeave model | Table created |
| 5.10 | Add WebSocket endpoint | Clients can connect |
| 5.11 | Push presence updates | Mobile receives updates |

---

## Phase 6: Mobile App Core (React Native)

| Step | Task | Verification |
|------|------|--------------|
| 6.1 | Setup React Native project structure | Folders created |
| 6.2 | Configure Zustand or React Context | State management works |
| 6.3 | Setup axios + Supabase client | API and Auth work |
| 6.4 | Build onboarding + welcome screens | User can select Student/Faculty |
| 6.5 | Build student login screen | Student ID + password |
| 6.6 | Build faculty login screen | Email + password (no register) |
| 6.7 | Build student register Step 1 (verify ID) | Validates against university data |
| 6.8 | Build student register Step 2 (account) | Email, phone, password |
| 6.9 | Store auth token (Supabase) | Token persists |
| 6.10 | Build student home screen | Shows today's status |
| 6.11 | Build faculty home screen | Shows class overview |
| 6.12 | Setup WebSocket service | Receives updates |

---

## Phase 7: Mobile App Features (React Native)

| Step | Task | Verification |
|------|------|--------------|
| 7.1 | Build student register Step 3 (face) + review | Captures 3–5 angles, review screen |
| 7.2 | Apply face registration rules (3–5 images, validation) | See implementation.md |
| 7.3 | Upload face to backend | Registration succeeds; FAISS updated |
| 7.4 | (Optional) Add ID scan/upload for Step 1 | Fallback to manual if scan fails |
| 7.5 | Build attendance history | Shows past records |
| 7.6 | Build live attendance view (faculty) | Real-time student list |
| 7.7 | Add early leave alerts | Notification appears |
| 7.8 | Build schedule view | Shows class times |
| 7.9 | Add pull-to-refresh | Data refreshes |
| 7.10 | Polish UI/UX | Smooth animations |
| 7.11 | Pre-seed faculty (script + CSV from client) | Faculty can log in only |

---

## Phase 8: Integration Testing

| Step | Task | Verification |
|------|------|--------------|
| 8.1 | Register 5-10 test users | All registered |
| 8.2 | Register faces for all users | FAISS has embeddings |
| 8.3 | Run full attendance flow | Attendance marked |
| 8.4 | Test 30-minute session | Presence logs complete |
| 8.5 | Test early leave detection | Alert triggers |
| 8.6 | Test mobile real-time updates | Updates appear |
| 8.7 | Test poor lighting | System handles it |
| 8.8 | Test partial occlusion | System handles it |
| 8.9 | Test RPi queue when server down | Queues and retries |
| 8.10 | Run validation tests (see testing.md) | Metrics within targets |
| 8.11 | Fix all bugs | System stable |

---

## Phase 9: Hardware Enclosure

| Step | Task | Verification |
|------|------|--------------|
| 9.1 | Design enclosure | Fits RPi + camera |
| 9.2 | Build or buy enclosure | Physical box ready |
| 9.3 | Mount camera | Good angle achieved |
| 9.4 | Manage cables | Clean setup |
| 9.5 | Test in classroom | Works in real environment |
| 9.6 | Adjust camera position | Covers all students |

---

## Phase 10: Documentation and Polish

| Step | Task | Verification |
|------|------|--------------|
| 10.1 | Write user manual | Clear instructions |
| 10.2 | Document all APIs | Swagger complete |
| 10.3 | Create demo script | Step-by-step demo plan |
| 10.4 | Record backup video | Video ready |
| 10.5 | Dry run with users | Feedback collected |
| 10.6 | Final bug fixes | All issues resolved |
| 10.7 | Prepare presentation | Slides ready |
| 10.8 | Defense prep | Ready to present |

---

## Daily Checklist

```
□ Pull latest code
□ Check RPi is connected
□ Check server is running
□ Check database is accessible
□ Run tests
□ Commit changes
□ Update documentation
```

---

## Milestone Checkpoints

| Week | Milestone | Demo |
|------|-----------|------|
| 2 | RPi detects faces | Show detection on monitor |
| 4 | Server recognizes faces | Register and recognize demo |
| 5 | Presence tracking works | 5-minute tracking demo |
| 7 | Mobile app functional | Full app walkthrough |
| 10 | System complete | End-to-end demo |
| 12 | Defense ready | Final presentation |
