# Client-Side Detection Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the broken server-side video pipeline with on-device face detection (ML Kit) + simplified recognition-only backend. Rewrite mobile app in Kotlin/Jetpack Compose.

**Architecture:** Raw video streams from camera → mediamtx → WebRTC → Kotlin app (ExoPlayer). ML Kit detects faces on-device at 30fps. Backend grabs 1 frame every 10-15s for ArcFace recognition, writes attendance to DB, broadcasts names via WebSocket. Three independent systems: video delivery, face detection, attendance tracking.

**Tech Stack:** Kotlin + Jetpack Compose + Material 3, ExoPlayer (Media3), Google ML Kit Face Detection, CameraX, Retrofit + OkHttp, Hilt, Navigation Compose, DataStore. Backend: FastAPI + InsightFace (SCRFD + ArcFace) + FAISS + PostgreSQL + Redis.

**Design Doc:** `docs/plans/2026-03-19-client-side-detection-redesign-design.md`

---

## Track 1: Backend Simplification (Days 1-3)

### Task 1: Delete Unnecessary Backend Files

Remove all video pipeline and over-engineered services. The backend becomes a recognition + CRUD API.

**Files to DELETE:**

```
# Video pipeline (entire directory)
backend/app/pipeline/

# Unnecessary services
backend/app/services/ml/yunet_detector.py
backend/app/services/stream_bus.py
backend/app/services/recognition_service.py
backend/app/services/mediamtx_service.py
backend/app/services/webrtc_service.py
backend/app/services/session_scheduler.py
backend/app/services/analytics_service.py
backend/app/services/anomaly_service.py
backend/app/services/prediction_service.py
backend/app/services/engagement_service.py
backend/app/services/reenrollment_service.py
backend/app/services/notification_service.py
backend/app/services/digest_service.py
backend/app/services/email_service.py
backend/app/services/email_templates.py
backend/app/services/camera_config.py

# Unnecessary routers
backend/app/routers/pipeline.py
backend/app/routers/live_stream.py
backend/app/routers/edge_ws.py
backend/app/routers/webrtc.py
backend/app/routers/analytics.py
backend/app/routers/audit.py
backend/app/routers/edge.py
backend/app/routers/settings_router.py

# Unnecessary models (analytics)
backend/app/models/attendance_anomaly.py
backend/app/models/attendance_prediction.py
backend/app/models/engagement_score.py
backend/app/models/audit_log.py

# Unnecessary schemas
backend/app/schemas/analytics.py
backend/app/schemas/webrtc.py
backend/app/schemas/audit_log.py

# Workers
backend/app/workers/
```

**Step 1:** Delete all files listed above.

```bash
# Pipeline directory
rm -rf backend/app/pipeline/

# Services
rm -f backend/app/services/ml/yunet_detector.py
rm -f backend/app/services/stream_bus.py
rm -f backend/app/services/recognition_service.py
rm -f backend/app/services/mediamtx_service.py
rm -f backend/app/services/webrtc_service.py
rm -f backend/app/services/session_scheduler.py
rm -f backend/app/services/analytics_service.py
rm -f backend/app/services/anomaly_service.py
rm -f backend/app/services/prediction_service.py
rm -f backend/app/services/engagement_service.py
rm -f backend/app/services/reenrollment_service.py
rm -f backend/app/services/notification_service.py
rm -f backend/app/services/digest_service.py
rm -f backend/app/services/email_service.py
rm -f backend/app/services/email_templates.py
rm -f backend/app/services/camera_config.py

# Routers
rm -f backend/app/routers/pipeline.py
rm -f backend/app/routers/live_stream.py
rm -f backend/app/routers/edge_ws.py
rm -f backend/app/routers/webrtc.py
rm -f backend/app/routers/analytics.py
rm -f backend/app/routers/audit.py
rm -f backend/app/routers/edge.py
rm -f backend/app/routers/settings_router.py

# Models
rm -f backend/app/models/attendance_anomaly.py
rm -f backend/app/models/attendance_prediction.py
rm -f backend/app/models/engagement_score.py
rm -f backend/app/models/audit_log.py

# Schemas
rm -f backend/app/schemas/analytics.py
rm -f backend/app/schemas/webrtc.py
rm -f backend/app/schemas/audit_log.py

# Workers
rm -rf backend/app/workers/
```

**Step 2:** Remove imports of deleted modules from `__init__.py` files and any other files that import them. Search for broken imports:

```bash
cd backend && python -c "import app.main" 2>&1 | head -20
```

Fix all `ImportError` and `ModuleNotFoundError` until the import succeeds.

**Step 3:** Remove `supervision` from `requirements.txt` (ByteTrack no longer needed).

**Step 4:** Commit.

```bash
git add -A
git commit -m "refactor: delete video pipeline, analytics, and unnecessary services"
```

---

### Task 2: Simplify main.py

Strip `main.py` down to essentials: DB, Redis, InsightFace, FAISS, FrameGrabber, AttendanceEngine, WebSocket.

**File:** Modify `backend/app/main.py`

**Step 1:** Rewrite the lifespan and router registration. The new `main.py` should:

- Keep: CORS middleware, exception handlers, DB check, Redis init, InsightFace load, FAISS load/reconcile
- Keep: APScheduler with `run_attendance_scan_cycle` (every SCAN_INTERVAL_SECONDS)
- Remove: pipeline_manager, mediamtx_service, broadcaster (Redis Streams), pipeline health check, digest jobs, session_scheduler auto-management
- Remove: router registrations for deleted routers (pipeline, analytics, audit, edge, edge_ws, live_stream, webrtc, settings)

**Keep these routers:**
```python
app.include_router(auth_router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(users_router, prefix=f"{API_PREFIX}/users", tags=["Users"])
app.include_router(face_router, prefix=f"{API_PREFIX}/face", tags=["Face"])
app.include_router(rooms_router, prefix=f"{API_PREFIX}/rooms", tags=["Rooms"])
app.include_router(schedules_router, prefix=f"{API_PREFIX}/schedules", tags=["Schedules"])
app.include_router(attendance_router, prefix=f"{API_PREFIX}/attendance", tags=["Attendance"])
app.include_router(presence_router, prefix=f"{API_PREFIX}/presence", tags=["Presence"])
app.include_router(notifications_router, prefix=f"{API_PREFIX}/notifications", tags=["Notifications"])
app.include_router(ws_router, prefix=f"{API_PREFIX}/ws", tags=["WebSocket"])
app.include_router(health_router, prefix=f"{API_PREFIX}/health", tags=["Health"])
```

**Step 2:** Update the scan cycle function. The current `run_attendance_scan_cycle` feeds results to `PresenceService`. Keep this flow but remove any references to pipeline or Redis Streams. The scan cycle should:

1. For each active session: get or create FrameGrabber
2. Call `attendance_engine.scan_frame()`
3. Feed results to `presence_service.run_scan_cycle(scan_results=...)`
4. Broadcast detections via WebSocket (direct, not via Redis Streams)

**Step 3:** Verify the server starts:

```bash
cd backend && python -c "from app.main import app; print('OK')"
```

**Step 4:** Commit.

```bash
git add backend/app/main.py
git commit -m "refactor: simplify main.py — remove pipeline, analytics, digest jobs"
```

---

### Task 3: Simplify WebSocket to Direct Broadcast

