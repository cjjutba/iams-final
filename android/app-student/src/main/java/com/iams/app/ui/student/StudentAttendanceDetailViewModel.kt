package com.iams.app.ui.student

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.PresenceLogResponse
import com.iams.app.data.model.StudentAttendanceEvent
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AttendanceDetailUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val attendance: AttendanceRecordResponse? = null,
    val logs: List<PresenceLogResponse> = emptyList(),
)

@HiltViewModel
class StudentAttendanceDetailViewModel @Inject constructor(
    private val apiService: ApiService,
    private val notificationService: NotificationService,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val attendanceId: String? = savedStateHandle["attendanceId"]
    private val scheduleId: String? = savedStateHandle["scheduleId"]
    private val date: String? = savedStateHandle["date"]

    private val _uiState = MutableStateFlow(AttendanceDetailUiState())
    val uiState: StateFlow<AttendanceDetailUiState> = _uiState.asStateFlow()

    init {
        loadDetails()
        observeRealtimeEvents()
    }

    /**
     * Merge live attendance events into the currently-open record. If the
     * event refers to the same `attendance_id` we're showing, update
     * `status` and `checkInTime` in place — no refetch.
     *
     * Presence logs arrive on a different pipeline and are flushed to the
     * DB every ~10s; we trigger a silent refetch for those since backend
     * doesn't stream individual log rows.
     */
    private fun observeRealtimeEvents() {
        viewModelScope.launch {
            notificationService.attendanceEvents.collect { event ->
                when (event) {
                    is StudentAttendanceEvent.CheckIn ->
                        applyStatus(event.attendanceId, event.scheduleId, event.status, event.checkInTime)
                    is StudentAttendanceEvent.EarlyLeave ->
                        applyStatus(event.attendanceId, event.scheduleId, "early_leave", null)
                    is StudentAttendanceEvent.EarlyLeaveReturn ->
                        applyStatus(event.attendanceId, event.scheduleId, event.restoredStatus, event.returnedAt)
                    is StudentAttendanceEvent.SnapshotUpdate -> { /* handled via loadDetails on resume */ }
                }
            }
        }
    }

    private fun applyStatus(
        eventAttendanceId: String,
        eventScheduleId: String,
        status: String,
        checkInTime: String?,
    ) {
        val current = _uiState.value.attendance ?: return
        val isSame = current.id == eventAttendanceId ||
            (current.scheduleId == eventScheduleId && current.id == eventAttendanceId)
        if (!isSame) return
        _uiState.value = _uiState.value.copy(
            attendance = current.copy(
                status = status,
                checkInTime = checkInTime ?: current.checkInTime,
            ),
        )
        // Presence logs are server-side timer flushes — a lightweight
        // refetch keeps the timeline fresh without waiting for the user
        // to pull-to-refresh.
        viewModelScope.launch {
            runCatching { apiService.getPresenceLogs(current.id) }
                .onSuccess { resp ->
                    if (resp.isSuccessful) {
                        _uiState.value = _uiState.value.copy(
                            logs = resp.body() ?: _uiState.value.logs,
                        )
                    }
                }
        }
    }

    fun loadDetails(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            } else {
                _uiState.value = _uiState.value.copy(error = null)
            }

            try {
                if (attendanceId != null) {
                    // Fetch by attendance ID
                    val attendanceResponse = apiService.getAttendanceDetail(attendanceId)
                    val logsResponse = apiService.getPresenceLogs(attendanceId)

                    if (attendanceResponse.isSuccessful) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            isRefreshing = false,
                            attendance = attendanceResponse.body(),
                            logs = if (logsResponse.isSuccessful) {
                                logsResponse.body() ?: emptyList()
                            } else emptyList()
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            isRefreshing = false,
                            error = "Failed to load attendance details"
                        )
                    }
                } else if (scheduleId != null) {
                    // Fetch student's own attendance for today, filter by schedule
                    val today = date ?: java.time.LocalDate.now().toString()
                    val response = apiService.getMyAttendance(
                        startDate = today,
                        endDate = today
                    )

                    if (response.isSuccessful) {
                        val records = response.body() ?: emptyList()
                        val matchingRecord = records.find { it.scheduleId == scheduleId }

                        if (matchingRecord != null) {
                            val logsResponse = apiService.getPresenceLogs(matchingRecord.id)
                            _uiState.value = _uiState.value.copy(
                                isLoading = false,
                                isRefreshing = false,
                                attendance = matchingRecord,
                                logs = if (logsResponse.isSuccessful) {
                                    logsResponse.body() ?: emptyList()
                                } else emptyList()
                            )
                        } else {
                            _uiState.value = _uiState.value.copy(
                                isLoading = false,
                                isRefreshing = false,
                                attendance = null,
                                logs = emptyList()
                            )
                        }
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            isRefreshing = false,
                            error = "Failed to load attendance details"
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "No attendance ID or schedule ID provided"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Network error. Please check your connection."
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadDetails(silent = true)
    }

    fun getHeaderDate(): String? = date
}
