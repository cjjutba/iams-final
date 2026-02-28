# Step 7: Start the Backend Server

The backend server is the core of the IAMS system. It handles:
- User authentication (login/register)
- Face recognition
- Attendance tracking
- Live camera streaming
- WebSocket real-time updates
- REST API for the mobile app

---

## Prerequisites

- Database is running (Step 3)
- Migrations are done (Step 5)
- Database is seeded (Step 6)
- Virtual environment is activated (`(venv)` in your prompt)
- You are in the `backend/` folder

---

## Start the server

```bash
python run.py
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to stop)
INFO:     Started reloader process [12345]
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

The server is now running on **port 8000** and accessible from any device on the local network.

---

## Verify the server is working

### Check health endpoint

Open a browser and go to:

```
http://localhost:8000/api/v1/health
```

You should see:
```json
{"status": "healthy"}
```

### View API documentation

Open a browser and go to:

```
http://localhost:8000/docs
```

This shows the interactive Swagger UI with all available API endpoints.

### Test faculty login

You can test login directly from the Swagger UI:
1. Go to http://localhost:8000/docs
2. Find the `POST /api/v1/auth/login` endpoint
3. Click "Try it out"
4. Enter the request body:
   ```json
   {
     "email": "faculty@gmail.com",
     "password": "password123"
   }
   ```
5. Click "Execute"
6. You should get a response with `access_token` and `refresh_token`

---

## Important Notes

- **Keep this terminal open** — the server stops if you close it
- Press `Ctrl+C` to stop the server
- The server auto-reloads when you change code files (development mode)
- The server listens on `0.0.0.0:8000` which means it's accessible from other devices on the network

---

**Next step:** [08 - Set Up the Mobile App](../08-setup-mobile-app/README.md)
