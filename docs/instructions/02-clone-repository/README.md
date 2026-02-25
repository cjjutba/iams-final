# Step 2: Clone the Repository

Download the IAMS source code to your computer.

---

## Instructions

1. Open a terminal (Command Prompt, PowerShell, or Git Bash)

2. Navigate to the folder where you want to store the project:
   ```bash
   cd C:\Projects
   ```
   (You can use any folder you prefer)

3. Clone the repository:
   ```bash
   git clone <repository-url> iams
   ```
   Replace `<repository-url>` with the actual Git repository URL provided to you.

4. Enter the project folder:
   ```bash
   cd iams
   ```

---

## Verify

You should see the following folder structure:

```
iams/
├── backend/          <-- FastAPI server
├── mobile/           <-- React Native mobile app
├── edge/             <-- Raspberry Pi edge device (optional)
├── docs/             <-- Documentation
├── docker-compose.yml
└── CLAUDE.md
```

Run this command to confirm:
```bash
ls
```

---

## What You Just Downloaded

| Folder | Description |
|--------|-------------|
| `backend/` | The Python FastAPI server that handles face recognition, attendance, and all business logic |
| `mobile/` | The React Native Android app for students and faculty |
| `edge/` | Code for the Raspberry Pi edge device (optional — for camera face detection) |
| `docs/` | All project documentation |
| `docker-compose.yml` | Configuration to start the PostgreSQL database |

---

**Next step:** [03 - Set Up the Database](../03-setup-database/README.md)
