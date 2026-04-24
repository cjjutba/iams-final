package com.iams.app.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Schedule

import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.navigation
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.iams.app.ui.auth.ForgotPasswordScreen
import com.iams.app.ui.auth.ResetPasswordScreen
import com.iams.app.ui.auth.RegisterReviewScreen
import com.iams.app.ui.auth.RegisterStep1Screen
import com.iams.app.ui.auth.RegisterStep2Screen
import com.iams.app.ui.auth.RegisterStep3Screen
import com.iams.app.ui.auth.RegistrationViewModel
import com.iams.app.ui.auth.StudentLoginScreen
import com.iams.app.ui.onboarding.OnboardingScreen
import com.iams.app.ui.onboarding.SplashScreen
import com.iams.app.ui.onboarding.WelcomeScreen
import com.iams.app.ui.components.BottomNavTab
import com.iams.app.ui.components.IAMSBottomBar
import com.iams.app.ui.components.IAMSToastHost
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.common.SettingsScreen
import com.iams.app.ui.student.StudentAnalyticsScreen
import com.iams.app.ui.student.StudentAttendanceDetailScreen
import com.iams.app.ui.student.StudentEditProfileScreen
import com.iams.app.ui.student.StudentHistoryScreen
import com.iams.app.ui.student.StudentHomeScreen
import com.iams.app.ui.student.StudentNotificationsScreen
import com.iams.app.ui.student.StudentProfileScreen
import com.iams.app.ui.student.StudentScheduleScreen

/**
 * Student-only navigation host.
 *
 * Faculty routes + screens moved to the dedicated `:app-faculty` APK in the
 * 2026-04-22 two-app split. This APK (applicationId `com.iams.app.student`)
 * contains only the student-facing onboarding, auth, registration, and
 * primary dashboard screens.
 */
