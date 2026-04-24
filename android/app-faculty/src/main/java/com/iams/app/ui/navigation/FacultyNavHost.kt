package com.iams.app.ui.navigation

import android.net.Uri
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.iams.app.data.api.TokenManager
import com.iams.app.ui.auth.FacultyLoginScreen
import com.iams.app.ui.components.IAMSToastHost
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastState
import com.iams.app.ui.faculty.FacultyLiveFeedScreen
import com.iams.app.ui.faculty.FacultySchedulesScreen
import com.iams.app.ui.onboarding.FacultyWelcomeScreen

/**
 * Faculty routes — 4-screen navigation graph.
 *
 * The monolithic [com.iams.app.ui.navigation.Routes] object lives in the
 * student APK. This object contains only the routes the faculty APK needs.
 */
object FacultyRoutes {
    const val WELCOME = "faculty/welcome"
    const val LOGIN = "faculty/login"
    const val SCHEDULES = "faculty/schedules"

    // Live feed requires a scheduleId (to load the session context) and a
    // roomId (to derive the WHEP stream key).
    const val LIVE_FEED = "faculty/live-feed/{scheduleId}/{roomId}"

    fun liveFeed(scheduleId: String, roomId: String): String =
        "faculty/live-feed/${Uri.encode(scheduleId)}/${Uri.encode(roomId)}"
}

/**
 * 3-screen nav host for the faculty APK.
 *
 * Entry point is decided at runtime: if a valid auth token is already on
 * disk, skip login and go straight to schedules. Otherwise start at login.
 *
 * Wraps the NavHost in `CompositionLocalProvider(LocalToastState ...)` +
 * overlays the `IAMSToastHost` because FacultyLoginScreen (ported from the
 * legacy single APK) uses `LocalToastState.current` — without a provider
 * the app crashes on first compose with "No ToastState provided".
 */
@Composable
fun FacultyNavHost() {
    val navController = rememberNavController()
    val tokenManager: TokenManager = hiltViewModel<NavStartViewModel>().tokenManager
    val toastState = remember { ToastState() }

    val startDestination = if (!tokenManager.userId.isNullOrBlank()) {
        FacultyRoutes.SCHEDULES
    } else {
        FacultyRoutes.WELCOME
    }

    CompositionLocalProvider(LocalToastState provides toastState) {
        Box {
            NavHost(
                navController = navController,
                startDestination = startDestination,
            ) {
                composable(FacultyRoutes.WELCOME) {
                    FacultyWelcomeScreen(navController = navController)
                }

                composable(FacultyRoutes.LOGIN) {
                    FacultyLoginScreen(navController = navController)
                }

                composable(FacultyRoutes.SCHEDULES) {
                    FacultySchedulesScreen(navController = navController)
                }

                composable(
                    route = FacultyRoutes.LIVE_FEED,
                    arguments = listOf(
                        navArgument("scheduleId") { type = NavType.StringType },
                        navArgument("roomId") { type = NavType.StringType },
                    )
                ) { backStackEntry ->
                    FacultyLiveFeedScreen(
                        navController = navController,
                        scheduleId = backStackEntry.arguments?.getString("scheduleId") ?: "",
                        roomId = backStackEntry.arguments?.getString("roomId") ?: "",
                    )
                }
            }

            IAMSToastHost(toastState)
        }
    }
}