Replace the Redis Streams-based `BroadcastManager` with a simple in-memory connection manager that broadcasts directly.

**File:** Rewrite `backend/app/routers/websocket.py`

**Step 1:** Write the simplified WebSocket manager and router:

```python
"""Simple WebSocket manager — direct broadcast, no Redis Streams."""
import asyncio
import json
import logging
from collections import defaultdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """In-memory WebSocket connection manager."""

    def __init__(self):
        self._attendance_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._alert_clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def add_attendance_client(self, schedule_id: str, ws: WebSocket):
        await ws.accept()
        self._attendance_clients[schedule_id].add(ws)

    def remove_attendance_client(self, schedule_id: str, ws: WebSocket):
        self._attendance_clients[schedule_id].discard(ws)

    async def add_alert_client(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self._alert_clients[user_id].add(ws)

    def remove_alert_client(self, user_id: str, ws: WebSocket):
        self._alert_clients[user_id].discard(ws)

    async def broadcast_attendance(self, schedule_id: str, data: dict):
        """Broadcast attendance scan results to all connected faculty."""
        dead = []
        for ws in self._attendance_clients.get(schedule_id, set()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._attendance_clients[schedule_id].discard(ws)

    async def broadcast_alert(self, user_id: str, data: dict):
        """Send alert to a specific user."""
        dead = []
        for ws in self._alert_clients.get(user_id, set()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._alert_clients[user_id].discard(ws)

    async def broadcast_scan_result(self, schedule_id: str, detections: list[dict],
                                     present_count: int, total_enrolled: int,
                                     absent: list[str], early_leave: list[str]):
        """Broadcast a scan result from the attendance engine."""
        await self.broadcast_attendance(schedule_id, {
            "type": "scan_result",
            "schedule_id": schedule_id,
            "detections": detections,
            "present_count": present_count,
            "total_enrolled": total_enrolled,
            "absent": absent,
            "early_leave": early_leave,
        })


ws_manager = ConnectionManager()


@router.websocket("/attendance/{schedule_id}")
async def attendance_websocket(websocket: WebSocket, schedule_id: str):
    await ws_manager.add_attendance_client(schedule_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.remove_attendance_client(schedule_id, websocket)


@router.websocket("/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: str):
    await ws_manager.add_alert_client(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.remove_alert_client(user_id, websocket)
```

**Step 2:** Update `main.py` and `presence_service.py` to use `ws_manager.broadcast_scan_result()` instead of publishing to Redis Streams.

**Step 3:** Verify WebSocket connections work:

```bash
cd backend && python run.py &
# In another terminal:
pip install websockets
python -c "
import asyncio, websockets
async def test():
    async with websockets.connect('ws://localhost:8000/api/v1/ws/attendance/test') as ws:
        await ws.send('ping')
        print(await ws.recv())
asyncio.run(test())
"
```

Expected: `pong`

**Step 4:** Commit.

```bash
git add backend/app/routers/websocket.py
git commit -m "refactor: simplify WebSocket to direct broadcast, remove Redis Streams"
```

---

### Task 4: Update Docker Compose

Simplify both dev and prod docker-compose files.

**File:** Modify `docker-compose.yml` (dev) and `deploy/docker-compose.prod.yml`

**Step 1:** Dev compose should have only:

```yaml
services:
  api-gateway:
    build: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./backend/app:/app/app
      - faiss_data:/app/data/faiss
      - face_uploads:/app/uploads
    env_file: ./backend/.env
    depends_on: [redis, mediamtx]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru --save ""

  mediamtx:
    image: bluenviron/mediamtx:latest
    ports:
      - "8554:8554"      # RTSP ingest
      - "8889:8889"      # WHEP API
      - "8887:8887/udp"  # WebRTC UDP

volumes:
  faiss_data:
  face_uploads:
```

**Step 2:** Prod compose: same 3 services + nginx. Remove coturn, dozzle, certbot, admin.

**Step 3:** Verify dev stack starts:

```bash
docker compose up -d
docker compose logs api-gateway | tail -20
```

**Step 4:** Commit.

```bash
git add docker-compose.yml deploy/docker-compose.prod.yml
git commit -m "refactor: simplify docker-compose — 3 services only"
```

---

### Task 5: Verify Simplified Backend Works End-to-End

**Step 1:** Start the stack and verify health:

```bash
docker compose up -d
curl http://localhost:8000/api/v1/health
```

Expected: `{"status": "healthy", ...}`

**Step 2:** Verify auth works:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "test@test.com", "password": "password"}'
```

**Step 3:** Verify face registration endpoint responds (don't need to test with real images yet):

```bash
curl http://localhost:8000/api/v1/face/statistics
```

**Step 4:** Run existing tests that still apply:

```bash
cd backend && pytest tests/ -v --ignore=tests/test_pipeline 2>&1 | tail -30
```

Fix any failures caused by deleted imports.

**Step 5:** Commit any fixes.

```bash
git add -A
git commit -m "fix: resolve import errors after backend simplification"
```

---

## Track 2: Kotlin Project Foundation (Days 3-6)

### Task 6: Create Kotlin Android Project

Create a new Android project with Jetpack Compose inside the existing repo.

**Step 1:** Create the project structure. Use Android Studio or manually create:

```
android/
├── app/
│   ├── build.gradle.kts
│   ├── src/
│   │   └── main/
│   │       ├── AndroidManifest.xml
│   │       ├── java/com/iams/app/
│   │       │   ├── IAMSApplication.kt
│   │       │   ├── MainActivity.kt
│   │       │   ├── di/                    # Hilt modules
│   │       │   ├── data/
│   │       │   │   ├── api/               # Retrofit interfaces
│   │       │   │   ├── model/             # Data classes
│   │       │   │   └── repository/        # Repositories
│   │       │   ├── ui/
│   │       │   │   ├── navigation/        # Nav graphs
│   │       │   │   ├── theme/             # Material 3 theme
│   │       │   │   ├── components/        # Shared composables
│   │       │   │   ├── auth/              # Auth screens
│   │       │   │   ├── student/           # Student screens
│   │       │   │   └── faculty/           # Faculty screens
│   │       │   └── util/                  # Extensions, helpers
│   │       └── res/
│   │           ├── values/
│   │           │   ├── strings.xml
│   │           │   ├── colors.xml
│   │           │   └── themes.xml
│   │           └── drawable/
├── build.gradle.kts                       # Project-level
├── settings.gradle.kts
└── gradle.properties
```

**Step 2:** Write `app/build.gradle.kts` with all dependencies:

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt.android)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.iams.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.iams.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }
    buildFeatures {
        compose = true
    }
}

dependencies {
    // Compose BOM
    val composeBom = platform("androidx.compose:compose-bom:2025.01.00")
    implementation(composeBom)
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    // Navigation
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("androidx.hilt:hilt-navigation-compose:1.2.0")

    // Hilt DI
    implementation("com.google.dagger:hilt-android:2.53.1")
    ksp("com.google.dagger:hilt-compiler:2.53.1")

    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // ExoPlayer (Media3) for RTSP
    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-exoplayer-rtsp:1.5.1")
    implementation("androidx.media3:media3-ui:1.5.1")

    // ML Kit Face Detection
    implementation("com.google.mlkit:face-detection:16.1.7")

    // CameraX (face registration)
    implementation("androidx.camera:camera-core:1.4.1")
    implementation("androidx.camera:camera-camera2:1.4.1")
    implementation("androidx.camera:camera-lifecycle:1.4.1")
    implementation("androidx.camera:camera-view:1.4.1")

    // DataStore (token storage)
    implementation("androidx.datastore:datastore-preferences:1.1.2")

    // Image loading
    implementation("io.coil-kt:coil-compose:2.7.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
}
```

