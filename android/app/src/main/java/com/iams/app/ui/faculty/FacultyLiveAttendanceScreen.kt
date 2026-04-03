package com.iams.app.ui.faculty

import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.EarlyLeaveBg
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.InputBackground
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyLiveAttendanceScreen(
    navController: NavController,
    scheduleId: String,
    viewModel: FacultyLiveAttendanceViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    var showEndSessionDialog by remember { mutableStateOf(false) }

    LaunchedEffect(scheduleId) {
        viewModel.initialize(scheduleId)
    }

    // End session confirmation dialog
    if (showEndSessionDialog) {
        AlertDialog(
            onDismissRequest = { showEndSessionDialog = false },
            title = { Text("End Session") },
            text = {
                Text("Are you sure you want to end this attendance session? This action cannot be undone.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showEndSessionDialog = false
                        viewModel.endSession(
                            onSuccess = { /* Session ended */ },
                            onError = { /* Error handled in VM */ }
                        )
                    }
                ) {
                    Text("End Session", color = AbsentFg)
                }
            },
            dismissButton = {
                TextButton(onClick = { showEndSessionDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Header
        IAMSHeader(
            title = "Live Attendance",
            onBack = { navController.popBackStack() },
            trailing = {
                Row {
                    IconButton(
                        onClick = {
                            navController.navigate(
                                Routes.facultyLiveFeed(scheduleId, uiState.roomId)
                            )
                        },
                        modifier = Modifier.size(40.dp)
                    ) {
                        Icon(
                            Icons.Default.CameraAlt,
                            contentDescription = "View Camera Feed",
                            tint = Primary,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    IconButton(
                        onClick = {
                            navController.navigate(Routes.facultyManualEntry(scheduleId))
                        },
                        modifier = Modifier.size(40.dp)
                    ) {
                        Icon(
                            Icons.Default.Edit,
                            contentDescription = "Manual Entry",
                            tint = Primary,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                }
            }
        )

        when {
            // Error state
            uiState.error != null && uiState.liveAttendance == null -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.padding(horizontal = spacing.xxl)
                    ) {
                        Text(
                            text = uiState.error!!,
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextSecondary,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(spacing.lg))
                        IAMSButton(
                            text = "Retry",
                            onClick = { viewModel.loadData() },
                            variant = IAMSButtonVariant.SECONDARY,
                            fullWidth = false
                        )
                    }
                }
            }

            // Loading state
            uiState.isLoading && uiState.liveAttendance == null -> {
                Column(modifier = Modifier.fillMaxSize()) {
                    // Connection bar skeleton
                    SkeletonBox(height = 24.dp, cornerRadius = 0.dp)
                    // Stats row skeleton (4 cards)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = spacing.screenPadding, vertical = spacing.lg),
                        horizontalArrangement = Arrangement.spacedBy(spacing.sm)
                    ) {
                        repeat(4) {
                            IAMSCard(modifier = Modifier.weight(1f)) {
                                Column(
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = spacing.md)
                                ) {
                                    SkeletonBox(width = 32.dp, height = 28.dp, cornerRadius = 4.dp)
                                    Spacer(modifier = Modifier.height(spacing.xs))
                                    SkeletonBox(width = 40.dp, height = 10.dp)
                                }
                            }
                        }
                    }
                    // Search bar skeleton
                    SkeletonBox(
                        height = 44.dp,
                        cornerRadius = 12.dp,
                        modifier = Modifier
                            .padding(horizontal = spacing.screenPadding)
                            .padding(bottom = spacing.lg)
                    )
                    // Student card skeletons
                    repeat(4) {
                        IAMSCard(
                            modifier = Modifier
                                .padding(horizontal = spacing.screenPadding)
                                .padding(bottom = spacing.sm)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                SkeletonBox(width = 40.dp, height = 40.dp, cornerRadius = 20.dp)
                                Spacer(modifier = Modifier.width(spacing.md))
                                Column(modifier = Modifier.weight(1f)) {
                                    SkeletonBox(width = 140.dp, height = 14.dp)
                                    Spacer(modifier = Modifier.height(4.dp))
                                    SkeletonBox(width = 100.dp, height = 12.dp)
                                    Spacer(modifier = Modifier.height(2.dp))
                                    SkeletonBox(width = 80.dp, height = 10.dp)
                                }
                                Spacer(modifier = Modifier.width(spacing.md))
                                SkeletonBox(width = 56.dp, height = 22.dp, cornerRadius = 12.dp)
                            }
                        }
                    }
                }
            }

            // Main content
            else -> {
                Box(modifier = Modifier.fillMaxSize()) {
                    PullToRefreshBox(
                        isRefreshing = uiState.isRefreshing,
                        onRefresh = { viewModel.refresh() },
                        modifier = Modifier.fillMaxSize()
                    ) {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(
                                bottom = if (uiState.isSessionActive) 80.dp else spacing.xxl
                            )
                        ) {
                            // Connection status bar
                            item {
                                ConnectionStatusBar(isConnected = uiState.isConnected)
                            }

                            // Session active indicator
                            if (uiState.isSessionActive) {
                                item {
                                    SessionActiveBar()
                                }
                            }

                            // Stats row
                            item {
                                StatsRow(
                                    presentCount = uiState.presentCount,
                                    lateCount = uiState.lateCount,
                                    absentCount = uiState.absentCount,
                                    earlyLeaveCount = uiState.earlyLeaveCount
                                )
                            }

                            // Search bar
                            item {
                                SearchBar(
                                    query = uiState.searchQuery,
                                    onQueryChange = { viewModel.updateSearchQuery(it) }
                                )
                            }

                            // Students list
                            val students = uiState.filteredStudents
                            if (students.isEmpty()) {
                                item {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 48.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = if (uiState.searchQuery.isNotBlank())
                                                "No students match your search"
                                            else
                                                "No students enrolled",
                                            style = MaterialTheme.typography.bodyLarge,
                                            color = TextSecondary,
                                            textAlign = TextAlign.Center
                                        )
                                    }
                                }
                            } else {
                                items(
                                    items = students,
                                    key = { it.studentId }
                                ) { student ->
                                    StudentAttendanceCard(
                                        student = student,
                                        onClick = {
                                            navController.navigate(
                                                Routes.facultyStudentDetail(
                                                    student.studentId,
                                                    scheduleId
                                                )
                                            )
                                        }
                                    )
                                }
                            }
                        }
                    }

                    // End Session fixed bar at bottom
                    if (uiState.isSessionActive) {
                        EndSessionBar(
                            isEnding = uiState.isEndingSession,
                            onEndSession = { showEndSessionDialog = true },
                            modifier = Modifier.align(Alignment.BottomCenter)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ConnectionStatusBar(isConnected: Boolean) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Secondary)
            .padding(vertical = spacing.xs),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = if (isConnected) Icons.Default.Wifi else Icons.Default.WifiOff,
            contentDescription = if (isConnected) "Connected" else "Disconnected",
            modifier = Modifier.size(14.dp),
            tint = if (isConnected) PresentFg else AbsentFg
        )
        Spacer(modifier = Modifier.width(spacing.xs))
        Text(
            text = if (isConnected) "Live" else "Reconnecting...",
            style = MaterialTheme.typography.labelSmall,
            color = if (isConnected) PresentFg else AbsentFg
        )
    }
}

@Composable
private fun SessionActiveBar() {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(PresentFg)
            .padding(vertical = spacing.sm),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(Color.White)
        )
        Spacer(modifier = Modifier.width(spacing.sm))
        Text(
            text = "Session Active",
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            color = Color.White
        )
    }
}

