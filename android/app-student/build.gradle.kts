plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt.android)
    alias(libs.plugins.ksp)
}

android {
    // Namespace stays `com.iams.app` so existing imports (incl. all
    // `import com.iams.app.BuildConfig` references across shared files)
    // keep working without modification. The install identifier differs
    // from :app-faculty via applicationId below.
    namespace = "com.iams.app"
    compileSdk = 35

    defaultConfig {
        // Two distinct applicationIds so student + faculty APKs can install
        // side-by-side on the same phone. Migrating from the legacy single
        // `com.iams.app` APK requires a one-time uninstall.
        applicationId = "com.iams.app.student"
        minSdk = 26
        targetSdk = 35
        // Overridable from CI: ./gradlew ... -PversionCode=42 -PversionName=1.0.42
        versionCode = (project.findProperty("versionCode") as? String)?.toInt() ?: 1
        versionName = (project.findProperty("versionName") as? String) ?: "1.0.0"

        // BuildConfig: student app uses IAMS_STUDENT_* keys from
        // gradle.properties. scripts/switch-env.sh mutates ONLY these keys
        // (faculty is always VPS). Falls back to the legacy IAMS_BACKEND_*
        // keys for any local.properties that predates the 2026-04-22 split.
        val host = (project.findProperty("IAMS_STUDENT_BACKEND_HOST") as? String)
            ?: (project.findProperty("IAMS_BACKEND_HOST") as? String ?: "192.168.88.254")
        val port = (project.findProperty("IAMS_STUDENT_BACKEND_PORT") as? String)
            ?: (project.findProperty("IAMS_BACKEND_PORT") as? String ?: "8000")
        val mtxPort = project.findProperty("IAMS_MEDIAMTX_PORT") as? String ?: "8554"
        val mtxWebrtcPort = project.findProperty("IAMS_MEDIAMTX_WEBRTC_PORT") as? String ?: "8889"
        val streamHost = project.findProperty("IAMS_STREAM_HOST") as? String ?: "167.71.217.44"
        val streamWebrtcPort = project.findProperty("IAMS_STREAM_WEBRTC_PORT") as? String ?: "8889"

        buildConfigField("String", "BACKEND_HOST", "\"$host\"")
        buildConfigField("String", "BACKEND_PORT", "\"$port\"")
        buildConfigField("String", "MEDIAMTX_PORT", "\"$mtxPort\"")
        buildConfigField("String", "MEDIAMTX_WEBRTC_PORT", "\"$mtxWebrtcPort\"")
        buildConfigField("String", "STREAM_HOST", "\"$streamHost\"")
        buildConfigField("String", "STREAM_WEBRTC_PORT", "\"$streamWebrtcPort\"")

        // Restrict to arm64-v8a so the distributed APK fits under GitHub's 100 MiB
        // per-file limit (Vercel pulls the file from the repo). All target phones
        // (min SDK 26 / Android 8.0) are arm64.
        ndk {
            abiFilters += "arm64-v8a"
        }
    }

    // Release signing — populated from environment variables in CI (GitHub Secrets).
    // Local builds without these env vars produce an unsigned release APK (won't install,
    // but `assembleDebug` still works exactly as before).
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
            // Only attach the signing config if the keystore was actually configured
            // above — otherwise the build silently produces an unsigned APK.
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
    // Compose BOM
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

    // Navigation
    implementation(libs.navigation.compose)
    implementation(libs.hilt.navigation.compose)

    // Hilt DI
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    // Networking
    implementation(libs.retrofit)
    implementation(libs.retrofit.gson)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)

    // ML Kit Face Detection — used by FaceScanScreen for on-device face guidance
    // during the face-registration flow. Do NOT remove; the hybrid live-feed
    // detection was removed in 2026-04-21 but registration still needs it.
    //
    // NOTE: ExoPlayer/Media3 deps were removed in the 2026-04-22 two-app
    // split — RTSP playback lives in :app-faculty only.
    implementation(libs.mlkit.face.detection)

    // CameraX (face registration)
    implementation(libs.camerax.core)
    implementation(libs.camerax.camera2)
    implementation(libs.camerax.lifecycle)
    implementation(libs.camerax.view)

    // DataStore (token storage)
    implementation(libs.datastore.preferences)

    // Image loading
    implementation(libs.coil.compose)

    // Lottie animations
    implementation(libs.lottie.compose)

    // Coroutines
    implementation(libs.coroutines.android)

    // NOTE: WebRTC (libs.stream.webrtc.android) was removed in the 2026-04-22
    // two-app split — the student app has no live-feed UI. WebRTC lives in
    // :app-faculty only.

    // Unit test deps — kept for any future JVM tests. Hybrid tests were removed
    // along with the hybrid/ package on 2026-04-21.
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
    testImplementation("com.google.truth:truth:1.4.2")
}