**Step 3:** Write `AndroidManifest.xml`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:name=".IAMSApplication"
        android:label="IAMS"
        android:theme="@style/Theme.IAMS">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

**Step 4:** Write `IAMSApplication.kt`:

```kotlin
package com.iams.app

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class IAMSApplication : Application()
```

**Step 5:** Write `MainActivity.kt`:

```kotlin
package com.iams.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.iams.app.ui.navigation.IAMSNavHost
import com.iams.app.ui.theme.IAMSTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            IAMSTheme {
                IAMSNavHost()
            }
        }
    }
}
```

**Step 6:** Build and verify it compiles:

```bash
cd android && ./gradlew assembleDebug
```

**Step 7:** Commit.

```bash
git add android/
git commit -m "feat: create Kotlin Android project with Compose + Hilt + Media3 + ML Kit"
```

---

### Task 7: Set Up Material 3 Theme

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/theme/Theme.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/theme/Color.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/theme/Type.kt`

**Step 1:** Define a clean monochrome theme matching the current design:

```kotlin
// Color.kt
package com.iams.app.ui.theme

import androidx.compose.ui.graphics.Color

val Black = Color(0xFF000000)
val White = Color(0xFFFFFFFF)
val Gray50 = Color(0xFFFAFAFA)
val Gray100 = Color(0xFFF5F5F5)
val Gray200 = Color(0xFFEEEEEE)
val Gray300 = Color(0xFFE0E0E0)
val Gray500 = Color(0xFF9E9E9E)
val Gray700 = Color(0xFF616161)
val Gray900 = Color(0xFF212121)
val Green500 = Color(0xFF4CAF50)
val Red500 = Color(0xFFF44336)
val Amber500 = Color(0xFFFFC107)
```

```kotlin
// Theme.kt
package com.iams.app.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable

private val LightColorScheme = lightColorScheme(
    primary = Gray900,
    onPrimary = White,
    secondary = Gray700,
    background = Gray50,
    surface = White,
    onSurface = Gray900,
    error = Red500,
)

@Composable
fun IAMSTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = IAMSTypography,
        content = content
    )
}
```

**Step 2:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/theme/
git commit -m "feat: add Material 3 monochrome theme"
```

---

### Task 8: Set Up Retrofit API Client + Auth Interceptor

**Files:**
- Create: `android/app/src/main/java/com/iams/app/data/api/ApiService.kt`
- Create: `android/app/src/main/java/com/iams/app/data/api/AuthInterceptor.kt`
- Create: `android/app/src/main/java/com/iams/app/data/api/TokenManager.kt`
- Create: `android/app/src/main/java/com/iams/app/di/NetworkModule.kt`

**Step 1:** Write `TokenManager.kt` (DataStore-based):

```kotlin
package com.iams.app.data.api

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore("auth")

@Singleton
class TokenManager @Inject constructor(@ApplicationContext private val context: Context) {
    private val ACCESS_TOKEN = stringPreferencesKey("access_token")
    private val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
    private val USER_ROLE = stringPreferencesKey("user_role")
    private val USER_ID = stringPreferencesKey("user_id")

    val accessToken get() = runBlocking {
        context.dataStore.data.map { it[ACCESS_TOKEN] }.first()
    }

    val refreshToken get() = runBlocking {
        context.dataStore.data.map { it[REFRESH_TOKEN] }.first()
    }

    val userRole get() = runBlocking {
        context.dataStore.data.map { it[USER_ROLE] }.first()
    }

    val userId get() = runBlocking {
        context.dataStore.data.map { it[USER_ID] }.first()
    }

    suspend fun saveTokens(access: String, refresh: String, role: String, userId: String) {
        context.dataStore.edit {
            it[ACCESS_TOKEN] = access
            it[REFRESH_TOKEN] = refresh
            it[USER_ROLE] = role
            it[USER_ID] = userId
        }
    }

    suspend fun clearTokens() {
        context.dataStore.edit { it.clear() }
    }
}
```

**Step 2:** Write `AuthInterceptor.kt`:

```kotlin
package com.iams.app.data.api

import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenManager: TokenManager
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val token = tokenManager.accessToken

        return if (token != null) {
            val authedRequest = request.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
            chain.proceed(authedRequest)
        } else {
            chain.proceed(request)
        }
    }
}
```

**Step 3:** Write `ApiService.kt` with all needed endpoints:

```kotlin
package com.iams.app.data.api

import com.iams.app.data.model.*
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    // Auth
    @POST("auth/verify-student-id")
    suspend fun verifyStudentId(@Body request: VerifyStudentIdRequest): Response<VerifyStudentIdResponse>

    @POST("auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<RegisterResponse>

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): Response<TokenResponse>

    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshRequest): Response<TokenResponse>

    @GET("auth/me")
    suspend fun getMe(): Response<UserResponse>

    @POST("auth/check-email-verified")
    suspend fun checkEmailVerified(@Body request: CheckEmailRequest): Response<EmailVerifiedResponse>

    // Face
    @Multipart
    @POST("face/register")
    suspend fun registerFace(@Part images: List<MultipartBody.Part>): Response<FaceRegisterResponse>

    @GET("face/status")
    suspend fun getFaceStatus(): Response<FaceStatusResponse>

    // Schedules
    @GET("schedules")
    suspend fun getSchedules(): Response<List<ScheduleResponse>>

    @GET("schedules/{id}")
    suspend fun getSchedule(@Path("id") id: String): Response<ScheduleResponse>

    // Attendance
    @GET("attendance/me")
    suspend fun getMyAttendance(
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null,
    ): Response<List<AttendanceRecordResponse>>

    @GET("attendance/me/summary")
    suspend fun getMyAttendanceSummary(): Response<AttendanceSummaryResponse>

    @GET("attendance/today/{scheduleId}")
    suspend fun getTodayAttendance(@Path("scheduleId") scheduleId: String): Response<List<AttendanceRecordResponse>>

    @GET("attendance/live/{scheduleId}")
    suspend fun getLiveAttendance(@Path("scheduleId") scheduleId: String): Response<LiveAttendanceResponse>

    @GET("attendance/schedule/{scheduleId}/summary")
    suspend fun getScheduleAttendanceSummary(@Path("scheduleId") scheduleId: String): Response<AttendanceSummaryResponse>

    // Rooms
    @GET("rooms")
    suspend fun getRooms(): Response<List<RoomResponse>>
}
```

**Step 4:** Write `NetworkModule.kt` (Hilt DI):

```kotlin
package com.iams.app.di

import com.iams.app.data.api.ApiService
import com.iams.app.data.api.AuthInterceptor
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    // Change this to your backend URL
    private const val BASE_URL = "http://10.0.2.2:8000/api/v1/"

    @Provides
    @Singleton
    fun provideOkHttpClient(authInterceptor: AuthInterceptor): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            })
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideApiService(retrofit: Retrofit): ApiService {
        return retrofit.create(ApiService::class.java)
    }
}
```

