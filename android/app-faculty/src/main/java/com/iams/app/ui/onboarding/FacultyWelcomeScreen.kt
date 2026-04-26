package com.iams.app.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.airbnb.lottie.compose.LottieAnimation
import com.airbnb.lottie.compose.LottieCompositionSpec
import com.airbnb.lottie.compose.LottieConstants
import com.airbnb.lottie.compose.animateLottieCompositionAsState
import com.airbnb.lottie.compose.rememberLottieComposition
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.navigation.FacultyRoutes
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

/**
 * FacultyWelcomeScreen — faculty-side counterpart to the student
 * `WelcomeScreen`. Same layout (logo → title → subtitle → CTA) but
 * faculty-specific copy so the two apps feel unmistakably distinct
 * while sharing visual language.
 */
@Composable
fun FacultyWelcomeScreen(
    navController: NavController,
) {
    val composition by rememberLottieComposition(
        LottieCompositionSpec.Asset("lottie/face-id.json")
    )
    val progress by animateLottieCompositionAsState(
        composition = composition,
        iterations = LottieConstants.IterateForever,
        speed = 0.6f,
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 24.dp)
            .padding(bottom = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Logo section: animation + title + subtitle (flex 1, centered)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(top = 40.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            LottieAnimation(
                composition = composition,
                progress = { progress },
                modifier = Modifier.size(200.dp),
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Title — faculty-specific (parallels student's "Welcome to IAMS")
            Text(
                text = "Welcome, Faculty",
                style = MaterialTheme.typography.headlineLarge.copy(
                    fontWeight = FontWeight.Bold,
                ),
                color = Primary,
                textAlign = TextAlign.Center,
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Subtitle — faculty-specific (parallels student's system tagline)
            Text(
                text = "Live classroom monitoring for IAMS",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 24.dp),
            )
        }

        // Role section: heading + login button
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "I am a...",
                style = MaterialTheme.typography.headlineMedium.copy(
                    fontWeight = FontWeight.SemiBold,
                ),
                color = Primary,
                textAlign = TextAlign.Center,
            )

            Spacer(modifier = Modifier.height(20.dp))

            IAMSButton(
                text = "Faculty Login",
                onClick = {
                    navController.navigate(FacultyRoutes.LOGIN)
                },
                variant = IAMSButtonVariant.PRIMARY,
                size = IAMSButtonSize.LG,
                fullWidth = true,
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "Student? Install the separate IAMS Student app.",
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }

        // Footer
        Spacer(modifier = Modifier.height(20.dp))

        Text(
            text = "By continuing, you agree to our Terms of Service and Privacy Policy",
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}
