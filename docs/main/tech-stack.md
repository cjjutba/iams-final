# Tech Stack

## Overview

| Layer | Technology |
|-------|------------|
| Edge Device | Raspberry Pi 4 + Python |
| Backend | FastAPI (Python) |
| Database & Auth | Supabase (PostgreSQL + Auth) |
| Vector Search | FAISS |
| Mobile | React Native |
| ML/AI | PyTorch + FaceNet |

---

## Edge (Raspberry Pi)

| Purpose | Technology |
|---------|------------|
| Operating System | Raspberry Pi OS Lite 64-bit |
| Language | Python 3.11 |
| Camera | picamera2 (Pi Cam) or OpenCV (USB) |
| Face Detection | MediaPipe Face Detection (TFLite runtime on Pi) |
| HTTP Client | httpx |
| Config | python-dotenv |

---

## Backend (Laptop or Cloud)

| Purpose | Technology |
|---------|------------|
| Language | Python 3.11 |
| Web Framework | FastAPI |
| Server | Uvicorn |
| Database | Supabase (PostgreSQL); optional SQLAlchemy for local/custom |
| Auth | Supabase Auth (JWT) or python-jose (JWT) if custom |
| Password Hashing | passlib + bcrypt |
| Validation | Pydantic |
| WebSocket | FastAPI WebSocket (built-in) |

---

## Database & Auth (Supabase)

| Purpose | Technology |
|---------|------------|
| Hosted Database | Supabase (PostgreSQL 15) |
| Auth | Supabase Auth (sign up, login, JWT, refresh) |
| API | Supabase REST/Realtime (optional for simple CRUD) |
| Vector Storage | FAISS (file-based, on backend server) |
| Connection | Backend connects to Supabase Postgres; mobile uses Supabase client for auth |

---

## Machine Learning

| Purpose | Technology |
|---------|------------|
| Deep Learning | PyTorch + CUDA 11.8 |
| Face Recognition | facenet-pytorch |
| Object Tracking | deep-sort-realtime |
| Vector Search | FAISS (faiss-cpu) |
| Image Processing | OpenCV |

---

## Mobile App (React Native)

| Purpose | Technology |
|---------|------------|
| Framework | React Native |
| Language | TypeScript (or JavaScript) |
| State Management | Zustand or React Context |
| HTTP Client | axios or fetch |
| WebSocket | native WebSocket or socket.io-client |
| Local Storage | AsyncStorage |
| Camera | react-native-vision-camera or expo-camera |
| Navigation | React Navigation |
| Supabase Client | @supabase/supabase-js (auth, optional data) |

---

## Development Tools

| Purpose | Technology |
|---------|------------|
| Code Formatting | black (Python); Prettier (JS/TS) |
| Linting | ruff (Python); ESLint (JS/TS) |
| Testing | pytest (backend); Jest (mobile) |
| API Documentation | Swagger (auto from FastAPI) |
| Version Control | Git |
| Editor | VS Code |

---

## Why These Choices

| Choice | Reason |
|--------|--------|
| FastAPI | Fast, modern, auto-generates API docs |
| Supabase | Hosted Postgres + Auth; use in dev and pilot; no self-hosted DB for pilot |
| FAISS | No server needed, fast similarity search |
| MediaPipe | Easy setup, works well on RPi (TFLite for edge) |
| FaceNet | Proven accuracy, PyTorch integration |
| React Native | Single codebase for iOS and Android; familiar JS/TS ecosystem |
| Zustand / Context | Simple state management for auth and attendance state |

---

## Version Summary

```
Python          3.11
FastAPI         0.109+
PostgreSQL      15 (Supabase)
PyTorch         2.1+
CUDA            11.8
React Native    0.73+
TypeScript      5.x
Node.js         20+
```
