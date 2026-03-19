package com.iams.app.ui.faculty

import android.graphics.SurfaceTexture
import android.view.TextureView
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.ui.components.FaceOverlay
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.RtspVideoPlayer
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun FacultyLiveFeedScreen(
    navController: NavController,
    scheduleId: String,
    roomId: String,
    viewModel: FacultyLiveFeedViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val localFaces by viewModel.localFaces.collectAsState()
    val recognitions by viewModel.recognitions.collectAsState()
    val wsConnected by viewModel.wsConnected.collectAsState()

    LaunchedEffect(scheduleId, roomId) {
        viewModel.initialize(scheduleId, roomId)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Header with subject name and connection indicator
        IAMSHeader(
            title = uiState.schedule?.subjectName ?: "Live Feed",
            onBack = { navController.popBackStack() },
            trailing = {
                // Connection status indicator
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(if (wsConnected) PresentFg else AbsentFg)
                )
            }
        )

        if (uiState.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = Primary)
            }
        } else if (uiState.error != null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = uiState.error!!,
                    color = MaterialTheme.colorScheme.error,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(32.dp)
                )
            }
        } else {
            // Video feed area (~55% of remaining space)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(0.55f)
                    .background(Color.Black)
            ) {
                if (uiState.rtspUrl.isNotEmpty()) {
                    var textureViewRef by remember { mutableStateOf<TextureView?>(null) }

                    RtspVideoPlayer(
                        rtspUrl = uiState.rtspUrl,
                        modifier = Modifier.fillMaxSize(),
                        onTextureViewReady = { textureView ->
                            textureViewRef = textureView
                            // Hook up ML Kit face detection via SurfaceTexture listener
                            textureView.surfaceTextureListener =
                                object : TextureView.SurfaceTextureListener {
                                    override fun onSurfaceTextureAvailable(
                                        surface: SurfaceTexture,
                                        width: Int,
                                        height: Int
                                    ) {}

                                    override fun onSurfaceTextureSizeChanged(
                                        surface: SurfaceTexture,
                                        width: Int,
                                        height: Int
                                    ) {}

                                    override fun onSurfaceTextureDestroyed(
                                        surface: SurfaceTexture
                                    ): Boolean = true

                                    override fun onSurfaceTextureUpdated(
                                        surface: SurfaceTexture
                                    ) {
                                        // Process every frame through ML Kit
                                        viewModel.faceProcessor.processFrame(textureView)
                                    }
                                }
                        },
                        onError = { /* Could show error toast */ }
                    )

                    // ML Kit face overlay on top of video
                    FaceOverlay(
                        localFaces = localFaces,
                        recognitions = recognitions,
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    // No RTSP URL available
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "No camera stream configured\nfor this room",
                            color = Color.White.copy(alpha = 0.7f),
                            textAlign = TextAlign.Center,
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                }
            }

            // Attendance panel (~45% of remaining space)
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(0.45f)
                    .background(Background)
            ) {
                // Attendance header card
                AttendanceHeader(
                    presentCount = uiState.presentCount,
                    totalEnrolled = uiState.totalEnrolled
                )

                HorizontalDivider(color = Border, thickness = 1.dp)

                // Attendance list
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    // Present students
                    if (uiState.presentStudents.isNotEmpty()) {
                        item {
                            Spacer(modifier = Modifier.height(8.dp))
                            AttendanceSectionLabel("Present", PresentFg)
                        }
                        items(uiState.presentStudents) { student ->
                            StudentAttendanceRow(
                                student = student,
                                icon = { StatusIcon(Icons.Default.Check, PresentFg) }
                            )
                        }
                    }

                    // Late students
                    if (uiState.lateStudents.isNotEmpty()) {
                        item {
                            Spacer(modifier = Modifier.height(8.dp))
                            AttendanceSectionLabel("Late", LateFg)
                        }
                        items(uiState.lateStudents) { student ->
                            StudentAttendanceRow(
                                student = student,
                                icon = { StatusIcon(Icons.Default.Warning, LateFg) }
                            )
                        }
                    }

                    // Early leave students
                    if (uiState.earlyLeaveStudents.isNotEmpty()) {
                        item {
                            Spacer(modifier = Modifier.height(8.dp))
                            AttendanceSectionLabel("Early Leave", EarlyLeaveFg)
                        }
                        items(uiState.earlyLeaveStudents) { student ->
                            StudentAttendanceRow(
                                student = student,
                                icon = { StatusIcon(Icons.Default.Warning, EarlyLeaveFg) }
                            )
                        }
                    }

                    // Absent students
                    if (uiState.absentStudents.isNotEmpty()) {
                        item {
                            Spacer(modifier = Modifier.height(8.dp))
                            AttendanceSectionLabel("Absent", AbsentFg)
                        }
                        items(uiState.absentStudents) { student ->
                            StudentAttendanceRow(
                                student = student,
                                icon = { StatusIcon(Icons.Default.Close, AbsentFg) }
                            )
                        }
                    }

                    // Empty state
                    if (uiState.presentStudents.isEmpty() &&
                        uiState.absentStudents.isEmpty() &&
                        uiState.lateStudents.isEmpty() &&
                        uiState.earlyLeaveStudents.isEmpty()
                    ) {
                        item {
                            Text(
                                text = "No attendance data yet.\nWaiting for scan results...",
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextSecondary,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(32.dp)
                            )
                        }
                    }

                    item {
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun AttendanceHeader(presentCount: Int, totalEnrolled: Int) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        IAMSCard {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Attendance",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary
                )
                Text(
                    text = "Present: $presentCount / $totalEnrolled",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = PresentFg
                )
            }
        }
    }
}

@Composable
private fun AttendanceSectionLabel(label: String, color: Color) {
    Text(
        text = label,
        style = MaterialTheme.typography.labelMedium,
        fontWeight = FontWeight.SemiBold,
        color = color,
        modifier = Modifier.padding(vertical = 4.dp)
    )
}

@Composable
private fun StatusIcon(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    tint: Color
) {
    Icon(
        imageVector = icon,
        contentDescription = null,
        tint = tint,
        modifier = Modifier.size(18.dp)
    )
}

@Composable
private fun StudentAttendanceRow(
    student: StudentAttendanceStatus,
    icon: @Composable () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        icon()
        Spacer(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = student.studentName,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = Primary
            )
        }
        if (student.checkInTime != null) {
            Text(
                text = student.checkInTime,
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
                fontSize = 11.sp
            )
        }
    }
}
