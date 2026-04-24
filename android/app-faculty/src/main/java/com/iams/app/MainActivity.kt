package com.iams.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.iams.app.ui.navigation.FacultyNavHost
import com.iams.app.ui.theme.IAMSTheme
import dagger.hilt.android.AndroidEntryPoint

/**
 * Faculty-app entry activity.
 *
 * Mounts [FacultyNavHost] — a 3-route graph (login → schedules → live feed).
 * The student-oriented [com.iams.app.ui.navigation.IAMSNavHost] is NOT
 * included in this APK's source set.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            IAMSTheme {
                FacultyNavHost()
            }
        }
    }
}