**Step 5:** Write the data model classes in `android/app/src/main/java/com/iams/app/data/model/`. Create data classes matching the backend Pydantic schemas:

```kotlin
// Models.kt — all API data classes
package com.iams.app.data.model

import com.google.gson.annotations.SerializedName

// Auth
data class LoginRequest(val identifier: String, val password: String)
data class VerifyStudentIdRequest(
    @SerializedName("student_id") val studentId: String,
    val birthdate: String
)
data class VerifyStudentIdResponse(val valid: Boolean, @SerializedName("student_info") val studentInfo: Map<String, Any>?, val message: String)
data class RegisterRequest(
    val email: String, val password: String,
    @SerializedName("first_name") val firstName: String,
    @SerializedName("last_name") val lastName: String,
    @SerializedName("student_id") val studentId: String,
    val birthdate: String
)
data class RegisterResponse(val message: String, val user: UserResponse?)
data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("token_type") val tokenType: String,
    val user: UserResponse
)
data class RefreshRequest(@SerializedName("refresh_token") val refreshToken: String)
data class CheckEmailRequest(val email: String)
data class EmailVerifiedResponse(val verified: Boolean, val message: String)

// User
data class UserResponse(
    val id: String,
    val email: String,
    @SerializedName("first_name") val firstName: String,
    @SerializedName("last_name") val lastName: String,
    val role: String,
    @SerializedName("student_id") val studentId: String?,
    @SerializedName("face_registered") val faceRegistered: Boolean?
)

// Face
data class FaceRegisterResponse(val message: String, @SerializedName("images_processed") val imagesProcessed: Int)
data class FaceStatusResponse(@SerializedName("face_registered") val faceRegistered: Boolean)

// Schedule
data class ScheduleResponse(
    val id: String,
    @SerializedName("subject_name") val subjectName: String,
    @SerializedName("subject_code") val subjectCode: String?,
    @SerializedName("day_of_week") val dayOfWeek: String,
    @SerializedName("start_time") val startTime: String,
    @SerializedName("end_time") val endTime: String,
    @SerializedName("room_name") val roomName: String?,
    @SerializedName("faculty_name") val facultyName: String?,
)

// Attendance
data class AttendanceRecordResponse(
    val id: String,
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("student_id") val studentId: String?,
    @SerializedName("student_name") val studentName: String?,
    val status: String,
    val date: String,
    @SerializedName("check_in_time") val checkInTime: String?,
    @SerializedName("presence_score") val presenceScore: Float?
)
data class AttendanceSummaryResponse(
    @SerializedName("total_classes") val totalClasses: Int,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("absent_count") val absentCount: Int,
    @SerializedName("late_count") val lateCount: Int,
    @SerializedName("attendance_rate") val attendanceRate: Float
)
data class LiveAttendanceResponse(
    @SerializedName("schedule_id") val scheduleId: String,
    @SerializedName("present") val present: List<StudentAttendanceStatus>,
    @SerializedName("absent") val absent: List<StudentAttendanceStatus>,
    @SerializedName("late") val late: List<StudentAttendanceStatus>,
    @SerializedName("early_leave") val earlyLeave: List<StudentAttendanceStatus>
)
data class StudentAttendanceStatus(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("student_name") val studentName: String,
    val status: String,
    @SerializedName("check_in_time") val checkInTime: String?
)

// Room
data class RoomResponse(
    val id: String, val name: String,
    @SerializedName("stream_key") val streamKey: String?
)

// WebSocket scan result
data class ScanResultMessage(
    val type: String,
    @SerializedName("schedule_id") val scheduleId: String,
    val detections: List<Detection>,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("total_enrolled") val totalEnrolled: Int,
    val absent: List<String>,
    @SerializedName("early_leave") val earlyLeave: List<String>
)
data class Detection(
    val bbox: List<Float>,  // [x1, y1, x2, y2] normalized 0-1
    val name: String,
    val confidence: Float,
    @SerializedName("user_id") val userId: String
)
```

**Step 6:** Build:

```bash
cd android && ./gradlew assembleDebug
```

**Step 7:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/data/ android/app/src/main/java/com/iams/app/di/
git commit -m "feat: add Retrofit API client, auth interceptor, data models"
```

---

### Task 9: Set Up Navigation Structure

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/navigation/IAMSNavHost.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/navigation/Routes.kt`

**Step 1:** Define routes:

```kotlin
// Routes.kt
package com.iams.app.ui.navigation

object Routes {
    // Auth
    const val LOGIN = "login"
    const val REGISTER_STEP1 = "register/step1"
    const val REGISTER_STEP2 = "register/step2"
    const val REGISTER_STEP3 = "register/step3"
    const val REGISTER_REVIEW = "register/review"
    const val EMAIL_VERIFICATION = "email-verification"

    // Student
    const val STUDENT_HOME = "student/home"
    const val STUDENT_SCHEDULE = "student/schedule"
    const val STUDENT_HISTORY = "student/history"
    const val STUDENT_PROFILE = "student/profile"

    // Faculty
    const val FACULTY_HOME = "faculty/home"
    const val FACULTY_LIVE_FEED = "faculty/live-feed/{scheduleId}"
    const val FACULTY_REPORTS = "faculty/reports"
    const val FACULTY_PROFILE = "faculty/profile"

    fun facultyLiveFeed(scheduleId: String) = "faculty/live-feed/$scheduleId"
}
```

**Step 2:** Write the NavHost with auth state check:

```kotlin
// IAMSNavHost.kt
package com.iams.app.ui.navigation

import androidx.compose.runtime.*
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.*
import com.iams.app.data.api.TokenManager
import com.iams.app.ui.auth.*
import com.iams.app.ui.student.*
import com.iams.app.ui.faculty.*

@Composable
fun IAMSNavHost(tokenManager: TokenManager = hiltViewModel<NavViewModel>().tokenManager) {
    val navController = rememberNavController()
    val startDestination = remember {
        if (tokenManager.accessToken != null) {
            when (tokenManager.userRole) {
                "faculty" -> Routes.FACULTY_HOME
                else -> Routes.STUDENT_HOME
            }
        } else {
            Routes.LOGIN
        }
    }

    NavHost(navController = navController, startDestination = startDestination) {
        // Auth
        composable(Routes.LOGIN) { LoginScreen(navController) }
        composable(Routes.REGISTER_STEP1) { RegisterStep1Screen(navController) }
        composable(Routes.REGISTER_STEP2) { RegisterStep2Screen(navController) }
        composable(Routes.REGISTER_STEP3) { RegisterStep3Screen(navController) }
        composable(Routes.REGISTER_REVIEW) { RegisterReviewScreen(navController) }

        // Student (with bottom nav)
        composable(Routes.STUDENT_HOME) { StudentHomeScreen(navController) }
        composable(Routes.STUDENT_SCHEDULE) { StudentScheduleScreen(navController) }
        composable(Routes.STUDENT_HISTORY) { StudentHistoryScreen(navController) }
        composable(Routes.STUDENT_PROFILE) { StudentProfileScreen(navController) }

        // Faculty (with bottom nav)
        composable(Routes.FACULTY_HOME) { FacultyHomeScreen(navController) }
        composable(Routes.FACULTY_LIVE_FEED) { backStackEntry ->
            val scheduleId = backStackEntry.arguments?.getString("scheduleId") ?: return@composable
            FacultyLiveFeedScreen(navController, scheduleId)
        }
        composable(Routes.FACULTY_REPORTS) { FacultyReportsScreen(navController) }
        composable(Routes.FACULTY_PROFILE) { FacultyProfileScreen(navController) }
    }
}
```

