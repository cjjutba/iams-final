package com.iams.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiErrorParser
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.LoginRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val loginSuccess: Boolean = false,
    val userRole: String? = null,
    val successMessage: String? = null
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun login(identifier: String, password: String) {
        // Callers (StudentLoginScreen, FacultyLoginScreen) validate before calling
        if (identifier.isBlank() || password.isBlank()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.login(LoginRequest(identifier, password))

                if (response.isSuccessful) {
                    val body = response.body()!!
                    tokenManager.saveTokens(
                        access = body.accessToken,
                        refresh = body.refreshToken,
                        role = body.user.role,
                        userId = body.user.id
                    )

                    // Faculty app has no push-notification WebSocket — the
                    // notifications path was deliberately dropped in the
                    // 2026-04-22 two-app split.

                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        loginSuccess = true,
                        userRole = body.user.role,
                        successMessage = "Welcome back!"
                    )
                } else {
                    val message = when (response.code()) {
                        401 -> "Invalid credentials"
                        403 -> "Account not verified. Please check your email."
                        404 -> "Account not found"
                        else -> ApiErrorParser.parse(response, fallback = "Login failed. Please try again.")
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = message
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Network error. Please check your connection."
                )
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccessMessage() {
        _uiState.value = _uiState.value.copy(successMessage = null)
    }
}
