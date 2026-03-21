package com.iams.app.ui.auth

import android.graphics.Bitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.CheckEmailRequest
import com.iams.app.data.model.RegisterRequest
import com.iams.app.data.model.ResendVerificationRequest
import com.iams.app.data.model.CheckStudentIdRequest
import com.iams.app.data.model.VerifyStudentIdRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import javax.inject.Inject

data class RegistrationUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    // Step 1 results
    val studentIdChecked: Boolean = false,
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
    val resendSuccess: Boolean = false,
    // Step 3 face capture
    val capturedFaces: List<Bitmap> = emptyList(),
    // Review / upload
    val isUploading: Boolean = false,
    val uploadSuccess: Boolean = false,
    val uploadError: String? = null,
)

@HiltViewModel
class RegistrationViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(RegistrationUiState())
    val uiState: StateFlow<RegistrationUiState> = _uiState.asStateFlow()

    fun checkStudentId(studentId: String) {
        if (studentId.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Please enter your Student ID")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.checkStudentId(
                    CheckStudentIdRequest(studentId.trim().uppercase())
                )

                if (response.isSuccessful) {
                    val body = response.body()!!
                    if (body.exists && body.available) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            studentIdChecked = true,
                            studentId = studentId.trim().uppercase()
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body.message
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = response.errorBody()?.string() ?: "Failed to check Student ID"
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

    fun resetStudentIdCheck() {
        _uiState.value = _uiState.value.copy(
            studentIdChecked = false,
            error = null
        )
    }

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

    fun resendVerificationEmail(email: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.resendVerification(
                    ResendVerificationRequest(email)
                )

                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = null,
                        resendSuccess = true
                    )
                } else {
                    val message = when (response.code()) {
                        429 -> "Please wait before requesting another email"
                        else -> response.errorBody()?.string() ?: "Failed to resend verification email"
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

    // Face capture methods

    fun addCapturedFace(bitmap: Bitmap) {
        val current = _uiState.value.capturedFaces.toMutableList()
        current.add(bitmap)
        _uiState.value = _uiState.value.copy(capturedFaces = current)
    }

    fun removeCapturedFace(index: Int) {
        val current = _uiState.value.capturedFaces.toMutableList()
        if (index in current.indices) {
            current.removeAt(index)
            _uiState.value = _uiState.value.copy(capturedFaces = current)
        }
    }

    fun clearCapturedFaces() {
        _uiState.value = _uiState.value.copy(capturedFaces = emptyList())
    }

    fun uploadFaceImages() {
        val faces = _uiState.value.capturedFaces
        if (faces.isEmpty()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isUploading = true,
                uploadError = null
            )

            try {
                val parts = faces.mapIndexed { index, bitmap ->
                    val stream = ByteArrayOutputStream()
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 90, stream)
                    val bytes = stream.toByteArray()
                    val requestBody = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
                    MultipartBody.Part.createFormData(
                        "images",
                        "face_$index.jpg",
                        requestBody
                    )
                }

                val response = apiService.registerFace(parts)

                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isUploading = false,
                        uploadSuccess = true
                    )
                } else {
                    val message = response.errorBody()?.string() ?: "Face registration failed"
                    _uiState.value = _uiState.value.copy(
                        isUploading = false,
                        uploadError = message
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isUploading = false,
                    uploadError = "Network error. Please check your connection."
                )
            }
        }
    }

    fun clearResendSuccess() {
        _uiState.value = _uiState.value.copy(resendSuccess = false)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearUploadError() {
        _uiState.value = _uiState.value.copy(uploadError = null)
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
