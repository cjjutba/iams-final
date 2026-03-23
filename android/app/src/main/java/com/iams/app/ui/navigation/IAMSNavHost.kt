package com.iams.app.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Assessment
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Schedule

import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
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
import com.iams.app.ui.auth.FacultyLoginScreen
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
import com.iams.app.ui.common.SettingsScreen
import com.iams.app.ui.faculty.FacultyAlertsScreen
import com.iams.app.ui.faculty.FacultyAnalyticsDashboardScreen
import com.iams.app.ui.faculty.FacultyClassDetailScreen
import com.iams.app.ui.faculty.FacultyEditProfileScreen
import com.iams.app.ui.faculty.FacultyHomeScreen
import com.iams.app.ui.faculty.FacultyLiveAttendanceScreen
import com.iams.app.ui.faculty.FacultyLiveFeedScreen
import com.iams.app.ui.faculty.FacultyManualEntryScreen
import com.iams.app.ui.faculty.FacultyNotificationsScreen
import com.iams.app.ui.faculty.FacultyProfileScreen
import com.iams.app.ui.faculty.FacultyReportsScreen
import com.iams.app.ui.faculty.FacultyScheduleScreen
import com.iams.app.ui.faculty.FacultyStudentDetailScreen
import com.iams.app.ui.student.StudentAnalyticsScreen
import com.iams.app.ui.student.StudentAttendanceDetailScreen
import com.iams.app.ui.student.StudentEditProfileScreen
import com.iams.app.ui.student.StudentHistoryScreen
import com.iams.app.ui.student.StudentHomeScreen
import com.iams.app.ui.student.StudentNotificationsScreen
import com.iams.app.ui.student.StudentProfileScreen
import com.iams.app.ui.student.StudentScheduleScreen

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
        BottomNavTab("Home", Icons.Default.Home, Routes.STUDENT_HOME),
        BottomNavTab("Schedule", Icons.Default.Schedule, Routes.STUDENT_SCHEDULE),
        BottomNavTab("History", Icons.Default.History, Routes.STUDENT_HISTORY),
        BottomNavTab("Profile", Icons.Default.Person, Routes.STUDENT_PROFILE),
    )

    val facultyTabs = listOf(
        BottomNavTab("Home", Icons.Default.Home, Routes.FACULTY_HOME),
        BottomNavTab("Schedule", Icons.Default.Schedule, Routes.FACULTY_SCHEDULE),
        BottomNavTab("Analytics", Icons.Default.Assessment, Routes.FACULTY_ANALYTICS_DASHBOARD),
        BottomNavTab("Alerts", Icons.Default.Notifications, Routes.FACULTY_ALERTS),
        BottomNavTab("Profile", Icons.Default.Person, Routes.FACULTY_PROFILE),
    )

    val isStudentSection = currentRoute in studentTabs.map { it.route }
    val isFacultySection = currentRoute in facultyTabs.map { it.route }
    val showBottomBar = isStudentSection || isFacultySection

    CompositionLocalProvider(LocalToastState provides toastState) {
        Box {
            Scaffold(
                bottomBar = {
                    when {
                        isStudentSection -> IAMSBottomBar(navController, studentTabs)
                        isFacultySection -> IAMSBottomBar(navController, facultyTabs)
                    }
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

            // Welcome / role-selection screen
            composable(Routes.WELCOME) {
                WelcomeScreen(navController = navController)
            }

            // ── Auth screens ────────────────────────────────────────────────
            composable(Routes.STUDENT_LOGIN) {
                StudentLoginScreen(navController = navController)
            }

            composable(Routes.FACULTY_LOGIN) {
                FacultyLoginScreen(navController = navController)
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
                    val parentEntry = navController.getBackStackEntry(Routes.REGISTER_FACE_FLOW)
                    val sharedViewModel: RegistrationViewModel = hiltViewModel(parentEntry)
                    RegisterStep3Screen(
                        navController = navController,
                        viewModel = sharedViewModel
                    )
                }

                composable(Routes.REGISTER_REVIEW_INNER) {
                    val parentEntry = navController.getBackStackEntry(Routes.REGISTER_FACE_FLOW)
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

            composable(Routes.STUDENT_HISTORY) {
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

            // ── Faculty screens (primary tabs) ──────────────────────────────
            composable(Routes.FACULTY_HOME) {
                FacultyHomeScreen(navController = navController)
            }

            composable(Routes.FACULTY_SCHEDULE) {
                FacultyScheduleScreen(navController = navController)
            }

            composable(Routes.FACULTY_ANALYTICS_DASHBOARD) {
                FacultyAnalyticsDashboardScreen(navController = navController)
            }

            composable(Routes.FACULTY_ALERTS) {
                FacultyAlertsScreen(navController = navController)
            }

            composable(Routes.FACULTY_PROFILE) {
                FacultyProfileScreen(navController = navController)
            }

            // ── Faculty screens (secondary / stack) ─────────────────────────
            composable(
                route = Routes.FACULTY_LIVE_FEED,
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

            composable(Routes.FACULTY_REPORTS) {
                FacultyReportsScreen(navController = navController)
            }

            composable(
                route = Routes.FACULTY_CLASS_DETAIL,
                arguments = listOf(
                    navArgument("scheduleId") { type = NavType.StringType },
                )
            ) {
                FacultyClassDetailScreen(navController = navController)
            }

            composable(
                route = Routes.FACULTY_STUDENT_DETAIL,
                arguments = listOf(
                    navArgument("studentId") { type = NavType.StringType },
                    navArgument("scheduleId") { type = NavType.StringType },
                )
            ) {
                FacultyStudentDetailScreen(navController = navController)
            }

            composable(Routes.FACULTY_EDIT_PROFILE) {
                FacultyEditProfileScreen(navController = navController)
            }

            composable(Routes.FACULTY_NOTIFICATIONS) {
                FacultyNotificationsScreen(navController = navController)
            }

            composable(
                route = Routes.FACULTY_LIVE_ATTENDANCE,
                arguments = listOf(
                    navArgument("scheduleId") { type = NavType.StringType },
                )
            ) { backStackEntry ->
                FacultyLiveAttendanceScreen(
                    navController = navController,
                    scheduleId = backStackEntry.arguments?.getString("scheduleId") ?: "",
                )
            }

            composable(
                route = Routes.FACULTY_MANUAL_ENTRY,
                arguments = listOf(
                    navArgument("scheduleId") { type = NavType.StringType },
                )
            ) { backStackEntry ->
                FacultyManualEntryScreen(
                    navController = navController,
                    scheduleId = backStackEntry.arguments?.getString("scheduleId") ?: "",
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
