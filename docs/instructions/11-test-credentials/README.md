# Step 11: Test Login Credentials

These are the default accounts created by the seed scripts.

---

## Faculty Account

| Field | Value |
|-------|-------|
| **Email** | faculty@gmail.com |
| **Password** | password123 |
| **Role** | Faculty |

Use this to log in as faculty from the mobile app. Faculty can:
- View the attendance dashboard
- Start/stop attendance sessions
- View live camera feed
- Monitor student presence
- View attendance reports

---

## Student Registration

Students **do not have pre-made accounts**. They must register through the mobile app.

### Registration Flow

1. Open the IAMS app on the student's phone
2. Tap **"Register as Student"**
3. Enter the **Student ID** (e.g., `21-A-012345`)
4. The app verifies the ID against the school registry and auto-fills:
   - Full name
   - Course
   - Year level
   - Section
   - Email
5. The student creates a **password**
6. The student captures **3-5 face photos** from different angles
7. Review and submit

### Test Student ID

| Field | Value |
|-------|-------|
| **Student ID** | 21-A-012345 |
| **Name** | Christian Jerald Jutba |
| **Course** | BSCPE |
| **Year Level** | 4 |
| **Section** | A |
| **Email** | cjjutbaofficial@gmail.com |

> After registration, the student can log in with their Student ID/email and the password they created.

---

## Adding More Student Records

To register more students, you need to add their records to the `student_records` table in the database. This can be done:

### Option 1: Via pgAdmin
1. Open pgAdmin and connect to the database
2. Navigate to **Tables > student_records**
3. Right-click > **View/Edit Data > All Rows**
4. Add new rows with student information

### Option 2: Via SQL command
```bash
docker exec -it iams-postgres psql -U postgres -d iams -c "
INSERT INTO student_records (student_id, first_name, last_name, email, course, year_level, section, is_active)
VALUES ('22-B-01234', 'Juan', 'Dela Cruz', 'juan@gmail.com', 'BSCPE', '3', 'A', true);
"
```

### Option 3: Via the seed script
Edit `backend/scripts/seed_reference_data.py` to add more student records, then re-run:
```bash
cd backend
python -m scripts.seed_reference_data
```

---

**Next step:** [12 - Verify the System](../12-verify-system/README.md)
