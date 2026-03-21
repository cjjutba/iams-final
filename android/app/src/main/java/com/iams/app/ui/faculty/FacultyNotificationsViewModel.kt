package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.NotificationResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FacultyNotificationsUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val notifications: List<NotificationResponse> = emptyList(),
    val markingReadIds: Set<String> = emptySet(),
)

@HiltViewModel
class FacultyNotificationsViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyNotificationsUiState())
    val uiState: StateFlow<FacultyNotificationsUiState> = _uiState.asStateFlow()

    init {
        loadNotifications()
    }

    fun loadNotifications(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            }
            try {
                val response = apiService.getNotifications()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        notifications = response.body() ?: emptyList(),
                        isLoading = false,
                        isRefreshing = false,
                        error = null,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load notifications",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Unable to load notifications. Please try again.",
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadNotifications(silent = true)
    }

    fun markAsRead(notificationId: String) {
        // Optimistic update
        _uiState.value = _uiState.value.copy(
            markingReadIds = _uiState.value.markingReadIds + notificationId,
            notifications = _uiState.value.notifications.map { n ->
                if (n.id == notificationId) n.copy(read = true) else n
            }
        )

        viewModelScope.launch {
            try {
                val response = apiService.markNotificationRead(notificationId)
                if (!response.isSuccessful) {
                    // Revert on failure
                    _uiState.value = _uiState.value.copy(
                        notifications = _uiState.value.notifications.map { n ->
                            if (n.id == notificationId) n.copy(read = false) else n
                        }
                    )
                }
            } catch (_: Exception) {
                // Revert on failure
                _uiState.value = _uiState.value.copy(
                    notifications = _uiState.value.notifications.map { n ->
                        if (n.id == notificationId) n.copy(read = false) else n
                    }
                )
            } finally {
                _uiState.value = _uiState.value.copy(
                    markingReadIds = _uiState.value.markingReadIds - notificationId
                )
            }
        }
    }
}
