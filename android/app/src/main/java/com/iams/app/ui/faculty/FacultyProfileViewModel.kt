package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FacultyProfileUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val loggedOut: Boolean = false,
)

@HiltViewModel
class FacultyProfileViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
    val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyProfileUiState())
    val uiState: StateFlow<FacultyProfileUiState> = _uiState.asStateFlow()

    init {
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.getMe()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        user = response.body()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load profile"
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
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        loadProfile()
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun logout() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            // Set flag FIRST so TokenAuthenticator stops refreshing
            tokenManager.isLoggingOut = true
            // Stop the real-time WebSocket *before* clearing tokens — a
            // pending reconnect coroutine reads `userId` / `accessToken`
            // from TokenManager, so clearing tokens first can null-race it.
            notificationService.disconnectAndAwait()
            tokenManager.clearTokens()
            // Fire-and-forget API logout (will fail since token is cleared, that's fine)
            try { apiService.logout() } catch (_: Exception) {}
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                loggedOut = true
            )
        }
    }
}