@Composable
fun IAMSNavHost() {
    val navController = rememberNavController()
    val navViewModel: NavViewModel = hiltViewModel()
    val toastState = remember { ToastState() }

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    // Always start at splash — it checks auth state and routes accordingly
    val startDestination = Routes.SPLASH

    val studentTabs = listOf(
        BottomNavTab("Home", Icons.Outlined.Home, Icons.Filled.Home, Routes.STUDENT_HOME),
        BottomNavTab("Schedule", Icons.Outlined.Schedule, Icons.Filled.Schedule, Routes.STUDENT_SCHEDULE),
        // History's destination route is the templated pattern (optional `scheduleId`
        // query arg), so we match against STUDENT_HISTORY_PATTERN while still
        // navigating to the plain STUDENT_HISTORY path on tab click.
        BottomNavTab(
            label = "History",
            icon = Icons.Outlined.History,
            selectedIcon = Icons.Filled.History,
            route = Routes.STUDENT_HISTORY_PATTERN,
            navRoute = Routes.STUDENT_HISTORY,
        ),
        BottomNavTab("Profile", Icons.Outlined.Person, Icons.Filled.Person, Routes.STUDENT_PROFILE),
    )

    val isStudentSection = currentRoute in studentTabs.map { it.route }
    val showBottomBar = isStudentSection

    // Observe notification WebSocket events and show toasts
    LaunchedEffect(navViewModel.notificationService) {
        navViewModel.notificationService.events?.collect { event ->
            val toastType = when (event.toastType) {
                "success" -> ToastType.SUCCESS
                "warning" -> ToastType.WARNING
                "error" -> ToastType.ERROR
                else -> ToastType.INFO
            }
            toastState.showToast(event.title, toastType, subtitle = event.message)
            navViewModel.notificationService.incrementUnreadCount()
        }
    }

    CompositionLocalProvider(LocalToastState provides toastState) {
        Box {
            Scaffold(
                bottomBar = {
                    if (showBottomBar) IAMSBottomBar(navController, studentTabs)
                }
            ) { innerPadding ->
                NavHost(
                    navController = navController,
                    startDestination = startDestination,
                    modifier = Modifier.padding(innerPadding)
                ) {
                    // ── Onboarding flow ─────────────────────────────────────────────
                    composable(Routes.SPLASH) {
                        SplashScreen(navController = navController)
                    }

                    composable(Routes.ONBOARDING) {
                        OnboardingScreen(navController = navController)
                    }

                    // Welcome / role-selection screen. After the two-app split this
                    // is effectively the student-landing — the faculty button that
                    // used to live here now opens the faculty-APK link text.
                    composable(Routes.WELCOME) {
                        WelcomeScreen(navController = navController)
                    }

                    // ── Auth screens ────────────────────────────────────────────────
                    composable(Routes.STUDENT_LOGIN) {
                        StudentLoginScreen(navController = navController)
                    }

                    composable(Routes.FORGOT_PASSWORD) {
                        ForgotPasswordScreen(navController = navController)
                    }

                    composable(Routes.RESET_PASSWORD) {
                        ResetPasswordScreen(navController = navController)
                    }

                    composable(Routes.REGISTER_STEP1) {
                        RegisterStep1Screen(navController = navController)
                    }

                    composable(
                        route = Routes.REGISTER_STEP2,
                        arguments = listOf(
                            navArgument("studentId") { type = NavType.StringType },
                            navArgument("firstName") { type = NavType.StringType },
                            navArgument("lastName") { type = NavType.StringType },
                            navArgument("email") { type = NavType.StringType },
                        )
                    ) { backStackEntry ->
                        val emailArg = backStackEntry.arguments?.getString("email") ?: ""
                        RegisterStep2Screen(
                            navController = navController,
                            studentId = backStackEntry.arguments?.getString("studentId") ?: "",
                            firstName = backStackEntry.arguments?.getString("firstName") ?: "",
                            lastName = backStackEntry.arguments?.getString("lastName") ?: "",
                            prefillEmail = if (emailArg == "_") "" else emailArg,
                        )
                    }

                    // Nested nav graph for face registration flow (Step3 + Review share ViewModel)
                    navigation(
                        startDestination = Routes.REGISTER_STEP3_INNER,
                        route = Routes.REGISTER_FACE_FLOW
                    ) {
                        composable(Routes.REGISTER_STEP3_INNER) {
                            val parentEntry = remember(it) {
                                navController.getBackStackEntry(Routes.REGISTER_FACE_FLOW)
                            }
                            val sharedViewModel: RegistrationViewModel = hiltViewModel(parentEntry)
                            RegisterStep3Screen(
                                navController = navController,
                                viewModel = sharedViewModel
                            )
                        }

                        composable(Routes.REGISTER_REVIEW_INNER) {
                            val parentEntry = remember(it) {
                                navController.getBackStackEntry(Routes.REGISTER_FACE_FLOW)
                            }
                            val sharedViewModel: RegistrationViewModel = hiltViewModel(parentEntry)
                            RegisterReviewScreen(
                                navController = navController,
                                viewModel = sharedViewModel,
                            )
                        }
                    }

                    // ── Student screens (primary tabs) ─────────────────────────────
                    composable(Routes.STUDENT_HOME) {
                        StudentHomeScreen(navController = navController)
                    }

                    composable(Routes.STUDENT_SCHEDULE) {
                        StudentScheduleScreen(navController = navController)
                    }

                    composable(
                        route = Routes.STUDENT_HISTORY_PATTERN,
                        arguments = listOf(
                            navArgument("scheduleId") {
                                type = NavType.StringType
                                nullable = true
                                defaultValue = null
                            },
                        ),
                    ) {
                        StudentHistoryScreen(navController = navController)
                    }

                    composable(Routes.STUDENT_PROFILE) {
                        StudentProfileScreen(navController = navController)
                    }

                    // ── Student screens (secondary) ─────────────────────────────────
                    composable(
                        route = Routes.STUDENT_ATTENDANCE_DETAIL,
                        arguments = listOf(
                            navArgument("attendanceId") { type = NavType.StringType },
                            navArgument("scheduleId") { type = NavType.StringType },
                            navArgument("date") { type = NavType.StringType },
                        )
                    ) {
                        StudentAttendanceDetailScreen(navController = navController)
                    }

                    composable(Routes.STUDENT_ANALYTICS) {
                        StudentAnalyticsScreen(navController = navController)
                    }

                    composable(Routes.STUDENT_EDIT_PROFILE) {
                        StudentEditProfileScreen(navController = navController)
                    }

                    composable(Routes.STUDENT_NOTIFICATIONS) {
                        StudentNotificationsScreen(navController = navController)
                    }

                    composable(
                        route = Routes.STUDENT_FACE_REGISTER,
                        arguments = listOf(
                            navArgument("mode") { type = NavType.StringType },
                        )
                    ) { backStackEntry ->
                        val mode = backStackEntry.arguments?.getString("mode") ?: "register"
                        // Standalone face registration from student profile (not during signup flow)
                        RegisterStep3Screen(
                            navController = navController,
                            isStandalone = true,
                            isReregister = mode == "reregister"
                        )
                    }

                    // ── Common screens ──────────────────────────────────────────────
                    composable(Routes.SETTINGS) {
                        SettingsScreen(navController = navController)
                    }
                }
            }

            IAMSToastHost(toastState)
        }
    }
}