@Composable
private fun StatsRow(
    presentCount: Int,
    lateCount: Int,
    absentCount: Int,
    earlyLeaveCount: Int
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = spacing.screenPadding, vertical = spacing.lg),
        horizontalArrangement = Arrangement.spacedBy(spacing.sm)
    ) {
        StatCard(
            label = "Present",
            value = presentCount,
            color = PresentFg,
            modifier = Modifier.weight(1f)
        )
        StatCard(
            label = "Late",
            value = lateCount,
            color = LateFg,
            modifier = Modifier.weight(1f)
        )
        StatCard(
            label = "Absent",
            value = absentCount,
            color = AbsentFg,
            modifier = Modifier.weight(1f)
        )
        StatCard(
            label = "Left",
            value = earlyLeaveCount,
            color = EarlyLeaveFg,
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
private fun StatCard(
    label: String,
    value: Int,
    color: Color,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(modifier = modifier) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = spacing.md)
        ) {
            Text(
                text = "$value",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = color
            )
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = TextTertiary
            )
        }
    }
}

@Composable
private fun SearchBar(
    query: String,
    onQueryChange: (String) -> Unit
) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = spacing.screenPadding)
            .padding(bottom = spacing.lg)
            .clip(radius.mdShape)
            .background(InputBackground)
            .padding(horizontal = spacing.lg, vertical = spacing.md),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            Icons.Default.Search,
            contentDescription = "Search",
            modifier = Modifier.size(20.dp),
            tint = TextTertiary
        )
        Spacer(modifier = Modifier.width(spacing.sm))
        BasicTextField(
            value = query,
            onValueChange = onQueryChange,
            modifier = Modifier.fillMaxWidth(),
            textStyle = MaterialTheme.typography.bodyLarge.copy(color = Primary),
            singleLine = true,
            cursorBrush = SolidColor(Primary),
            decorationBox = { innerTextField ->
                Box {
                    if (query.isEmpty()) {
                        Text(
                            text = "Search students...",
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextTertiary
                        )
                    }
                    innerTextField()
                }
            }
        )
    }
}

