package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.ChangePasswordRequest
import com.iams.app.data.model.UpdateProfileRequest
import com.iams.app.data.model.UserResponse
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class EditProfileUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val user: UserResponse? = null,

    // Profile form
    val email: String = "",
    val phone: String = "",
    val isSavingProfile: Boolean = false,
    val profileSuccess: String? = null,
    val profileError: String? = null,

    // Password form
    val currentPassword: String = "",
    val newPassword: String = "",
    val confirmPassword: String = "",
    val isChangingPassword: Boolean = false,
    val passwordSuccess: String? = null,
    val passwordError: String? = null,

    // Validation errors
    val emailError: String? = null,
    val phoneError: String? = null,
    val currentPasswordError: String? = null,
    val newPasswordError: String? = null,
    val confirmPasswordError: String? = null,
)

@HiltViewModel
class StudentEditProfileViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(EditProfileUiState())
    val uiState: StateFlow<EditProfileUiState> = _uiState.asStateFlow()

    init {
        loadUser()
    }

    fun loadUser() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val response = apiService.getMe()
                if (response.isSuccessful) {
                    val user = response.body()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        user = user,
                        email = user?.email ?: "",
                        phone = "", // Phone is not in UserResponse; leave blank
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadUser()
    }

    // --- Profile form field updates ---

    fun updateEmail(value: String) {
        _uiState.value = _uiState.value.copy(email = value, emailError = null, profileError = null)
    }

    fun updatePhone(value: String) {
        _uiState.value = _uiState.value.copy(phone = value, phoneError = null, profileError = null)
    }

    // --- Password form field updates ---

    fun updateCurrentPassword(value: String) {
        _uiState.value = _uiState.value.copy(
            currentPassword = value,
            currentPasswordError = null,
            passwordError = null
        )
    }

    fun updateNewPassword(value: String) {
        _uiState.value = _uiState.value.copy(
            newPassword = value,
            newPasswordError = null,
            passwordError = null
        )
    }

    fun updateConfirmPassword(value: String) {
        _uiState.value = _uiState.value.copy(
            confirmPassword = value,
            confirmPasswordError = null,
            passwordError = null
        )
    }

    // --- Save Profile ---

    fun saveProfile() {
        val state = _uiState.value

        // Validate
        val emailErr = InputValidation.validateEmail(state.email)
        val phoneErr = InputValidation.validatePhone(state.phone)

        if (emailErr != null || phoneErr != null) {
            _uiState.value = state.copy(emailError = emailErr, phoneError = phoneErr)
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isSavingProfile = true,
                profileSuccess = null,
                profileError = null
            )

            try {
                val response = apiService.updateProfile(
                    UpdateProfileRequest(
                        email = InputSanitizer.email(state.email),
                        phone = InputSanitizer.trimmed(state.phone)
                    )
                )

                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isSavingProfile = false,
                        profileSuccess = "Profile updated successfully",
                        user = response.body() ?: _uiState.value.user
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isSavingProfile = false,
                        profileError = "Failed to update profile"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isSavingProfile = false,
                    profileError = "Network error. Please try again."
                )
            }
        }
    }

    // --- Change Password ---

    fun changePassword() {
        val state = _uiState.value

        // Validate
        val currentErr = InputValidation.validateRequired(state.currentPassword, "Current password")
        val newErr = InputValidation.validatePassword(state.newPassword)
        val confirmErr = InputValidation.validatePasswordMatch(state.newPassword, state.confirmPassword)

        if (currentErr != null || newErr != null || confirmErr != null) {
            _uiState.value = state.copy(
                currentPasswordError = currentErr,
                newPasswordError = newErr,
                confirmPasswordError = confirmErr
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isChangingPassword = true,
                passwordSuccess = null,
                passwordError = null
            )

            try {
                val response = apiService.changePassword(
                    ChangePasswordRequest(
                        oldPassword = state.currentPassword,
                        newPassword = state.newPassword
                    )
                )

                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isChangingPassword = false,
                        passwordSuccess = "Password changed successfully",
                        currentPassword = "",
                        newPassword = "",
                        confirmPassword = ""
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isChangingPassword = false,
                        passwordError = "Failed to change password"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isChangingPassword = false,
                    passwordError = "Network error. Please try again."
                )
            }
        }
    }

    fun clearProfileMessages() {
        _uiState.value = _uiState.value.copy(profileSuccess = null, profileError = null)
    }

    fun clearPasswordMessages() {
        _uiState.value = _uiState.value.copy(passwordSuccess = null, passwordError = null)
    }
}
