package com.iams.app.ui.auth

import android.graphics.Bitmap
import androidx.compose.foundation.Image
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
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
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
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Green500
import com.iams.app.ui.theme.Red500

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
            .padding(horizontal = 24.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(modifier = Modifier.height(48.dp))

        // Header icon
        Icon(
            imageVector = if (hasFaces) Icons.Default.CheckCircle else Icons.Default.Person,
            contentDescription = "Review",
            modifier = Modifier.size(72.dp),
            tint = Green500
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "Review Registration",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Student info summary
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            )
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                Text(
                    text = "Student Information",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.primary
                )

                Spacer(modifier = Modifier.height(12.dp))

                ReviewInfoRow(
                    label = "Name",
                    value = "${uiState.firstName} ${uiState.lastName}".trim()
                        .ifEmpty { "Completed in Step 1" }
                )

                HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

                ReviewInfoRow(
                    label = "Student ID",
                    value = uiState.studentId.ifEmpty { "Completed in Step 1" }
                )

                HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

                ReviewInfoRow(
                    label = "Email",
                    value = uiState.registeredEmail.ifEmpty { "Completed in Step 2" }
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Face registration section
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            )
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Face,
                        contentDescription = "Face",
                        modifier = Modifier.size(20.dp),
                        tint = if (hasFaces) Green500 else Red500
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Face Registration",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                if (hasFaces) {
                    Text(
                        text = "${uiState.capturedFaces.size} face photo(s) captured",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Green500
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
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.Warning,
                            contentDescription = "Warning",
                            modifier = Modifier.size(16.dp),
                            tint = Red500
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Face registration was skipped. You can register your face later from your profile.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
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

        Spacer(modifier = Modifier.height(16.dp))

        // Submit button
        Button(
            onClick = {
                if (hasFaces) {
                    viewModel.uploadFaceImages()
                } else {
                    // No faces captured — go directly to login
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            enabled = !uiState.isUploading
        ) {
            if (uiState.isUploading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = MaterialTheme.colorScheme.onPrimary,
                    strokeWidth = 2.dp
                )
            } else {
                Text(
                    text = if (hasFaces) "Submit Registration" else "Complete Registration",
                    style = MaterialTheme.typography.titleMedium
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

@Composable
private fun ReviewInfoRow(label: String, value: String) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge
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
            .clip(RoundedCornerShape(8.dp))
            .border(
                1.dp,
                MaterialTheme.colorScheme.outline,
                RoundedCornerShape(8.dp)
            )
    )
}
