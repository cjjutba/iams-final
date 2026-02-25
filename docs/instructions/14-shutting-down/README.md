# Step 14: Shutting Down the System

How to properly stop all components when you're done.

---

## Step 1: Stop the Backend Server

In the terminal where the backend is running, press:

```
Ctrl + C
```

You'll see:
```
INFO:     Shutting down
INFO:     Finished server process
```

---

## Step 2: Stop the Database

```bash
cd iams
docker compose down
```

You'll see:
```
[+] Running 1/1
 ✔ Container iams-postgres  Stopped
```

---

## Step 3: (Optional) Close Docker Desktop

You can close Docker Desktop if you're done for the day. The database data is saved and will be there when you start it again.

---

## Important Notes

### Your data is safe

All data is stored in a Docker volume called `iams_pgdata`. When you run `docker compose down`, the container stops but the data is preserved. Next time you run `docker compose up -d`, all your data (users, attendance records, etc.) will still be there.

### If you want to delete ALL data and start fresh

**WARNING: This permanently deletes all database data.**

```bash
docker compose down -v
```

The `-v` flag removes the Docker volume. After this, you'll need to run migrations and seeds again (Steps 5-6).

---

## Shutdown Order Summary

| Order | Action | Command |
|-------|--------|---------|
| 1 | Stop backend | `Ctrl+C` in the backend terminal |
| 2 | Stop database | `docker compose down` |
| 3 | Close Docker Desktop | (optional) Close the app |

---

**Next step:** [15 - Troubleshooting](../15-troubleshooting/README.md)
