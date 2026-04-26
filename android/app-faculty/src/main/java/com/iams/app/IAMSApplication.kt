package com.iams.app

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Faculty-app Hilt entry point.
 *
 * Deliberately minimal: no NotificationService (faculty app has no push
 * notifications), no lifecycle observers, no background WebSocket. The
 * faculty user launches the app, logs in, picks a schedule, watches the
 * stream, and closes it.
 *
 * Named `IAMSApplication` (not `FacultyApplication`) so the AndroidManifest
 * `android:name=".IAMSApplication"` string matches both apps' application
 * classes — simplifies manifest copy/paste without renames.
 */
@HiltAndroidApp
class IAMSApplication : Application()
