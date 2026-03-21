package com.iams.app.ui.common

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.NotificationPreferenceResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val prefs: NotificationPreferenceResponse? = null,
    val updatingKey: String? = null,
    val isFaculty: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        _uiState.value = _uiState.value.copy(
            isFaculty = tokenManager.userRole == "faculty"
        )
        loadPreferences()
    }

    fun loadPreferences() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val response = apiService.getNotificationPreferences()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        prefs = response.body()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false)
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true)
            loadPreferences()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun togglePreference(key: String, value: Boolean) {
        val currentPrefs = _uiState.value.prefs ?: return
        val previous = getPreferenceValue(currentPrefs, key)

        // Optimistic update
        val updatedPrefs = updatePreferenceLocally(currentPrefs, key, value)
        _uiState.value = _uiState.value.copy(prefs = updatedPrefs, updatingKey = key)

        viewModelScope.launch {
            try {
                val request = buildUpdateRequest(key, value)
                val response = apiService.updateNotificationPreferences(request)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        prefs = response.body() ?: updatedPrefs,
                        updatingKey = null
                    )
                } else {
                    // Revert on failure
                    val reverted = updatePreferenceLocally(currentPrefs, key, previous)
                    _uiState.value = _uiState.value.copy(prefs = reverted, updatingKey = null)
                }
            } catch (_: Exception) {
                // Revert on failure
                val reverted = updatePreferenceLocally(currentPrefs, key, previous)
                _uiState.value = _uiState.value.copy(prefs = reverted, updatingKey = null)
            }
        }
    }

    private fun getPreferenceValue(prefs: NotificationPreferenceResponse, key: String): Boolean {
        return when (key) {
            "attendance_confirmation" -> prefs.attendanceConfirmation
            "early_leave_alerts" -> prefs.earlyLeaveAlerts
            "anomaly_alerts" -> prefs.anomalyAlerts
            "low_attendance_warning" -> prefs.lowAttendanceWarning
            "daily_digest" -> prefs.dailyDigest
            "weekly_digest" -> prefs.weeklyDigest
            "email_enabled" -> prefs.emailEnabled
            else -> false
        }
    }

    private fun updatePreferenceLocally(
        prefs: NotificationPreferenceResponse,
        key: String,
        value: Boolean
    ): NotificationPreferenceResponse {
        return when (key) {
            "attendance_confirmation" -> prefs.copy(attendanceConfirmation = value)
            "early_leave_alerts" -> prefs.copy(earlyLeaveAlerts = value)
            "anomaly_alerts" -> prefs.copy(anomalyAlerts = value)
            "low_attendance_warning" -> prefs.copy(lowAttendanceWarning = value)
            "daily_digest" -> prefs.copy(dailyDigest = value)
            "weekly_digest" -> prefs.copy(weeklyDigest = value)
            "email_enabled" -> prefs.copy(emailEnabled = value)
            else -> prefs
        }
    }

    private fun buildUpdateRequest(
        key: String,
        value: Boolean
    ): com.iams.app.data.model.NotificationPreferenceUpdateRequest {
        return when (key) {
            "attendance_confirmation" -> com.iams.app.data.model.NotificationPreferenceUpdateRequest(attendanceConfirmation = value)
            "early_leave_alerts" -> com.iams.app.data.model.NotificationPreferenceUpdateRequest(earlyLeaveAlerts = value)
            "anomaly_alerts" -> com.iams.app.data.model.NotificationPreferenceUpdateRequest(anomalyAlerts = value)
            "low_attendance_warning" -> com.iams.app.data.model.NotificationPreferenceUpdateRequest(lowAttendanceWarning = value)
            "daily_digest" -> com.iams.app.data.model.NotificationPreferenceUpdateRequest(dailyDigest = value)
            "weekly_digest" -> com.iams.app.data.model.NotificationPreferenceUpdateRequest(weeklyDigest = value)
            "email_enabled" -> com.iams.app.data.model.NotificationPreferenceUpdateRequest(emailEnabled = value)
            else -> com.iams.app.data.model.NotificationPreferenceUpdateRequest()
        }
    }
}
