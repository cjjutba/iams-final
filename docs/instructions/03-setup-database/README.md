# Step 3: Set Up the Database (PostgreSQL via Docker)

The IAMS system uses PostgreSQL as its database. We run it inside a Docker container so it's easy to set up and portable.

---

## Step 3.1: Make sure Docker Desktop is running

1. Open **Docker Desktop** from your Start Menu (or Applications on Mac)
2. Wait until the bottom left says **"Docker is running"**

> If Docker is not running, none of the following commands will work.

---

## Step 3.2: Start the PostgreSQL container

1. Open a terminal
2. Navigate to the project root folder:
   ```bash
   cd iams
   ```
3. Start the database:
   ```bash
   docker compose up -d
   ```

You should see output like:
```
[+] Running 2/2
 ✔ Volume "iams_iams_pgdata"  Created
 ✔ Container iams-postgres     Started
```

**What this does:**
- Downloads the PostgreSQL 16 image (first time only, ~80MB)
- Creates a container named `iams-postgres`
- Starts PostgreSQL on **port 5433**
- Stores all data in a persistent Docker volume (data survives restarts)

---

## Step 3.3: Verify the database is running

```bash
docker ps
```

You should see something like:

```
CONTAINER ID   IMAGE                COMMAND                  STATUS         PORTS                    NAMES
abc123...      postgres:16-alpine   "docker-entrypoint..."   Up 5 seconds   0.0.0.0:5433->5432/tcp   iams-postgres
```

The key things to check:
- **STATUS** says "Up"
- **PORTS** shows `0.0.0.0:5433->5432/tcp`

---

## Step 3.4: Test the database connection

```bash
docker exec -it iams-postgres psql -U postgres -d iams -c "SELECT 'Database is working!' AS status;"
```

Expected output:
```
        status
---------------------
 Database is working!
(1 row)
```

---

## (Optional) View the database with pgAdmin

If you want a visual tool to browse tables and data:

1. Download pgAdmin from https://www.pgadmin.org/download/
2. Open pgAdmin
3. Right-click "Servers" > "Register" > "Server"
4. Fill in the connection details:

| Field | Value |
|-------|-------|
| **Name** | IAMS Local |
| **Host** | localhost |
| **Port** | 5433 |
| **Username** | postgres |
| **Password** | postgres |
| **Database** | iams |

5. Click "Save"

To view table data later: Navigate to **Servers > IAMS Local > Databases > iams > Schemas > public > Tables** > right-click a table > **View/Edit Data > All Rows**

---

## Database Connection Details

For reference, the database connection string is:

```
postgresql://postgres:postgres@localhost:5433/iams
```

| Parameter | Value |
|-----------|-------|
| Host | localhost |
| Port | 5433 |
| Database | iams |
| Username | postgres |
| Password | postgres |

---

**Next step:** [04 - Set Up the Backend](../04-setup-backend/README.md)