@Composable
private fun StudentAttendanceCard(
    student: StudentAttendanceStatus,
    onClick: () -> Unit
) {
    val spacing = IAMSThemeTokens.spacing
    val nameParts = student.studentName.split(" ", limit = 2)
    val firstInitial = nameParts.getOrNull(0)?.firstOrNull()?.uppercaseChar() ?: ' '
    val lastInitial = nameParts.getOrNull(1)?.firstOrNull()?.uppercaseChar() ?: ' '

    val statusBgColor = when (student.status) {
        "present" -> PresentBg
        "late" -> LateBg
        "absent" -> AbsentBg
        else -> EarlyLeaveBg
    }
    val statusFgColor = when (student.status) {
        "present" -> PresentFg
        "late" -> LateFg
        "absent" -> AbsentFg
        else -> EarlyLeaveFg
    }
    val statusText = when (student.status) {
        "early_leave" -> "Left"
        else -> student.status.replaceFirstChar { it.uppercaseChar() }
    }

    val isCurrentlyPresent = student.status == "present"

    IAMSCard(
        modifier = Modifier
            .padding(horizontal = spacing.screenPadding)
            .padding(bottom = spacing.sm),
        onClick = onClick
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Avatar
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(Secondary),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "$firstInitial$lastInitial",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary
                )
            }

            Spacer(modifier = Modifier.width(spacing.md))

            // Info
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = student.studentName,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false)
                    )
                    if (isCurrentlyPresent) {
                        Spacer(modifier = Modifier.width(spacing.sm))
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(PresentFg)
                        )
                    }
                }
                Text(
                    text = student.studentNumber ?: student.studentId,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
                student.presenceScore?.let { score ->
                    Text(
                        text = "Presence: ${score.toInt()}%",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextTertiary
                    )
                }
            }

            Spacer(modifier = Modifier.width(spacing.md))

            // Status badge
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(12.dp))
                    .background(statusBgColor)
                    .padding(horizontal = spacing.sm, vertical = spacing.xs),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = statusText,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = statusFgColor
                )
            }
        }
    }
}

@Composable
private fun EndSessionBar(
    isEnding: Boolean,
    onEndSession: () -> Unit,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(Background)
            .padding(horizontal = spacing.screenPadding, vertical = spacing.md)
    ) {
        IAMSButton(
            text = "End Session",
            onClick = onEndSession,
            enabled = !isEnding,
            isLoading = isEnding,
            loadingText = "Ending Session...",
            variant = IAMSButtonVariant.PRIMARY,
            leadingIcon = {
                if (!isEnding) {
                    Icon(
                        Icons.Default.Stop,
                        contentDescription = "End Session",
                        modifier = Modifier.size(18.dp),
                        tint = Color.White
                    )
                }
            }
        )
    }
}
