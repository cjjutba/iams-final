package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.AnomalyItem
import com.iams.app.data.model.AtRiskStudent
import com.iams.app.data.model.ClassOverview
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FacultyAnalyticsDashboardUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val classOverviews: List<ClassOverview> = emptyList(),
    val atRiskStudents: List<AtRiskStudent> = emptyList(),
    val anomalies: List<AnomalyItem> = emptyList(),
) {
    val unresolvedAnomalyCount: Int
        get() = anomalies.count { !it.resolved }

    val atRiskCount: Int
        get() = atRiskStudents.size

    val highRiskCount: Int
        get() = atRiskStudents.count {
            it.riskLevel == "critical" || it.riskLevel == "high"
        }
}

@HiltViewModel
class FacultyAnalyticsDashboardViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyAnalyticsDashboardUiState())
    val uiState: StateFlow<FacultyAnalyticsDashboardUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                // Fetch schedules first
                val schedulesResponse = apiService.getMySchedules()
                val schedules = if (schedulesResponse.isSuccessful) {
                    schedulesResponse.body() ?: emptyList()
                } else {
                    emptyList()
                }

                // Fetch at-risk students and anomalies in parallel
                val atRiskDeferred = async {
                    try {
                        val response = apiService.getAtRiskStudents()
                        if (response.isSuccessful) response.body() ?: emptyList()
                        else emptyList()
                    } catch (_: Exception) {
                        emptyList()
                    }
                }

                val anomaliesDeferred = async {
                    try {
                        val response = apiService.getAnomalies()
                        if (response.isSuccessful) {
                            (response.body() ?: emptyList()).filter { !it.resolved }
                        } else {
                            emptyList()
                        }
                    } catch (_: Exception) {
                        emptyList()
                    }
                }

                // Fetch class overviews for each schedule
                val overviews = schedules.mapNotNull { schedule ->
                    try {
                        val response = apiService.getClassOverview(schedule.id)
                        if (response.isSuccessful) response.body() else null
                    } catch (_: Exception) {
                        null
                    }
                }

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    classOverviews = overviews,
                    atRiskStudents = atRiskDeferred.await(),
                    anomalies = anomaliesDeferred.await(),
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load analytics data."
                )
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true)
            loadData()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }
}
