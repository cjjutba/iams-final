# Step 13: Daily Operation Guide

Follow these steps every time you want to use the system for attendance monitoring.

---

## Starting Up (Do This Every Time)

Follow this exact order:

### 1. Start Docker Desktop

- Open **Docker Desktop** from the Start Menu
- Wait until it shows **"Docker is running"**

### 2. Start the Database

Open a terminal and run:
```bash
cd iams
docker compose up -d
```

Wait a few seconds, then verify:
```bash
docker ps
```
You should see `iams-postgres` with status "Up".

### 3. Start the Backend Server

Open a terminal (or use the same one) and run:
```bash
cd backend
venv\Scripts\activate
python run.py
```

Wait until you see:
```
INFO:     Application startup complete.
```

### 4. Connect Devices

- Make sure the **laptop**, **camera**, and all **phones** are on the **same Wi-Fi**
- Students and faculty open the **IAMS app** on their phones

---

## During a Class Session

### For Faculty:
1. Open the IAMS app
2. Log in with faculty credentials
3. Go to the **Dashboard**
4. Select the current class/schedule
5. Tap **"Start Session"** to begin attendance tracking
6. The camera will automatically detect and recognize students
7. Monitor attendance in real-time from the dashboard
8. When class ends, tap **"End Session"**

### For Students:
1. Open the IAMS app (make sure they're registered first)
2. Their attendance is tracked automatically by the camera
3. They can view their attendance history in the app

### How Attendance Works:
- The camera scans for faces every **60 seconds**
- Students are marked **present** when their face is recognized
- If a student is not detected for **3 consecutive scans** (3 minutes), they are flagged as **early leave**
- Attendance score = (scans present / total scans) x 100%

---

## First-Time Student Setup

Before a student can be tracked, they must register:

1. Open the IAMS app
2. Tap **"Register as Student"**
3. Enter their **Student ID**
4. Fill in the registration form
5. Capture **3-5 face photos** (different angles)
6. Submit

This only needs to be done once per student.

---

## Tips for Best Results

- **Lighting:** Make sure the classroom has good lighting for the camera
- **Camera placement:** Position the camera to capture as many student faces as possible
- **Face registration:** Have students register in good lighting, facing the camera straight
- **Network:** Make sure all devices stay connected to the same Wi-Fi throughout the session

---

**Next step:** [14 - Shutting Down](../14-shutting-down/README.md)
