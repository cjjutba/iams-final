package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.ChangePasswordRequest
import com.iams.app.data.model.UpdateProfileRequest
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FacultyEditProfileUiState(
    val isRefreshing: Boolean = false,
    val isSavingProfile: Boolean = false,
    val isChangingPassword: Boolean = false,
    val user: UserResponse? = null,

    // Profile fields
    val email: String = "",
    val phone: String = "",
    val profileDirty: Boolean = false,

    // Password fields
    val currentPassword: String = "",
    val newPassword: String = "",
    val confirmPassword: String = "",

    // Validation errors
    val emailError: String? = null,
    val phoneError: String? = null,
    val currentPasswordError: String? = null,
    val newPasswordError: String? = null,
    val confirmPasswordError: String? = null,

    // Result messages
    val successMessage: String? = null,
    val errorMessage: String? = null,
)

@HiltViewModel
class FacultyEditProfileViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyEditProfileUiState())
    val uiState: StateFlow<FacultyEditProfileUiState> = _uiState.asStateFlow()

    init {
        loadUser()
    }

    fun loadUser() {
        viewModelScope.launch {
            try {
                val response = apiService.getMe()
                if (response.isSuccessful) {
                    val user = response.body()
                    _uiState.value = _uiState.value.copy(
                        user = user,
                        email = user?.email ?: "",
                    )
                }
            } catch (_: Exception) {}
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true)
            loadUser()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    // -- Profile field updates --

    fun updateEmail(value: String) {
        _uiState.value = _uiState.value.copy(
            email = value,
            emailError = null,
            profileDirty = value != (_uiState.value.user?.email ?: ""),
        )
    }

    fun updatePhone(value: String) {
        _uiState.value = _uiState.value.copy(
            phone = value,
            phoneError = null,
            profileDirty = true,
        )
    }

    // -- Password field updates --

    fun updateCurrentPassword(value: String) {
        _uiState.value = _uiState.value.copy(currentPassword = value, currentPasswordError = null)
    }

    fun updateNewPassword(value: String) {
        _uiState.value = _uiState.value.copy(newPassword = value, newPasswordError = null)
    }

    fun updateConfirmPassword(value: String) {
        _uiState.value = _uiState.value.copy(confirmPassword = value, confirmPasswordError = null)
    }

    // -- Save profile --

    fun saveProfile() {
        val state = _uiState.value

        // Validate
        var hasError = false
        if (state.email.isBlank()) {
            _uiState.value = _uiState.value.copy(emailError = "Email is required")
            hasError = true
        } else if (!android.util.Patterns.EMAIL_ADDRESS.matcher(state.email).matches()) {
            _uiState.value = _uiState.value.copy(emailError = "Invalid email address")
            hasError = true
        }

        if (state.phone.isNotBlank() && !state.phone.matches(Regex("^09\\d{9}$"))) {
            _uiState.value = _uiState.value.copy(phoneError = "Invalid phone number (09XXXXXXXXX)")
            hasError = true
        }

        if (hasError) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSavingProfile = true, successMessage = null, errorMessage = null)
            try {
                val request = UpdateProfileRequest(
                    email = state.email,
                    phone = state.phone.ifBlank { null },
                )
                val response = apiService.updateProfile(request)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isSavingProfile = false,
                        profileDirty = false,
                        successMessage = "Profile updated successfully",
                        user = response.body() ?: _uiState.value.user,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isSavingProfile = false,
                        errorMessage = "Failed to update profile",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isSavingProfile = false,
                    errorMessage = e.message ?: "Failed to update profile",
                )
            }
        }
    }

    // -- Change password --

    fun changePassword() {
        val state = _uiState.value

        // Validate
        var hasError = false
        if (state.currentPassword.isBlank()) {
            _uiState.value = _uiState.value.copy(currentPasswordError = "Required")
            hasError = true
        }
        if (state.newPassword.isBlank()) {
            _uiState.value = _uiState.value.copy(newPasswordError = "Required")
            hasError = true
        } else if (state.newPassword.length < 8) {
            _uiState.value = _uiState.value.copy(newPasswordError = "At least 8 characters")
            hasError = true
        }
        if (state.confirmPassword.isBlank()) {
            _uiState.value = _uiState.value.copy(confirmPasswordError = "Required")
            hasError = true
        } else if (state.newPassword != state.confirmPassword) {
            _uiState.value = _uiState.value.copy(confirmPasswordError = "Passwords do not match")
            hasError = true
        }

        if (hasError) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isChangingPassword = true, successMessage = null, errorMessage = null)
            try {
                val request = ChangePasswordRequest(
                    oldPassword = state.currentPassword,
                    newPassword = state.newPassword,
                )
                val response = apiService.changePassword(request)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isChangingPassword = false,
                        currentPassword = "",
                        newPassword = "",
                        confirmPassword = "",
                        successMessage = "Password changed successfully",
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isChangingPassword = false,
                        errorMessage = "Failed to change password",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isChangingPassword = false,
                    errorMessage = e.message ?: "Failed to change password",
                )
            }
        }
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(successMessage = null, errorMessage = null)
    }
}