**Step 3:** Write placeholder screens (empty composables) for all routes so the app compiles. Each screen is a file under the appropriate `ui/` subdirectory with a simple `Text("Screen Name")` placeholder.

**Step 4:** Build and run on emulator:

```bash
cd android && ./gradlew installDebug
```

**Step 5:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/
git commit -m "feat: add navigation structure with placeholder screens"
```

---

### Task 10: Implement Login Screen

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/auth/LoginScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/auth/LoginViewModel.kt`

**Step 1:** Write `LoginViewModel.kt`:

```kotlin
package com.iams.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.LoginRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val loginSuccess: Boolean = false,
    val userRole: String? = null
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState = _uiState.asStateFlow()

    fun login(identifier: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = apiService.login(LoginRequest(identifier, password))
                if (response.isSuccessful) {
                    val body = response.body()!!
                    tokenManager.saveTokens(
                        access = body.accessToken,
                        refresh = body.refreshToken,
                        role = body.user.role,
                        userId = body.user.id
                    )
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        loginSuccess = true,
                        userRole = body.user.role
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Invalid credentials"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Network error: ${e.message}"
                )
            }
        }
    }
}
```

**Step 2:** Write `LoginScreen.kt` composable with two text fields (identifier + password) and a login button. Include a "Register" link for students. Follow Material 3 patterns.

**Step 3:** Build and test on emulator with backend running.

**Step 4:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/
git commit -m "feat: implement login screen with ViewModel"
```

---

## Track 3: Student Screens (Days 6-9)

### Task 11: Student Registration Wizard (Steps 1-4)

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep1Screen.kt` (verify student ID)
- Create: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep2Screen.kt` (create account)
- Create: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep3Screen.kt` (face capture)
- Create: `android/app/src/main/java/com/iams/app/ui/auth/RegisterReviewScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/auth/RegistrationViewModel.kt`

**Step 1:** Write `RegistrationViewModel.kt` — shared across all 4 steps. Holds:
- `studentId`, `birthdate`, `studentInfo` (from step 1 verification)
- `email`, `password`, `firstName`, `lastName` (from step 2)
- `capturedImages: List<Bitmap>` (from step 3)
- Methods: `verifyStudentId()`, `register()`, `registerFace()`

**Step 2:** Implement Step 1 — two fields (Student ID + birthdate picker), calls `POST /auth/verify-student-id`.

**Step 3:** Implement Step 2 — account creation form, calls `POST /auth/register`.

**Step 4:** Implement Step 3 — face capture (see Task 17 for CameraX details). For now, use a placeholder that picks images from gallery.

**Step 5:** Implement Step 4 (review) — shows captured images and info, confirm button calls `POST /face/register`.

**Step 6:** Build and test the full wizard flow.

**Step 7:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/
git commit -m "feat: implement student registration wizard (4 steps)"
```

---

### Task 12: Student Home Dashboard

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/student/StudentHomeScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/student/StudentHomeViewModel.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/components/BottomNavBar.kt`

**Step 1:** Write `StudentHomeViewModel.kt` — fetches `/attendance/me/summary` and `/schedules`. Exposes attendance rate, today's classes, recent records.

**Step 2:** Write `StudentHomeScreen.kt`:
- Attendance rate card (circular progress indicator)
- Today's classes list
- Recent attendance records

**Step 3:** Write `BottomNavBar.kt` — reusable bottom navigation for student and faculty. Student tabs: Home, Schedule, History, Profile.

**Step 4:** Build and test.

**Step 5:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/student/ android/app/src/main/java/com/iams/app/ui/components/
git commit -m "feat: implement student home dashboard with bottom nav"
```

---

### Task 13: Student Schedule + History Screens

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/student/StudentScheduleScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/student/StudentHistoryScreen.kt`

**Step 1:** `StudentScheduleScreen` — fetches `/schedules`, displays as grouped-by-day list.

**Step 2:** `StudentHistoryScreen` — fetches `/attendance/me`, shows list with date filters.

**Step 3:** Build and test.

**Step 4:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/student/
git commit -m "feat: implement student schedule and history screens"
```

---

## Track 4: Faculty Core + Live Feed (Days 9-14) — CRITICAL PATH

### Task 14: Faculty Home Dashboard

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyHomeScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyHomeViewModel.kt`

