package com.iams.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.CheckEmailRequest
import com.iams.app.data.model.RegisterRequest
import com.iams.app.data.model.VerifyStudentIdRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RegistrationUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    // Step 1 results
    val studentVerified: Boolean = false,
    val studentId: String = "",
    val firstName: String = "",
    val lastName: String = "",
    // Step 2 results
    val registrationComplete: Boolean = false,
    val registeredEmail: String = "",
    // Email verification
    val emailVerified: Boolean = false,
    val isPolling: Boolean = false,
)

@HiltViewModel
class RegistrationViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(RegistrationUiState())
    val uiState: StateFlow<RegistrationUiState> = _uiState.asStateFlow()

    fun verifyStudentId(studentId: String, birthdate: String) {
        if (studentId.isBlank() || birthdate.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Please fill in all fields")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.verifyStudentId(
                    VerifyStudentIdRequest(studentId, birthdate)
                )

                if (response.isSuccessful) {
                    val body = response.body()!!
                    if (body.valid) {
                        val info = body.studentInfo ?: emptyMap()
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            studentVerified = true,
                            studentId = studentId,
                            firstName = info["first_name"]?.toString() ?: "",
                            lastName = info["last_name"]?.toString() ?: "",
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body.message
                        )
                    }
                } else {
                    val message = when (response.code()) {
                        404 -> "Student ID not found"
                        409 -> "Student already registered"
                        else -> response.errorBody()?.string() ?: "Verification failed"
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

    fun register(
        email: String,
        password: String,
        studentId: String,
        firstName: String,
        lastName: String,
        birthdate: String
    ) {
        if (email.isBlank() || password.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Please fill in all fields")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.register(
                    RegisterRequest(
                        email = email,
                        password = password,
                        firstName = firstName,
                        lastName = lastName,
                        studentId = studentId,
                        birthdate = birthdate
                    )
                )

                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        registrationComplete = true,
                        registeredEmail = email
                    )
                } else {
                    val message = when (response.code()) {
                        409 -> "An account with this email already exists"
                        422 -> "Invalid input. Please check your details."
                        else -> response.errorBody()?.string() ?: "Registration failed"
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

    fun checkEmailVerified(email: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.checkEmailVerified(CheckEmailRequest(email))

                if (response.isSuccessful) {
                    val body = response.body()!!
                    if (body.verified) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            emailVerified = true
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = "Email not yet verified. Please check your inbox."
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Could not check verification status"
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

    fun startEmailPolling(email: String) {
        if (_uiState.value.isPolling) return
        _uiState.value = _uiState.value.copy(isPolling = true)

        viewModelScope.launch {
            while (_uiState.value.isPolling && !_uiState.value.emailVerified) {
                delay(5000)
                try {
                    val response = apiService.checkEmailVerified(CheckEmailRequest(email))
                    if (response.isSuccessful && response.body()?.verified == true) {
                        _uiState.value = _uiState.value.copy(
                            emailVerified = true,
                            isPolling = false
                        )
                    }
                } catch (_: Exception) {
                    // Silently continue polling
                }
            }
        }
    }

    fun stopEmailPolling() {
        _uiState.value = _uiState.value.copy(isPolling = false)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun resetVerification() {
        _uiState.value = _uiState.value.copy(
            studentVerified = false,
            error = null
        )
    }

    fun resetRegistration() {
        _uiState.value = _uiState.value.copy(
            registrationComplete = false,
            error = null
        )
    }
}
