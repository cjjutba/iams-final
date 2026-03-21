package com.iams.app.ui.student

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

data class NotificationsUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val notifications: List<NotificationResponse> = emptyList(),
    val markingReadIds: Set<String> = emptySet(),
)

@HiltViewModel
class StudentNotificationsViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(NotificationsUiState())
    val uiState: StateFlow<NotificationsUiState> = _uiState.asStateFlow()

    init {
        loadNotifications()
    }

    fun loadNotifications(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            } else {
                _uiState.value = _uiState.value.copy(error = null)
            }

            try {
                val response = apiService.getNotifications()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        notifications = response.body() ?: emptyList()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load notifications"
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
        loadNotifications(silent = true)
    }

    fun markAsRead(notificationId: String) {
        // Optimistic update
        _uiState.value = _uiState.value.copy(
            markingReadIds = _uiState.value.markingReadIds + notificationId,
            notifications = _uiState.value.notifications.map {
                if (it.id == notificationId) it.copy(read = true) else it
            }
        )

        viewModelScope.launch {
            try {
                apiService.markNotificationRead(notificationId)
            } catch (e: Exception) {
                // Revert on failure
                _uiState.value = _uiState.value.copy(
                    notifications = _uiState.value.notifications.map {
                        if (it.id == notificationId) it.copy(read = false) else it
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