**Step 1:** Write `FacultyHomeViewModel` — fetches `/schedules` (filtered to faculty's classes), shows today's classes with "Start Session" / "Live Feed" buttons.

**Step 2:** Write `FacultyHomeScreen` — today's active classes, each with a button that navigates to `Routes.facultyLiveFeed(scheduleId)`.

**Step 3:** Build and test.

**Step 4:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/faculty/
git commit -m "feat: implement faculty home dashboard"
```

---

### Task 15: ExoPlayer RTSP Playback Component

This is the foundation of the live feed. A reusable composable that plays an RTSP stream.

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/components/RtspVideoPlayer.kt`

**Step 1:** Write the ExoPlayer composable:

```kotlin
package com.iams.app.ui.components

import android.view.TextureView
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.rtsp.RtspMediaSource

@Composable
fun RtspVideoPlayer(
    rtspUrl: String,
    modifier: Modifier = Modifier,
    onTextureView: ((TextureView) -> Unit)? = null,
    onError: ((String) -> Unit)? = null
) {
    val context = androidx.compose.ui.platform.LocalContext.current

    val player = remember {
        ExoPlayer.Builder(context).build().apply {
            val mediaSource = RtspMediaSource.Factory()
                .setForceUseRtpTcp(true)
                .createMediaSource(MediaItem.fromUri(rtspUrl))
            setMediaSource(mediaSource)
            playWhenReady = true
            prepare()
        }
    }

    DisposableEffect(Unit) {
        val listener = object : Player.Listener {
            override fun onPlayerError(error: PlaybackException) {
                onError?.invoke(error.message ?: "Playback error")
            }
        }
        player.addListener(listener)
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }

    AndroidView(
        factory = { ctx ->
            TextureView(ctx).also { textureView ->
                player.setVideoTextureView(textureView)
                onTextureView?.invoke(textureView)
            }
        },
        modifier = modifier
    )
}
```

**Step 2:** Test with a local RTSP source:

```bash
# Start mediamtx
docker run --rm -p 8554:8554 -p 8889:8889 bluenviron/mediamtx

# Feed a test video
ffmpeg -stream_loop -1 -re -i test_video.mp4 -c:v libx264 -f rtsp rtsp://localhost:8554/test/raw
```

Run the app and verify video plays.

**Step 3:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/components/RtspVideoPlayer.kt
git commit -m "feat: add ExoPlayer RTSP playback composable"
```

---

### Task 16: ML Kit Face Detection on Video Frames

Extract frames from ExoPlayer's TextureView and run ML Kit face detection.

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/components/FaceDetectionProcessor.kt`

**Step 1:** Write the frame processor:

```kotlin
package com.iams.app.ui.components

import android.graphics.Bitmap
import android.graphics.RectF
import android.view.TextureView
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

data class DetectedFaceLocal(
    val boundingBox: RectF,       // normalized 0-1
    val trackingId: Int?,
)

class FaceDetectionProcessor {
    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .enableTracking()
            .setMinFaceSize(0.1f)
            .build()
    )

    private val _detectedFaces = MutableStateFlow<List<DetectedFaceLocal>>(emptyList())
    val detectedFaces = _detectedFaces.asStateFlow()

    private var isProcessing = false
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    fun processFrame(textureView: TextureView) {
        if (isProcessing) return
        isProcessing = true

        val bitmap = textureView.bitmap ?: run {
            isProcessing = false
            return
        }

        val image = InputImage.fromBitmap(bitmap, 0)
        detector.process(image)
            .addOnSuccessListener { faces ->
                val w = bitmap.width.toFloat()
                val h = bitmap.height.toFloat()
                _detectedFaces.value = faces.map { face ->
                    DetectedFaceLocal(
                        boundingBox = RectF(
                            face.boundingBox.left / w,
                            face.boundingBox.top / h,
                            face.boundingBox.right / w,
                            face.boundingBox.bottom / h
                        ),
                        trackingId = face.trackingId
                    )
                }
                bitmap.recycle()
                isProcessing = false
            }
            .addOnFailureListener {
                bitmap.recycle()
                isProcessing = false
            }
    }

    fun close() {
        scope.cancel()
        detector.close()
    }
}
```

**Step 2:** Integrate with ExoPlayer — modify `RtspVideoPlayer` to accept a `FaceDetectionProcessor` and call `processFrame()` on each `onSurfaceTextureUpdated`:

```kotlin
// In the TextureView setup:
textureView.surfaceTextureListener = object : TextureView.SurfaceTextureListener {
    override fun onSurfaceTextureUpdated(surface: SurfaceTexture) {
        faceDetectionProcessor?.processFrame(textureView)
    }
    // ... other callbacks (no-op)
}
```

**Step 3:** Test: run the app with RTSP source and verify `detectedFaces` state updates when faces are visible.

**Step 4:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/components/FaceDetectionProcessor.kt
git commit -m "feat: add ML Kit face detection on ExoPlayer video frames"
```

---

### Task 17: Face Detection Overlay

Draw bounding boxes and name labels on top of the video.

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/components/FaceOverlay.kt`

**Step 1:** Write the overlay composable:

```kotlin
package com.iams.app.ui.components

import android.graphics.RectF
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.sp
import com.iams.app.data.model.Detection

@Composable
fun FaceOverlay(
    localFaces: List<DetectedFaceLocal>,  // ML Kit real-time boxes
    recognitions: List<Detection>,         // Backend names (update every 10-15s)
    modifier: Modifier = Modifier
) {
    Canvas(modifier = modifier.fillMaxSize()) {
        val canvasW = size.width
        val canvasH = size.height

        // Draw ML Kit bounding boxes (real-time)
        for (face in localFaces) {
            val left = face.boundingBox.left * canvasW
            val top = face.boundingBox.top * canvasH
            val right = face.boundingBox.right * canvasW
            val bottom = face.boundingBox.bottom * canvasH

            drawRect(
                color = Color.Green,
                topLeft = Offset(left, top),
                size = Size(right - left, bottom - top),
                style = Stroke(width = 3f)
            )

            // Find matching recognition by IoU
            val matchedName = findMatchingName(face.boundingBox, recognitions)
            if (matchedName != null) {
                drawContext.canvas.nativeCanvas.drawText(
                    matchedName,
                    left,
                    top - 10f,
                    android.graphics.Paint().apply {
                        color = android.graphics.Color.GREEN
                        textSize = 14.sp.toPx()
                        isAntiAlias = true
                    }
                )
            }
        }
    }
}

private fun findMatchingName(faceBox: RectF, recognitions: List<Detection>): String? {
    if (recognitions.isEmpty()) return null
    var bestMatch: Detection? = null
    var bestIoU = 0f

    for (rec in recognitions) {
        val recBox = RectF(rec.bbox[0], rec.bbox[1], rec.bbox[2], rec.bbox[3])
        val iou = calculateIoU(faceBox, recBox)
        if (iou > bestIoU && iou > 0.3f) {
            bestIoU = iou
            bestMatch = rec
        }
    }
    return bestMatch?.name
}

private fun calculateIoU(a: RectF, b: RectF): Float {
    val interLeft = maxOf(a.left, b.left)
    val interTop = maxOf(a.top, b.top)
    val interRight = minOf(a.right, b.right)
    val interBottom = minOf(a.bottom, b.bottom)
    if (interRight <= interLeft || interBottom <= interTop) return 0f
    val interArea = (interRight - interLeft) * (interBottom - interTop)
    val aArea = (a.right - a.left) * (a.bottom - a.top)
    val bArea = (b.right - b.left) * (b.bottom - b.top)
    return interArea / (aArea + bArea - interArea)
}
```

**Step 2:** Test with mock data and real ML Kit detections.

**Step 3:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/components/FaceOverlay.kt
git commit -m "feat: add face detection overlay with name matching"
```

---

### Task 18: WebSocket Client for Attendance Updates

**Files:**
- Create: `android/app/src/main/java/com/iams/app/data/api/WebSocketClient.kt`

**Step 1:** Write the WebSocket client using OkHttp:

```kotlin
package com.iams.app.data.api

import com.google.gson.Gson
import com.iams.app.data.model.Detection
import com.iams.app.data.model.ScanResultMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.*
import java.util.concurrent.TimeUnit

class AttendanceWebSocketClient(
    private val baseUrl: String  // e.g. "ws://10.0.2.2:8000/api/v1/ws"
) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    private val gson = Gson()

    private val _scanResults = MutableStateFlow<ScanResultMessage?>(null)
    val scanResults = _scanResults.asStateFlow()

    private val _detections = MutableStateFlow<List<Detection>>(emptyList())
    val detections = _detections.asStateFlow()

    private val _isConnected = MutableStateFlow(false)
    val isConnected = _isConnected.asStateFlow()

    fun connect(scheduleId: String) {
        val request = Request.Builder()
            .url("$baseUrl/attendance/$scheduleId")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                _isConnected.value = true
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text == "pong") return
                try {
                    val message = gson.fromJson(text, ScanResultMessage::class.java)
                    if (message.type == "scan_result") {
                        _scanResults.value = message
                        _detections.value = message.detections
                    }
                } catch (_: Exception) {}
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                _isConnected.value = false
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                _isConnected.value = false
                // Auto-reconnect after 3 seconds
                Thread.sleep(3000)
                connect(scheduleId)
            }
        })
    }

    fun disconnect() {
        webSocket?.close(1000, "Closing")
        webSocket = null
        _isConnected.value = false
    }
}
```

**Step 2:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/data/api/WebSocketClient.kt
git commit -m "feat: add WebSocket client for attendance updates"
```

---

### Task 19: Faculty Live Feed Screen (The Crown Jewel)

Combines ExoPlayer + ML Kit + Face Overlay + WebSocket + Attendance Panel.

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedViewModel.kt`

**Step 1:** Write `FacultyLiveFeedViewModel`:

```kotlin
package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.AttendanceWebSocketClient
import com.iams.app.data.model.*
import com.iams.app.ui.components.DetectedFaceLocal
import com.iams.app.ui.components.FaceDetectionProcessor
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LiveFeedUiState(
    val rtspUrl: String = "",
    val isLoading: Boolean = true,
    val error: String? = null,
    val presentCount: Int = 0,
    val totalEnrolled: Int = 0,
    val presentStudents: List<StudentAttendanceStatus> = emptyList(),
    val absentStudents: List<StudentAttendanceStatus> = emptyList(),
)

