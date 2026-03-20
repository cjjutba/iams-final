package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class StudentProfileUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val faceRegistered: Boolean = false,
    val loggedOut: Boolean = false,
)

@HiltViewModel
class StudentProfileViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentProfileUiState())
    val uiState: StateFlow<StudentProfileUiState> = _uiState.asStateFlow()

    init {
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                // Fetch user info
                val userResponse = apiService.getMe()
                if (userResponse.isSuccessful) {
                    _uiState.value = _uiState.value.copy(user = userResponse.body())
                }

                // Fetch face registration status
                val faceResponse = apiService.getFaceStatus()
                if (faceResponse.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        faceRegistered = faceResponse.body()?.faceRegistered ?: false
                    )
                }

                _uiState.value = _uiState.value.copy(isLoading = false)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load profile"
                )
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            loadProfile()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun logout() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            // Set flag FIRST so TokenAuthenticator stops refreshing
            tokenManager.isLoggingOut = true
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
