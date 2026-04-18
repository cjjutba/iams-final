package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.model.NotificationResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FacultyNotificationsUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val notifications: List<NotificationResponse> = emptyList(),
    val markingReadIds: Set<String> = emptySet(),
    val deletingIds: Set<String> = emptySet(),
    val isMarkingAllRead: Boolean = false,
    val isDeletingAll: Boolean = false,
)

@HiltViewModel
class FacultyNotificationsViewModel @Inject constructor(
    private val apiService: ApiService,
    private val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyNotificationsUiState())
    val uiState: StateFlow<FacultyNotificationsUiState> = _uiState.asStateFlow()

    private var wsJob: Job? = null

    val unreadCount: Int
        get() = _uiState.value.notifications.count { !it.read }

    val hasUnread: Boolean
        get() = _uiState.value.notifications.any { !it.read }

    init {
        loadNotifications()
        subscribeToLiveEvents()
    }

    /**
     * Listen for real-time notification events on the shared WebSocket and
     * silently re-fetch the list so the new row (with its real DB id +
     * created_at) shows up at the top without a manual refresh.
     *
     * SharedFlow has no replay, so re-collecting on every init is safe.
     */
    private fun subscribeToLiveEvents() {
        val events = notificationService.events ?: return
        wsJob?.cancel()
        wsJob = viewModelScope.launch {
            events.collectLatest {
                loadNotifications(silent = true)
            }
        }
    }

    override fun onCleared() {
        wsJob?.cancel()
        super.onCleared()
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
                        notifications = response.body() ?: emptyList(),
                        isLoading = false,
                        isRefreshing = false,
                        error = null,
                    )
                    // Reconcile centralized unread count with REST API
                    notificationService.fetchUnreadCount(apiService)
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
        val notification = _uiState.value.notifications.find { it.id == notificationId }
        if (notification == null || notification.read) return

        _uiState.value = _uiState.value.copy(
            markingReadIds = _uiState.value.markingReadIds + notificationId,
            notifications = _uiState.value.notifications.map { n ->
                if (n.id == notificationId) n.copy(read = true) else n
            }
        )

        viewModelScope.launch {
            try {
                val response = apiService.markNotificationRead(notificationId)
                if (response.isSuccessful) {
                    notificationService.decrementUnreadCount()
                } else {
                    // Revert optimistic update
                    _uiState.value = _uiState.value.copy(
                        notifications = _uiState.value.notifications.map { n ->
                            if (n.id == notificationId) n.copy(read = false) else n
                        }
                    )
                }
            } catch (_: Exception) {
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

    fun markAllAsRead() {
        if (!hasUnread) return
        _uiState.value = _uiState.value.copy(
            isMarkingAllRead = true,
            notifications = _uiState.value.notifications.map { it.copy(read = true) }
        )

        viewModelScope.launch {
            try {
                val response = apiService.markAllNotificationsRead()
                if (response.isSuccessful) {
                    notificationService.setUnreadCount(0)
                } else {
                    loadNotifications(silent = true)
                }
            } catch (_: Exception) {
                loadNotifications(silent = true)
            } finally {
                _uiState.value = _uiState.value.copy(isMarkingAllRead = false)
            }
        }
    }

    fun deleteNotification(notificationId: String) {
        val removed = _uiState.value.notifications.find { it.id == notificationId } ?: return
        val wasUnread = !removed.read
        _uiState.value = _uiState.value.copy(
            deletingIds = _uiState.value.deletingIds + notificationId,
            notifications = _uiState.value.notifications.filter { it.id != notificationId }
        )

        viewModelScope.launch {
            try {
                val response = apiService.deleteNotification(notificationId)
                if (response.isSuccessful) {
                    if (wasUnread) notificationService.decrementUnreadCount()
                } else {
                    _uiState.value = _uiState.value.copy(
                        notifications = (_uiState.value.notifications + removed)
                            .sortedByDescending { it.createdAt }
                    )
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(
                    notifications = (_uiState.value.notifications + removed)
                        .sortedByDescending { it.createdAt }
                )
            } finally {
                _uiState.value = _uiState.value.copy(
                    deletingIds = _uiState.value.deletingIds - notificationId
                )
            }
        }
    }

    fun deleteAllNotifications() {
        if (_uiState.value.notifications.isEmpty()) return
        val backup = _uiState.value.notifications
        _uiState.value = _uiState.value.copy(
            isDeletingAll = true,
            notifications = emptyList()
        )

        viewModelScope.launch {
            try {
                val response = apiService.deleteAllNotifications()
                if (response.isSuccessful) {
                    notificationService.setUnreadCount(0)
                } else {
                    _uiState.value = _uiState.value.copy(notifications = backup)
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(notifications = backup)
            } finally {
                _uiState.value = _uiState.value.copy(isDeletingAll = false)
            }
        }
    }
}
