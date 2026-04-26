package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.model.StudentAnalyticsDashboard
import com.iams.app.data.model.StudentAttendanceEvent
import com.iams.app.data.model.SubjectBreakdown
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class StudentAnalyticsUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val dashboard: StudentAnalyticsDashboard? = null,
    val subjects: List<SubjectBreakdown> = emptyList(),
)

@HiltViewModel
class StudentAnalyticsViewModel @Inject constructor(
    private val apiService: ApiService,
    private val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentAnalyticsUiState())
    val uiState: StateFlow<StudentAnalyticsUiState> = _uiState.asStateFlow()

    init {
        loadAnalytics()
        observeRealtimeEvents()
    }

    /**
     * Analytics is aggregation, so a single state change is best served
     * by a silent refetch rather than trying to re-derive the aggregates
     * locally. Endpoints are cheap (two small JSON payloads) and events
     * are rare (once per class session per day).
     */
    private fun observeRealtimeEvents() {
        viewModelScope.launch {
            notificationService.attendanceEvents.collect { event ->
                if (event is StudentAttendanceEvent.CheckIn ||
                    event is StudentAttendanceEvent.EarlyLeave ||
                    event is StudentAttendanceEvent.EarlyLeaveReturn
                ) {
                    loadAnalytics(silent = true)
                }
            }
        }
    }

    fun loadAnalytics(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) _uiState.value = _uiState.value.copy(error = null)

            try {
                val dashboardDeferred = async { apiService.getStudentAnalyticsDashboard() }
                val subjectsDeferred = async { apiService.getStudentSubjects() }

                val dashboardResponse = dashboardDeferred.await()
                val subjectsResponse = subjectsDeferred.await()

                if (dashboardResponse.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        dashboard = dashboardResponse.body(),
                        subjects = if (subjectsResponse.isSuccessful) {
                            subjectsResponse.body() ?: emptyList()
                        } else _uiState.value.subjects
                    )
                } else if (!silent) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load dashboard data."
                    )
                }
            } catch (e: Exception) {
                if (!silent) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load analytics data."
                    )
                }
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadAnalytics()
    }
}
