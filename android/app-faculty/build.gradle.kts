// IAMS Faculty App — 2026-04-22 two-app split
//
// Minimal WebRTC viewer that always points at the public VPS (167.71.217.44):
//   - Login  → POST /api/v1/auth/login  (VPS thin backend)
//   - Schedules list  → GET /api/v1/schedules/me
//   - Live feed → WHEP to 167.71.217.44:8889/<stream>/whep (public mediamtx)
//
// No CameraX, no ML Kit Face Detection, no ExoPlayer, no face registration.
// Those live in :app-student. Produces ~50 MB APK (~15 MB smaller than the
// legacy single APK).
//
// BuildConfig keys are sourced from IAMS_FACULTY_* properties in
// android/gradle.properties. These are NEVER mutated by scripts/switch-env.sh
// — the faculty app is always pointed at the VPS, by design.

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt.android)
    alias(libs.plugins.ksp)
}

android {
    // Same namespace as :app-student so `com.iams.app.BuildConfig` and the
    // shared `com.iams.app.*` package hierarchy resolve from both apps
    // without per-file import rewrites. Distinct applicationId (below)
    // gives each app a unique install ID on the phone.
    namespace = "com.iams.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.iams.app.faculty"
        minSdk = 26
        targetSdk = 35
        versionCode = (project.findProperty("versionCode") as? String)?.toInt() ?: 1
        versionName = (project.findProperty("versionName") as? String) ?: "1.0.0"

        // Faculty app always points at the VPS — `switch-env.sh` must NOT
        // touch these keys. Defaults below match production (167.71.217.44)
        // so even a fresh clone without any gradle.properties overrides
        // still produces a faculty APK that works against the real VPS.
        val apiHost = project.findProperty("IAMS_FACULTY_API_HOST") as? String ?: "167.71.217.44"
        val apiPort = project.findProperty("IAMS_FACULTY_API_PORT") as? String ?: "80"
        val streamHost = project.findProperty("IAMS_FACULTY_STREAM_HOST") as? String ?: "167.71.217.44"
        val streamWebrtcPort = project.findProperty("IAMS_FACULTY_STREAM_WEBRTC_PORT") as? String ?: "8889"

        // Fields named the same as :app-student's so the shared copies of
        // NetworkModule, TokenAuthenticator, WhepClient, etc. keep working
        // without per-app code paths.
        buildConfigField("String", "BACKEND_HOST", "\"$apiHost\"")
        buildConfigField("String", "BACKEND_PORT", "\"$apiPort\"")
        buildConfigField("String", "STREAM_HOST", "\"$streamHost\"")
        buildConfigField("String", "STREAM_WEBRTC_PORT", "\"$streamWebrtcPort\"")
        // MEDIAMTX_* kept for compile-time symmetry with files that were
        // originally dual-compiled; faculty app doesn't use them.
        buildConfigField("String", "MEDIAMTX_PORT", "\"8554\"")
        buildConfigField("String", "MEDIAMTX_WEBRTC_PORT", "\"$streamWebrtcPort\"")

        ndk {
            abiFilters += "arm64-v8a"
        }
    }

    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("IAMS_KEYSTORE_PATH")
            if (!keystorePath.isNullOrBlank()) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("IAMS_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("IAMS_KEY_ALIAS")
                keyPassword = System.getenv("IAMS_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
        }
        release {
            isMinifyEnabled = false
            if (signingConfigs.getByName("release").storeFile != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    val composeBom = platform(libs.compose.bom)
    implementation(composeBom)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.icons.extended)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.activity.compose)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.runtime.compose)
    implementation(libs.lifecycle.process)

    implementation(libs.navigation.compose)
    implementation(libs.hilt.navigation.compose)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    implementation(libs.retrofit)
    implementation(libs.retrofit.gson)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)

    // DataStore (token storage)
    implementation(libs.datastore.preferences)

    // Image loading
    implementation(libs.coil.compose)

    // Lottie animations
    implementation(libs.lottie.compose)

    // Coroutines
    implementation(libs.coroutines.android)

    // WebRTC (native libwebrtc for WHEP playback) — the faculty app's
    // raison d'être. Dropped from :app-student in the 2026-04-22 split.
    implementation(libs.stream.webrtc.android)

    // DELIBERATELY NOT INCLUDED:
    //   - libs.mlkit.face.detection     (face-reg-only; lives in :app-student)
    //   - libs.camerax.*                (face-reg-only; lives in :app-student)
    //   - libs.media3.exoplayer.*       (RTSP unused; WebRTC handles playback)

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
    testImplementation("com.google.truth:truth:1.4.2")
}
