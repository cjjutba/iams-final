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

        // Configured via gradle.properties; override per-machine in local.properties
        val host = project.findProperty("IAMS_BACKEND_HOST") as? String ?: "192.168.88.254"
        val port = project.findProperty("IAMS_BACKEND_PORT") as? String ?: "8000"
        val mtxPort = project.findProperty("IAMS_MEDIAMTX_PORT") as? String ?: "8554"
        val mtxWebrtcPort = project.findProperty("IAMS_MEDIAMTX_WEBRTC_PORT") as? String ?: "8889"

        buildConfigField("String", "BACKEND_HOST", "\"$host\"")
        buildConfigField("String", "BACKEND_PORT", "\"$port\"")
        buildConfigField("String", "MEDIAMTX_PORT", "\"$mtxPort\"")
        buildConfigField("String", "MEDIAMTX_WEBRTC_PORT", "\"$mtxWebrtcPort\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
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

    // ExoPlayer (Media3) for RTSP
    implementation(libs.media3.exoplayer)
    implementation(libs.media3.exoplayer.rtsp)
    implementation(libs.media3.ui)

    // ML Kit Face Detection (used by FaceCaptureView for on-device face detection during registration)
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

    // WebRTC (native libwebrtc for WHEP playback)
    implementation(libs.stream.webrtc.android)
}
