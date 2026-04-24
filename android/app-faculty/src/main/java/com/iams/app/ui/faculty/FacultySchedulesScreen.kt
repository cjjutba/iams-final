package com.iams.app.ui.faculty

import androidx.compose.foundation.BorderStroke
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
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material.icons.outlined.EventBusy
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.UserResponse
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.navigation.FacultyRoutes
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.PresentBorder
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.Duration
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.Calendar
import java.util.Locale
import javax.inject.Inject

/**
 * Faculty home — mirrors the Student home layout so the two apps feel
 * consistent, but sized for a pure-viewer flow:
 *
 *  • Greeting header with faculty's first name + today's date
 *  • ACTIVE SESSION hero card (outlined green) for any class in progress
 *  • UPCOMING section for classes later today
 *  • COMPLETED section for classes already finished
 *
 * Each section has a "View Live Camera Feed" CTA. The active session's
 * CTA is filled (primary); upcoming/completed CTAs are secondary.
 */

enum class ScheduleTimeState { COMPLETED, ACTIVE, UPCOMING }

data class FacultySchedulesUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val schedulesToday: List<ScheduleResponse> = emptyList(),
)

@HiltViewModel
class FacultySchedulesViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultySchedulesUiState())
    val uiState: StateFlow<FacultySchedulesUiState> = _uiState.asStateFlow()

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val userDeferred = async {
                    runCatching { apiService.getMe().body() }.getOrNull()
                }
                val schedulesDeferred = async {
                    runCatching { apiService.getMySchedules().body() ?: emptyList() }
                        .getOrDefault(emptyList())
                }

                val user = userDeferred.await()
                val all = schedulesDeferred.await()
                val todayIdx = LocalDate.now().dayOfWeek.value - 1 // Mon=0..Sun=6
                val todays = all
                    .filter { it.isActive && it.dayOfWeekInt == todayIdx }
                    .sortedBy { it.startTime }

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    user = user,
                    schedulesToday = todays,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = e.localizedMessage ?: "Failed to load schedules",
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        load()
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun getGreeting(): String {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return when {
            hour < 12 -> "Good morning"
            hour < 18 -> "Good afternoon"
            else -> "Good evening"
        }
    }

    fun getScheduleTimeState(schedule: ScheduleResponse): ScheduleTimeState {
        val now = LocalTime.now()
        val start = parseTime(schedule.startTime) ?: return ScheduleTimeState.UPCOMING
        val end = parseTime(schedule.endTime) ?: return ScheduleTimeState.UPCOMING
        return when {
            now.isAfter(end) -> ScheduleTimeState.COMPLETED
            now.isBefore(start) -> ScheduleTimeState.UPCOMING
            else -> ScheduleTimeState.ACTIVE
        }
    }

    fun getMinutesUntilStart(schedule: ScheduleResponse): Long {
        val start = parseTime(schedule.startTime) ?: return 0
        return Duration.between(LocalTime.now(), start).toMinutes().coerceAtLeast(0)
    }

    fun formatTime(timeStr: String): String {
        val time = parseTime(timeStr) ?: return timeStr
        val hours = time.hour
        val minutes = time.minute
        val period = if (hours >= 12) "PM" else "AM"
        val displayHours = if (hours % 12 == 0) 12 else hours % 12
        return "$displayHours:${minutes.toString().padStart(2, '0')} $period"
    }

    private fun parseTime(time: String): LocalTime? {
        return runCatching { LocalTime.parse(time) }.getOrNull()
            ?: runCatching {
                val parts = time.split(":")
                LocalTime.of(parts[0].toInt(), parts[1].toInt())
            }.getOrNull()
    }

    fun logout() {
        viewModelScope.launch {
            runCatching { apiService.logout() }
            tokenManager.clearTokens()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultySchedulesScreen(
    navController: NavController,
    viewModel: FacultySchedulesViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    LaunchedEffect(Unit) { viewModel.load() }

    // Error state with no cached data
    if (uiState.error != null && uiState.schedulesToday.isEmpty() && !uiState.isLoading) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Background)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = spacing.xxl),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(40.dp),
                        tint = TextTertiary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    Text(
                        text = "Unable to load your schedule. Please try again.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    IAMSButton(
                        text = "Retry",
                        onClick = {
                            viewModel.clearError()
                            viewModel.load()
                        },
                        variant = IAMSButtonVariant.SECONDARY,
                        size = IAMSButtonSize.MD,
                        fullWidth = false
                    )
                }
            }
        }
        return
    }

    val schedules = uiState.schedulesToday
    val activeSession = schedules.firstOrNull {
        viewModel.getScheduleTimeState(it) == ScheduleTimeState.ACTIVE
    }
    val otherSchedules = schedules.filter { it.id != activeSession?.id }
    val upcoming = otherSchedules
        .filter { viewModel.getScheduleTimeState(it) == ScheduleTimeState.UPCOMING }
        .sortedBy { it.startTime }
    val completed = otherSchedules
        .filter { viewModel.getScheduleTimeState(it) == ScheduleTimeState.COMPLETED }
        .sortedByDescending { it.startTime }

    PullToRefreshBox(
        isRefreshing = uiState.isRefreshing,
        onRefresh = { viewModel.refresh() },
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = spacing.lg),
        ) {
            // ── Header row: greeting + logout ──
            item {
                Spacer(modifier = Modifier.height(spacing.lg))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    val firstName = uiState.user?.firstName?.takeIf { it.isNotBlank() } ?: "Faculty"
                    Text(
                        text = "${viewModel.getGreeting()}, $firstName!",
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold,
                        color = Primary,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(onClick = {
                        viewModel.logout()
                        navController.navigate(FacultyRoutes.WELCOME) {
                            popUpTo(FacultyRoutes.SCHEDULES) { inclusive = true }
                        }
                    }) {
                        Icon(
                            Icons.AutoMirrored.Filled.Logout,
                            contentDescription = "Log out",
                            tint = TextSecondary
                        )
                    }
                }

                Spacer(modifier = Modifier.height(spacing.sm))

                Text(
                    text = LocalDate.now().format(
                        DateTimeFormatter.ofPattern("EEEE, MMMM d, yyyy", Locale.getDefault())
                    ),
                    style = MaterialTheme.typography.bodyLarge,
                    color = TextSecondary
                )
            }

            // ── Loading state ──
            if (uiState.isLoading) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxxl))
                    Box(
                        modifier = Modifier.fillMaxWidth(),
                        contentAlignment = Alignment.Center,
                    ) { CircularProgressIndicator() }
                }
            }

            // ── Active Session hero card ──
            if (!uiState.isLoading && activeSession != null) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    ActiveSessionCard(
                        schedule = activeSession,
                        formatTime = { viewModel.formatTime(it) },
                        onWatchLive = {
                            val roomId = activeSession.roomId
                            if (!roomId.isNullOrBlank()) {
                                navController.navigate(
                                    FacultyRoutes.liveFeed(activeSession.id, roomId)
                                )
                            }
                        }
                    )
                }
            }

            // ── Empty state ──
            if (!uiState.isLoading && schedules.isEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxxl))
                    EmptySchedulesState()
                }
            }

            // ── Upcoming section ──
            if (!uiState.isLoading && upcoming.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Upcoming (${upcoming.size})",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Primary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }
                items(upcoming, key = { "upcoming-${it.id}" }) { schedule ->
                    ScheduleCard(
                        schedule = schedule,
                        timeState = ScheduleTimeState.UPCOMING,
                        minutesUntilStart = viewModel.getMinutesUntilStart(schedule),
                        formatTime = { viewModel.formatTime(it) },
                        onWatchLive = {
                            val roomId = schedule.roomId
                            if (!roomId.isNullOrBlank()) {
                                navController.navigate(
                                    FacultyRoutes.liveFeed(schedule.id, roomId)
                                )
                            }
                        }
                    )
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // ── Completed section ──
            if (!uiState.isLoading && completed.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Completed (${completed.size})",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Primary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }
                items(completed, key = { "completed-${it.id}" }) { schedule ->
                    ScheduleCard(
                        schedule = schedule,
                        timeState = ScheduleTimeState.COMPLETED,
                        minutesUntilStart = 0,
                        formatTime = { viewModel.formatTime(it) },
                        onWatchLive = {
                            val roomId = schedule.roomId
                            if (!roomId.isNullOrBlank()) {
                                navController.navigate(
                                    FacultyRoutes.liveFeed(schedule.id, roomId)
                                )
                            }
                        }
                    )
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // Bottom spacing
            item {
                Spacer(modifier = Modifier.height(spacing.xxl))
            }
        }
    }
}

// ── Active Session hero card ──
@Composable
private fun ActiveSessionCard(
    schedule: ScheduleResponse,
    formatTime: (String) -> String,
    onWatchLive: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius
    val canWatch = !schedule.roomId.isNullOrBlank()

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = radius.cardShape,
        color = Background,
        border = BorderStroke(1.5.dp, PresentBorder),
        shadowElevation = 0.dp,
    ) {
        Column(modifier = Modifier.padding(spacing.cardPadding)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(PresentFg)
                )
                Spacer(modifier = Modifier.width(spacing.sm))
                Text(
                    text = "ACTIVE SESSION",
                    style = MaterialTheme.typography.bodySmall.copy(letterSpacing = 0.5.sp),
                    fontWeight = FontWeight.SemiBold,
                    color = PresentFg
                )
            }

            Spacer(modifier = Modifier.height(spacing.md))

            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = Primary
            )

            Spacer(modifier = Modifier.height(spacing.xs))

            Text(
                text = buildString {
                    if (!schedule.subjectCode.isNullOrBlank()) {
                        append(schedule.subjectCode)
                        append(" • ")
                    }
                    append(schedule.roomName ?: "No room")
                    append(" • ")
                    append(formatTime(schedule.startTime))
                    append(" - ")
                    append(formatTime(schedule.endTime))
                },
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )

            Spacer(modifier = Modifier.height(spacing.lg))

            IAMSButton(
                text = "View Live Camera Feed",
                onClick = onWatchLive,
                leadingIcon = {
                    Icon(
                        imageVector = Icons.Filled.Videocam,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                },
                variant = IAMSButtonVariant.PRIMARY,
                size = IAMSButtonSize.LG,
                fullWidth = true,
                enabled = canWatch,
            )
        }
    }
}

