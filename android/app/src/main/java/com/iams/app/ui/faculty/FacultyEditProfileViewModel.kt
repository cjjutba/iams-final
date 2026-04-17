package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.ChangePasswordRequest
import com.iams.app.data.model.UpdateProfileRequest
import com.iams.app.data.model.UserResponse
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.PasswordEvaluation
import com.iams.app.ui.utils.PasswordPolicy
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

    // Touched flags — suppress errors until user interacts.
    val newPasswordTouched: Boolean = false,
    val confirmPasswordTouched: Boolean = false,
) {
    val passwordEvaluation: PasswordEvaluation
        get() = PasswordPolicy.evaluate(newPassword)

    val liveConfirmError: String?
        get() = if (!confirmPasswordTouched || confirmPassword.isEmpty()) null
        else if (newPassword != confirmPassword) "Passwords do not match"
        else null

    val canSubmitPassword: Boolean
        get() = currentPassword.isNotBlank() &&
            passwordEvaluation.isValid &&
            confirmPassword.isNotEmpty() &&
            newPassword == confirmPassword &&
            !isChangingPassword
}

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
                        isRefreshing = false,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(isRefreshing = false)
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(isRefreshing = false)
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadUser()
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
        _uiState.value = _uiState.value.copy(
            newPassword = value,
            newPasswordError = null,
            newPasswordTouched = true,
        )
    }

    fun updateConfirmPassword(value: String) {
        _uiState.value = _uiState.value.copy(
            confirmPassword = value,
            confirmPasswordError = null,
            confirmPasswordTouched = true,
        )
    }

    // -- Save profile --

    fun saveProfile() {
        val state = _uiState.value

        // Validate
        val emailErr = InputValidation.validateEmail(state.email)
        val phoneErr = InputValidation.validatePhoneOptional(state.phone)

        if (emailErr != null || phoneErr != null) {
            _uiState.value = _uiState.value.copy(emailError = emailErr, phoneError = phoneErr)
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSavingProfile = true, successMessage = null, errorMessage = null)
            try {
                val request = UpdateProfileRequest(
                    email = InputSanitizer.email(state.email),
                    phone = InputSanitizer.trimmed(state.phone).ifBlank { null },
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
        val sanitizedNew = InputSanitizer.password(state.newPassword)

        // Validate
        val currentErr = InputValidation.validateRequired(state.currentPassword, "Current password")
        val newErr = InputValidation.validatePassword(sanitizedNew)
        val confirmErr = InputValidation.validatePasswordMatch(sanitizedNew, state.confirmPassword)

        if (currentErr != null || newErr != null || confirmErr != null) {
            _uiState.value = _uiState.value.copy(
                currentPasswordError = currentErr,
                newPasswordError = newErr,
                confirmPasswordError = confirmErr,
                newPasswordTouched = true,
                confirmPasswordTouched = true,
            )
            return
        }

        if (state.currentPassword == sanitizedNew) {
            _uiState.value = state.copy(
                newPasswordError = "New password must be different from current password",
                newPasswordTouched = true,
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isChangingPassword = true, successMessage = null, errorMessage = null)
            try {
                val request = ChangePasswordRequest(
                    oldPassword = state.currentPassword,
                    newPassword = sanitizedNew,
                )
                val response = apiService.changePassword(request)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isChangingPassword = false,
                        currentPassword = "",
                        newPassword = "",
                        confirmPassword = "",
                        newPasswordTouched = false,
                        confirmPasswordTouched = false,
                        successMessage = "Password changed successfully",
                    )
                } else {
                    val msg = when (response.code()) {
                        400, 401 -> "Current password is incorrect"
                        else -> "Failed to change password"
                    }
                    _uiState.value = _uiState.value.copy(
                        isChangingPassword = false,
                        errorMessage = msg,
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
