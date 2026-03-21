package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.AlertResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class AlertFilter(val value: String, val label: String) {
    TODAY("today", "Today"),
    WEEK("week", "This Week"),
    ALL("all", "All"),
}

data class FacultyAlertsUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val alerts: List<AlertResponse> = emptyList(),
    val selectedFilter: AlertFilter = AlertFilter.TODAY,
)

@HiltViewModel
class FacultyAlertsViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyAlertsUiState())
    val uiState: StateFlow<FacultyAlertsUiState> = _uiState.asStateFlow()

    init {
        loadAlerts()
    }

    fun loadAlerts(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            }
            try {
                val response = apiService.getAlerts(filter = _uiState.value.selectedFilter.value)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        alerts = response.body() ?: emptyList(),
                        isLoading = false,
                        isRefreshing = false,
                        error = null,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load alerts",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Unable to load alerts. Please try again.",
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadAlerts(silent = true)
    }

    fun selectFilter(filter: AlertFilter) {
        if (filter != _uiState.value.selectedFilter) {
            _uiState.value = _uiState.value.copy(selectedFilter = filter)
            loadAlerts()
        }
    }
}