@HiltViewModel
class FacultyLiveFeedViewModel @Inject constructor(
    private val apiService: ApiService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LiveFeedUiState())
    val uiState = _uiState.asStateFlow()

    val faceProcessor = FaceDetectionProcessor()
    private var wsClient: AttendanceWebSocketClient? = null

    // Backend recognition results (names + bboxes)
    val recognitions: StateFlow<List<Detection>>
        get() = wsClient?.detections ?: MutableStateFlow(emptyList())

    // ML Kit local face detections
    val localFaces: StateFlow<List<DetectedFaceLocal>> = faceProcessor.detectedFaces

    fun init(scheduleId: String) {
        viewModelScope.launch {
            // Fetch room info for RTSP URL
            try {
                val schedule = apiService.getSchedule(scheduleId).body()
                val rooms = apiService.getRooms().body() ?: emptyList()
                val room = rooms.find { it.name == schedule?.roomName }

                val rtspUrl = if (room?.streamKey != null) {
                    "rtsp://167.71.217.44:8554/${room.streamKey}/raw"
                } else {
                    ""
                }

                _uiState.value = _uiState.value.copy(
                    rtspUrl = rtspUrl,
                    isLoading = false
                )

                // Connect WebSocket
                wsClient = AttendanceWebSocketClient("ws://167.71.217.44:8000/api/v1/ws")
                wsClient?.connect(scheduleId)

                // Observe WebSocket scan results
                wsClient?.scanResults?.collect { result ->
                    if (result != null) {
                        _uiState.value = _uiState.value.copy(
                            presentCount = result.presentCount,
                            totalEnrolled = result.totalEnrolled,
                        )
                        // Fetch full live attendance for detailed list
                        val live = apiService.getLiveAttendance(scheduleId).body()
                        if (live != null) {
                            _uiState.value = _uiState.value.copy(
                                presentStudents = live.present,
                                absentStudents = live.absent,
                            )
                        }
                    }
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message
                )
            }
        }
    }

    override fun onCleared() {
        wsClient?.disconnect()
        faceProcessor.close()
    }
}
```

**Step 2:** Write `FacultyLiveFeedScreen.kt`:

```kotlin
package com.iams.app.ui.faculty

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.FaceOverlay
import com.iams.app.ui.components.RtspVideoPlayer

@Composable
fun FacultyLiveFeedScreen(
    navController: NavController,
    scheduleId: String,
    viewModel: FacultyLiveFeedViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val localFaces by viewModel.localFaces.collectAsState()
    val recognitions by viewModel.recognitions.collectAsState()

    LaunchedEffect(scheduleId) {
        viewModel.init(scheduleId)
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Video + overlay (top 60%)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(0.6f)
        ) {
            if (uiState.rtspUrl.isNotEmpty()) {
                RtspVideoPlayer(
                    rtspUrl = uiState.rtspUrl,
                    modifier = Modifier.fillMaxSize(),
                    onTextureView = { textureView ->
                        // ML Kit processes frames from this TextureView
                    }
                )

                FaceOverlay(
                    localFaces = localFaces,
                    recognitions = recognitions,
                    modifier = Modifier.fillMaxSize()
                )
            } else if (uiState.error != null) {
                Text("Error: ${uiState.error}", modifier = Modifier.align(Alignment.Center))
            } else {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }
        }

        HorizontalDivider()

        // Attendance panel (bottom 40%)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .weight(0.4f)
                .padding(16.dp)
        ) {
            Text(
                "Present: ${uiState.presentCount}/${uiState.totalEnrolled}",
                style = MaterialTheme.typography.titleMedium
            )

            Spacer(modifier = Modifier.height(8.dp))

            LazyColumn {
                items(uiState.presentStudents) { student ->
                    ListItem(
                        headlineContent = { Text(student.studentName) },
                        leadingContent = { Text("✓") },
                        supportingContent = { Text(student.checkInTime ?: "") }
                    )
                }
                items(uiState.absentStudents) { student ->
                    ListItem(
                        headlineContent = { Text(student.studentName) },
                        leadingContent = { Text("✗") },
                        colors = ListItemDefaults.colors(
                            containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
                        )
                    )
                }
            }
        }
    }
}
```

**Step 3:** Test end-to-end:
1. Start backend + mediamtx + RTSP source
2. Run Kotlin app
3. Login as faculty
4. Open live feed
5. Verify: video plays, ML Kit boxes appear, WebSocket data shows

**Step 4:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeed*
git commit -m "feat: implement faculty live feed — ExoPlayer + ML Kit + WebSocket"
```

---

## Track 5: Face Registration + Polish (Days 14-18)

### Task 20: CameraX Face Registration Screen

The student face registration uses the phone's own camera with ML Kit guidance.

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep3Screen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/components/FaceCaptureView.kt`

**Step 1:** Write `FaceCaptureView.kt` — CameraX + ML Kit for guided face capture:

```kotlin
package com.iams.app.ui.components

import android.graphics.Bitmap
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions

@Composable
fun FaceCaptureView(
    capturedCount: Int,
    requiredCount: Int = 5,
    guidanceText: String,
    onCapture: (Bitmap) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val previewView = remember { PreviewView(context) }

    val detector = remember {
        FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
                .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
                .build()
        )
    }

    var faceDetected by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val cameraProvider = ProcessCameraProvider.getInstance(context).get()
        val preview = Preview.Builder().build().apply {
            surfaceProvider = previewView.surfaceProvider
        }

        val imageAnalysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()

        imageAnalysis.setAnalyzer(ContextCompat.getMainExecutor(context)) { imageProxy ->
            @androidx.camera.core.ExperimentalGetImage
            val mediaImage = imageProxy.image ?: run { imageProxy.close(); return@setAnalyzer }
            val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
            detector.process(image)
                .addOnSuccessListener { faces ->
                    faceDetected = faces.isNotEmpty()
                }
                .addOnCompleteListener { imageProxy.close() }
        }

        cameraProvider.unbindAll()
        cameraProvider.bindToLifecycle(
            context as androidx.lifecycle.LifecycleOwner,
            CameraSelector.DEFAULT_FRONT_CAMERA,
            preview, imageAnalysis
        )
    }

    Column(modifier = modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
        // Camera preview
        AndroidView(factory = { previewView }, modifier = Modifier.weight(1f).fillMaxWidth())

        // Guidance
        Text(
            text = guidanceText,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.padding(16.dp)
        )

        // Capture button
        Button(
            onClick = {
                val bitmap = previewView.bitmap
                if (bitmap != null && faceDetected) {
                    onCapture(bitmap)
                }
            },
            enabled = faceDetected,
            modifier = Modifier.padding(16.dp)
        ) {
            Text("Capture ($capturedCount/$requiredCount)")
        }
    }
}
```

**Step 2:** Wire into `RegisterStep3Screen` — guide user through 3-5 angles:
- "Look straight at the camera"
- "Turn slightly left"
- "Turn slightly right"
- "Tilt head up slightly"
- "Tilt head down slightly"

Each capture adds a bitmap to the ViewModel's list.

**Step 3:** On review screen (Step 4), convert bitmaps to multipart form data and upload to `POST /api/v1/face/register`.

**Step 4:** Test the full registration flow.

**Step 5:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/components/FaceCaptureView.kt android/app/src/main/java/com/iams/app/ui/auth/
git commit -m "feat: implement CameraX face registration with ML Kit guidance"
```

