package com.iams.app.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.airbnb.lottie.compose.LottieAnimation
import com.airbnb.lottie.compose.LottieCompositionSpec
import com.airbnb.lottie.compose.LottieConstants
import com.airbnb.lottie.compose.animateLottieCompositionAsState
import com.airbnb.lottie.compose.rememberLottieComposition
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import kotlinx.coroutines.launch

private data class OnboardingSlide(
    val title: String,
    val description: String,
    val lottieAsset: String,
)

private val slides = listOf(
    OnboardingSlide(
        title = "Automated Attendance",
        description = "No more manual roll calls. Our AI-powered system automatically tracks your attendance using facial recognition.",
        lottieAsset = "lottie/ai.json",
    ),
    OnboardingSlide(
        title = "Real-time Monitoring",
        description = "Stay updated with live attendance status. Faculty can monitor classes in real-time, students can check their records instantly.",
        lottieAsset = "lottie/analytics.json",
    ),
    OnboardingSlide(
        title = "Face Recognition",
        description = "Secure and accurate identification using advanced face recognition technology. Your face is your attendance card.",
        lottieAsset = "lottie/security-camera.json",
    ),
    OnboardingSlide(
        title = "Easy Access",
        description = "View your schedule, attendance history, and presence scores all in one place. Simple, fast, and reliable.",
        lottieAsset = "lottie/phone.json",
    ),
)

@Composable
fun OnboardingScreen(
    navController: NavController,
    viewModel: SplashViewModel = hiltViewModel(),
) {
    val pagerState = rememberPagerState(pageCount = { slides.size })
    val coroutineScope = rememberCoroutineScope()
    val isLastPage = pagerState.currentPage == slides.size - 1

    val onComplete: () -> Unit = {
        coroutineScope.launch {
            viewModel.setOnboardingComplete()
            navController.navigate(Routes.WELCOME) {
                popUpTo(Routes.ONBOARDING) { inclusive = true }
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Main content
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Pager takes up available space
            HorizontalPager(
                state = pagerState,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
            ) { page ->
                OnboardingPage(slide = slides[page])
            }

            // Bottom section: dots + button
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp)
                    .padding(bottom = 32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                // Pagination dots
                PaginationDots(
                    totalDots = slides.size,
                    currentPage = pagerState.currentPage,
                )

                Spacer(modifier = Modifier.height(24.dp))

                // Next / Get Started button
                IAMSButton(
                    text = if (isLastPage) "Get Started" else "Next",
                    onClick = {
                        if (isLastPage) {
                            onComplete()
                        } else {
                            coroutineScope.launch {
                                pagerState.animateScrollToPage(pagerState.currentPage + 1)
                            }
                        }
                    },
                    variant = IAMSButtonVariant.PRIMARY,
                    size = IAMSButtonSize.LG,
                    fullWidth = true,
                )
            }
        }

        // Skip button — top-right (rendered after Column so it's on top in z-order)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.TopEnd
        ) {
            IAMSButton(
                text = "Skip",
                onClick = onComplete,
                variant = IAMSButtonVariant.GHOST,
                size = IAMSButtonSize.SM,
                fullWidth = false,
            )
        }
    }
}

@Composable
private fun OnboardingPage(slide: OnboardingSlide) {
    val composition by rememberLottieComposition(
        LottieCompositionSpec.Asset(slide.lottieAsset)
    )
    val progress by animateLottieCompositionAsState(
        composition = composition,
        iterations = LottieConstants.IterateForever,
        speed = 0.6f,
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        // Lottie animation
        LottieAnimation(
            composition = composition,
            progress = { progress },
            modifier = Modifier.size(250.dp),
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Title
        Text(
            text = slide.title,
            style = MaterialTheme.typography.headlineLarge.copy(
                fontWeight = FontWeight.SemiBold,
            ),
            color = Primary,
            textAlign = TextAlign.Center,
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Description
        Text(
            text = slide.description,
            style = MaterialTheme.typography.bodyLarge.copy(
                lineHeight = 24.sp,
            ),
            color = TextSecondary,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun PaginationDots(
    totalDots: Int,
    currentPage: Int,
) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        repeat(totalDots) { index ->
            if (index == currentPage) {
                // Active dot: pill shape
                Box(
                    modifier = Modifier
                        .width(24.dp)
                        .height(8.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(Primary)
                )
            } else {
                // Inactive dot: circle
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(Border)
                )
            }
        }
    }
}
