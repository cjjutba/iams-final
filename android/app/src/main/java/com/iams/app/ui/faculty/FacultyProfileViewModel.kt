package com.iams.app.ui.faculty

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

data class FacultyProfileUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val loggedOut: Boolean = false,
)

@HiltViewModel
class FacultyProfileViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
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
                        user = response.body()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load profile"
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

    fun logout() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                apiService.logout()
            } catch (_: Exception) {
                // Proceed with local logout even if API call fails
            }
            tokenManager.clearTokens()
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                loggedOut = true
            )
        }
    }
}
