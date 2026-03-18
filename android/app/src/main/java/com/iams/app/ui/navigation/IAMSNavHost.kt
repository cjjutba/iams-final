package com.iams.app.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Assessment
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.iams.app.ui.auth.EmailVerificationScreen
import com.iams.app.ui.auth.LoginScreen
import com.iams.app.ui.auth.RegisterReviewScreen
import com.iams.app.ui.auth.RegisterStep1Screen
import com.iams.app.ui.auth.RegisterStep2Screen
import com.iams.app.ui.auth.RegisterStep3Screen
import com.iams.app.ui.components.BottomNavTab
import com.iams.app.ui.components.IAMSBottomBar
import com.iams.app.ui.faculty.FacultyHomeScreen
import com.iams.app.ui.faculty.FacultyLiveFeedScreen
import com.iams.app.ui.faculty.FacultyProfileScreen
import com.iams.app.ui.faculty.FacultyReportsScreen
import com.iams.app.ui.student.StudentHistoryScreen
import com.iams.app.ui.student.StudentHomeScreen
import com.iams.app.ui.student.StudentProfileScreen
import com.iams.app.ui.student.StudentScheduleScreen

@Composable
fun IAMSNavHost() {
    val navController = rememberNavController()
    val navViewModel: NavViewModel = hiltViewModel()

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    // Determine start destination based on auth state
    val startDestination = when {
        navViewModel.tokenManager.accessToken != null -> {
            when (navViewModel.tokenManager.userRole) {
                "faculty" -> Routes.FACULTY_HOME
                else -> Routes.STUDENT_HOME
            }
        }
        else -> Routes.LOGIN
    }

    val studentTabs = listOf(
        BottomNavTab("Home", Icons.Default.Home, Routes.STUDENT_HOME),
        BottomNavTab("Schedule", Icons.Default.Schedule, Routes.STUDENT_SCHEDULE),
        BottomNavTab("History", Icons.Default.History, Routes.STUDENT_HISTORY),
        BottomNavTab("Profile", Icons.Default.Person, Routes.STUDENT_PROFILE),
    )

    val facultyTabs = listOf(
        BottomNavTab("Home", Icons.Default.Home, Routes.FACULTY_HOME),
        BottomNavTab("Live Feed", Icons.Default.Videocam, Routes.FACULTY_REPORTS),
        BottomNavTab("Reports", Icons.Default.Assessment, Routes.FACULTY_REPORTS),
        BottomNavTab("Profile", Icons.Default.Person, Routes.FACULTY_PROFILE),
    )

    val isStudentSection = currentRoute in studentTabs.map { it.route }
    val isFacultySection = currentRoute in facultyTabs.map { it.route }
    val showBottomBar = isStudentSection || isFacultySection

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
            // Auth screens
            composable(Routes.LOGIN) {
                LoginScreen(navController = navController)
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
                )
            ) { backStackEntry ->
                RegisterStep2Screen(
                    navController = navController,
                    studentId = backStackEntry.arguments?.getString("studentId") ?: "",
                    firstName = backStackEntry.arguments?.getString("firstName") ?: "",
                    lastName = backStackEntry.arguments?.getString("lastName") ?: "",
                )
            }

            composable(Routes.REGISTER_STEP3) {
                RegisterStep3Screen(navController = navController)
            }

            composable(Routes.REGISTER_REVIEW) {
                RegisterReviewScreen(navController = navController)
            }

            composable(
                route = Routes.EMAIL_VERIFICATION,
                arguments = listOf(
                    navArgument("email") { type = NavType.StringType }
                )
            ) { backStackEntry ->
                EmailVerificationScreen(
                    navController = navController,
                    email = backStackEntry.arguments?.getString("email") ?: "",
                )
            }

            // Student screens
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

            // Faculty screens
            composable(Routes.FACULTY_HOME) {
                FacultyHomeScreen(navController = navController)
            }

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

            composable(Routes.FACULTY_PROFILE) {
                FacultyProfileScreen(navController = navController)
            }
        }
    }
}
