package com.iams.app.ui.auth

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.NavController
import com.iams.app.ui.navigation.Routes

/**
 * Email verification is no longer required (local JWT auth, no Supabase).
 * This screen simply redirects to the student login screen.
 * Kept as a stub in case any deep-link or navigation path still references it.
 */
@Composable
fun EmailVerificationScreen(
    navController: NavController,
    email: String,
) {
    LaunchedEffect(Unit) {
        navController.navigate(Routes.STUDENT_LOGIN) {
            popUpTo(0) { inclusive = true }
        }
    }
}
