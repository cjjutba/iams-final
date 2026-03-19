package com.iams.app.ui.auth

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun RegisterReviewScreen(
    navController: NavController,
    viewModel: RegistrationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val hasFaces = uiState.capturedFaces.isNotEmpty()

    // Navigate to login on successful upload or if skipping faces
    LaunchedEffect(uiState.uploadSuccess) {
        if (uiState.uploadSuccess) {
            navController.navigate(Routes.LOGIN) {
                popUpTo(Routes.LOGIN) { inclusive = true }
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Header
        IAMSHeader(
            title = "Review",
            onBack = { navController.popBackStack() }
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .padding(top = 24.dp, bottom = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Title
            Text(
                text = "Review Registration",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onBackground,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "Please review your information before submitting.",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Student info card
            IAMSCard {
                Text(
                    text = "Student Information",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onBackground
                )

                Spacer(modifier = Modifier.height(16.dp))

                ReviewInfoRow(
                    label = "Name",
                    value = "${uiState.firstName} ${uiState.lastName}".trim()
                        .ifEmpty { "Completed in Step 1" }
                )

                Spacer(modifier = Modifier.height(12.dp))

                ReviewInfoRow(
                    label = "Student ID",
                    value = uiState.studentId.ifEmpty { "Completed in Step 1" }
                )

                Spacer(modifier = Modifier.height(12.dp))

                ReviewInfoRow(
                    label = "Email",
                    value = uiState.registeredEmail.ifEmpty { "Completed in Step 2" }
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Face registration card
            IAMSCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Face,
                        contentDescription = "Face",
                        modifier = Modifier.size(20.dp),
                        tint = if (hasFaces) PresentFg else AbsentFg
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Face Registration",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onBackground
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                if (hasFaces) {
                    Text(
                        text = "${uiState.capturedFaces.size} face photo(s) captured",
                        style = MaterialTheme.typography.bodyMedium,
                        color = PresentFg
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    // Face image grid
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(3),
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(
                                ((uiState.capturedFaces.size + 2) / 3 * 110).dp
                            ),
                        contentPadding = PaddingValues(4.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        userScrollEnabled = false
                    ) {
                        itemsIndexed(uiState.capturedFaces) { index, bitmap ->
                            FaceGridItem(bitmap = bitmap, index = index)
                        }
                    }
                } else {
                    // Warning badge
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Secondary, RoundedCornerShape(10.dp))
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Warning,
                            contentDescription = "Warning",
                            modifier = Modifier.size(16.dp),
                            tint = AbsentFg
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Face registration was skipped. You can register your face later from your profile.",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Error message
            if (uiState.uploadError != null) {
                Text(
                    text = uiState.uploadError!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(8.dp))
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Submit button
            IAMSButton(
                text = if (hasFaces) "Submit Registration" else "Complete Registration",
                onClick = {
                    if (hasFaces) {
                        viewModel.uploadFaceImages()
                    } else {
                        // No faces captured -- go directly to login
                        navController.navigate(Routes.LOGIN) {
                            popUpTo(Routes.LOGIN) { inclusive = true }
                        }
                    }
                },
                enabled = !uiState.isUploading,
                isLoading = uiState.isUploading
            )
        }
    }
}

@Composable
private fun ReviewInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = TextTertiary
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onBackground
        )
    }
}

@Composable
private fun FaceGridItem(bitmap: Bitmap, index: Int) {
    Image(
        bitmap = bitmap.asImageBitmap(),
        contentDescription = "Face photo ${index + 1}",
        modifier = Modifier
            .size(100.dp)
            .clip(RoundedCornerShape(10.dp))
            .border(
                1.dp,
                Border,
                RoundedCornerShape(10.dp)
            )
    )
}
