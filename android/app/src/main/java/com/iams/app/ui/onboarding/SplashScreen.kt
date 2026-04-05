package com.iams.app.ui.onboarding

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.R
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Background
import kotlinx.coroutines.delay

@Composable
fun SplashScreen(
    navController: NavController,
    viewModel: SplashViewModel = hiltViewModel(),
) {
    // Breathing animation: scale 1.0 -> 1.06, alpha 0.85 -> 1.0, 2-second loop
    val infiniteTransition = rememberInfiniteTransition(label = "splash_breathing")

    val scale by infiniteTransition.animateFloat(
        initialValue = 1.0f,
        targetValue = 1.06f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 2000,
                easing = androidx.compose.animation.core.CubicBezierEasing(0.42f, 0f, 0.58f, 1f)
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "splash_scale"
    )

    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 2000,
                easing = androidx.compose.animation.core.CubicBezierEasing(0.42f, 0f, 0.58f, 1f)
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "splash_alpha"
    )

    // Auth check + navigation after 2 seconds
    LaunchedEffect(Unit) {
        delay(2000)

        val onboardingComplete = viewModel.isOnboardingComplete()

        val destination = when {
            !onboardingComplete -> Routes.ONBOARDING
            viewModel.hasTokens() -> {
                when (viewModel.userRole()) {
                    "faculty" -> Routes.FACULTY_HOME
                    else -> Routes.STUDENT_HOME
                }
            }
            else -> Routes.WELCOME
        }

        navController.navigate(destination) {
            popUpTo(Routes.SPLASH) { inclusive = true }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Background),
        contentAlignment = Alignment.Center
    ) {
        Image(
            painter = painterResource(id = R.drawable.iams_icon),
            contentDescription = "IAMS Icon",
            modifier = Modifier
                .size(140.dp)
                .graphicsLayer {
                    scaleX = scale
                    scaleY = scale
                    this.alpha = alpha
                }
        )
    }
}
