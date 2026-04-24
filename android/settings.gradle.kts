pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
    // Hilt's gradle plugin doesn't publish the standard plugin-marker artifact
    // (com.google.dagger.hilt.android:com.google.dagger.hilt.android.gradle.plugin)
    // to Google Maven, so the plugins {} DSL fails on a clean checkout (CI).
    // Local builds work only because the actual hilt-android-gradle-plugin
    // module is already in ~/.gradle/caches from a prior run. Map the plugin
    // id directly to its real coordinates so resolution is reliable everywhere.
    resolutionStrategy {
        eachPlugin {
            if (requested.id.id == "com.google.dagger.hilt.android") {
                useModule("com.google.dagger:hilt-android-gradle-plugin:${requested.version}")
            }
        }
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "IAMS"

// Two Android APKs after the 2026-04-22 two-app split:
//   :app-student — full-feature student app, points at the on-prem Mac backend
//                  (IAMS-Net only). Ships CameraX + ML Kit for face registration.
//   :app-faculty — minimal pure-viewer, points at the public VPS for auth +
//                  schedules + live WebRTC stream. No CameraX, no ML Kit.
include(":app-student")
include(":app-faculty")