---

### Task 21: Faculty Reports + Profile Screens

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyReportsScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyProfileScreen.kt`
- Create: `android/app/src/main/java/com/iams/app/ui/student/StudentProfileScreen.kt`

**Step 1:** `FacultyReportsScreen` — schedule picker + attendance summary for selected schedule. Calls `/attendance/schedule/{id}/summary`.

**Step 2:** Profile screens — display user info from `/auth/me`, logout button clears tokens and navigates to login.

**Step 3:** Build and test.

**Step 4:** Commit.

```bash
git add android/app/src/main/java/com/iams/app/ui/
git commit -m "feat: add faculty reports and profile screens"
```

---

### Task 22: Backend — Add Normalized Bbox to WebSocket Broadcast

Update the attendance scan cycle to include normalized bounding box coordinates in the WebSocket broadcast, so the mobile app can match them with ML Kit detections.

**File:** Modify `backend/app/services/attendance_engine.py` and `backend/app/main.py` (scan cycle function)

**Step 1:** The `ScanResult.recognized` already has `bbox: tuple[int,int,int,int]` (pixel coordinates). After the scan, normalize them to 0-1:

```python
# In the scan cycle broadcast:
frame_h, frame_w = frame.shape[:2]
detections = []
for face in scan_result.recognized:
    x, y, w, h = face.bbox
    detections.append({
        "bbox": [x / frame_w, y / frame_h, (x + w) / frame_w, (y + h) / frame_h],
        "name": get_user_name(face.user_id),  # lookup from DB
        "confidence": face.confidence,
        "user_id": face.user_id,
    })
```

**Step 2:** Broadcast via the simplified `ws_manager`:

```python
from app.routers.websocket import ws_manager

await ws_manager.broadcast_scan_result(
    schedule_id=schedule_id,
    detections=detections,
    present_count=present_count,
    total_enrolled=total_enrolled,
    absent=absent_names,
    early_leave=early_leave_names,
)
```

**Step 3:** Test by connecting a WebSocket client and verifying the broadcast format matches the Kotlin app's expectations.

**Step 4:** Commit.

```bash
git add backend/app/services/attendance_engine.py backend/app/main.py
git commit -m "feat: broadcast normalized bbox coordinates via WebSocket"
```

---

## Track 6: Integration + Deployment (Days 18-21)

### Task 23: End-to-End Local Integration Test

**Step 1:** Start the full local stack:

```bash
# Terminal 1: mediamtx
docker run --rm -p 8554:8554 -p 8889:8889 -p 8887:8887/udp bluenviron/mediamtx

# Terminal 2: Redis
docker run --rm -p 6379:6379 redis:7-alpine

# Terminal 3: Fake RTSP with a face video
ffmpeg -stream_loop -1 -re -i test_face_video.mp4 -c:v libx264 -f rtsp rtsp://localhost:8554/room1/raw

# Terminal 4: Backend
cd backend && source venv/bin/activate && python run.py
```

**Step 2:** Run Kotlin app on a physical Android phone (USB debugging). The emulator may not support ML Kit or ExoPlayer RTSP well.

**Step 3:** Test full flow:
1. Register a student (login → verify ID → create account → capture face)
2. Verify face appears in FAISS (`GET /api/v1/face/statistics`)
3. Login as faculty
4. Open live feed for a room with the test RTSP source
5. Verify: video plays smoothly, ML Kit boxes appear on faces, backend recognizes faces after 10-15s, names appear on boxes
6. Verify attendance dashboard updates with present/absent

**Step 4:** Document any issues found and fix them.

**Step 5:** Commit fixes.

---

### Task 24: Update Docker Compose for Production

**File:** Modify `deploy/docker-compose.prod.yml`

**Step 1:** Simplify to 4 containers:

```yaml
services:
  api-gateway:
    build:
      context: ../backend
      dockerfile: Dockerfile
    restart: unless-stopped
    mem_limit: 1.5g
    cpus: 1.0
    env_file: ../backend/.env.production
    volumes:
      - faiss_data:/app/data/faiss
      - face_uploads:/app/uploads
    depends_on: [redis, mediamtx]
    networks: [iams]

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    mem_limit: 128m
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru --save ""
    networks: [iams]

  mediamtx:
    image: bluenviron/mediamtx:latest
    restart: unless-stopped
    ports:
      - "8554:8554"
      - "8889:8889"
      - "8887:8887/udp"
    networks: [iams]

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on: [api-gateway]
    networks: [iams]

volumes:
  faiss_data:
  face_uploads:

networks:
  iams:
```

**Step 2:** Update `deploy/deploy.sh` if needed to remove references to deleted services.

**Step 3:** Deploy to VPS:

```bash
bash deploy/deploy.sh
```

**Step 4:** Test on VPS with real RPi camera.

**Step 5:** Commit.

```bash
git add deploy/
git commit -m "refactor: simplify production docker-compose"
```

---

### Task 25: Update CLAUDE.md and Documentation

**File:** Modify `CLAUDE.md`

**Step 1:** Update the project overview, architecture diagram, and technical details to reflect the new architecture:
- Remove all references to MediaPipe on RPi, DeepSORT, FaceNet, ByteTrack
- Update to reflect: InsightFace (SCRFD + ArcFace), ML Kit on mobile, ExoPlayer
- Update the backend structure section
- Remove references to deleted services and routers
- Update mobile section from React Native to Kotlin

**Step 2:** Commit.

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new client-side detection architecture"
```

---

### Task 26: Demo Preparation

**Step 1:** Prepare a test scenario:
1. Pre-register 3-5 students with face data
2. Set up a schedule with a room that has the camera
3. Faculty starts session from the app
4. Students walk into camera view
5. Demo shows: smooth video → ML Kit boxes → names appear → attendance logged

**Step 2:** Create a demo checklist:
- [ ] RPi streaming to VPS mediamtx
- [ ] Backend running, FAISS loaded with registered students
- [ ] Android app installed on demo phone
- [ ] Faculty account ready
- [ ] Test students registered with face data
- [ ] Schedule configured for demo time
- [ ] WiFi stable at demo location

**Step 3:** Run through the demo 2-3 times to identify issues.

---

## Summary

| Track | Tasks | Days | Focus |
|-------|-------|------|-------|
| 1 | Tasks 1-5 | Days 1-3 | Backend simplification |
| 2 | Tasks 6-10 | Days 3-6 | Kotlin project + auth |
| 3 | Tasks 11-13 | Days 6-9 | Student screens |
| 4 | Tasks 14-19 | Days 9-14 | Faculty + Live Feed (critical path) |
| 5 | Tasks 20-22 | Days 14-18 | Face registration + polish |
| 6 | Tasks 23-26 | Days 18-21 | Integration + deployment |

**Parallelism:** Tracks 1 and 2 can run in parallel (backend and mobile are independent). Track 4 depends on Track 2. Track 5 depends on Track 4. Track 6 depends on everything.

**Critical path:** Task 19 (Faculty Live Feed Screen) is the most important deliverable. Everything else supports it.