// ── Schedule card for Upcoming / Completed ──
@Composable
private fun ScheduleCard(
    schedule: ScheduleResponse,
    timeState: ScheduleTimeState,
    minutesUntilStart: Long,
    formatTime: (String) -> String,
    onWatchLive: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing
    val canWatch = !schedule.roomId.isNullOrBlank()

    IAMSCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = schedule.subjectName,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = buildString {
                        if (!schedule.subjectCode.isNullOrBlank()) {
                            append(schedule.subjectCode)
                            append(" • ")
                        }
                        append(schedule.roomName ?: "No room")
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            Text(
                text = when (timeState) {
                    ScheduleTimeState.COMPLETED -> "Completed"
                    ScheduleTimeState.UPCOMING ->
                        if (minutesUntilStart in 1..60) "in $minutesUntilStart min"
                        else "Upcoming"
                    ScheduleTimeState.ACTIVE -> "Now"
                },
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Medium,
                color = when (timeState) {
                    ScheduleTimeState.COMPLETED -> TextTertiary
                    ScheduleTimeState.UPCOMING -> TextSecondary
                    ScheduleTimeState.ACTIVE -> PresentFg
                }
            )
        }

        Spacer(modifier = Modifier.height(spacing.md))

        IAMSButton(
            text = "View Live Camera Feed",
            onClick = onWatchLive,
            leadingIcon = {
                Icon(
                    imageVector = Icons.Filled.Videocam,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
            },
            variant = IAMSButtonVariant.SECONDARY,
            size = IAMSButtonSize.MD,
            fullWidth = true,
            enabled = canWatch,
        )
    }
}

// ── Empty state ──
@Composable
private fun EmptySchedulesState() {
    val spacing = IAMSThemeTokens.spacing
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.xxxl),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Outlined.EventBusy,
            contentDescription = null,
            tint = TextTertiary,
            modifier = Modifier.size(48.dp),
        )
        Spacer(modifier = Modifier.height(spacing.md))
        Text(
            text = "No classes today",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = TextPrimary,
        )
        Spacer(modifier = Modifier.height(spacing.xs))
        Text(
            text = "Your schedule is all clear. Check back tomorrow.",
            style = MaterialTheme.typography.bodyMedium,
            color = TextSecondary,
            textAlign = TextAlign.Center,
        )
    }
}
