package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.StudentAnalyticsDashboard
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
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentAnalyticsUiState())
    val uiState: StateFlow<StudentAnalyticsUiState> = _uiState.asStateFlow()

    init {
        loadAnalytics()
    }

    fun loadAnalytics() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(error = null)

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
                        } else emptyList()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load dashboard data."
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Failed to load analytics data."
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadAnalytics()
    }
}
