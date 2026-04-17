package com.iams.app.ui.auth

import android.graphics.Bitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.RegisterRequest
import com.iams.app.data.model.CheckStudentIdRequest
import com.iams.app.data.model.VerifyStudentIdRequest
import android.content.Context
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
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
    val email: String = "",
    // Step 2 results
    val accountCreated: Boolean = false,
    val registrationComplete: Boolean = false,
    val registeredEmail: String = "",
    // Step 3 face capture
    val capturedFaces: List<Bitmap> = emptyList(),
    // Review / upload
    val isUploading: Boolean = false,
    val uploadSuccess: Boolean = false,
    val uploadError: String? = null,
)

@HiltViewModel
class RegistrationViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
    @ApplicationContext private val appContext: Context
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
                            email = info["email"]?.toString() ?: "",
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

        // Final-gate validation — password MUST satisfy the unified policy even
        // if Step 2 was bypassed or the holder was mutated elsewhere.
        val sanitizedEmail = InputSanitizer.email(email)
        val sanitizedPassword = InputSanitizer.password(password)
        val emailErr = InputValidation.validateEmail(sanitizedEmail)
        val passwordErr = InputValidation.validatePassword(sanitizedPassword)
        if (emailErr != null) {
            _uiState.value = _uiState.value.copy(error = emailErr)
            return
        }
        if (passwordErr != null) {
            _uiState.value = _uiState.value.copy(error = passwordErr)
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.register(
                    RegisterRequest(
                        email = sanitizedEmail,
                        password = sanitizedPassword,
                        firstName = firstName,
                        lastName = lastName,
                        studentId = studentId,
                        birthdate = birthdate
                    )
                )

                if (response.isSuccessful) {
                    val body = response.body()
                    // Save tokens so face upload can authenticate
                    val tokens = body?.tokens
                    if (tokens != null) {
                        tokenManager.saveTokens(
                            access = tokens.accessToken,
                            refresh = tokens.refreshToken ?: "",
                            role = "STUDENT",
                            userId = body.user?.id ?: ""
                        )
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        accountCreated = true,
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

    // Face capture methods

    fun addCapturedFace(bitmap: Bitmap) {
        val current = _uiState.value.capturedFaces.toMutableList()
        current.add(bitmap)
        _uiState.value = _uiState.value.copy(capturedFaces = current)
    }

    fun removeCapturedFace(index: Int) {
        val current = _uiState.value.capturedFaces.toMutableList()
        if (index in current.indices) {
            val removed = current.removeAt(index)
            if (!removed.isRecycled) removed.recycle()
            _uiState.value = _uiState.value.copy(capturedFaces = current)
        }
    }

    fun clearCapturedFaces() {
        _uiState.value.capturedFaces.forEach { if (!it.isRecycled) it.recycle() }
        _uiState.value = _uiState.value.copy(capturedFaces = emptyList())
    }

    override fun onCleared() {
        super.onCleared()
        _uiState.value.capturedFaces.forEach { if (!it.isRecycled) it.recycle() }
    }

    /**
     * Downscale a bitmap so its longest edge is at most [maxSize] pixels.
     * Preserves aspect ratio. Returns the original if already small enough.
     */
    private fun downscaleBitmap(bitmap: Bitmap, maxSize: Int = 800): Bitmap {
        val w = bitmap.width
        val h = bitmap.height
        if (w <= maxSize && h <= maxSize) return bitmap
        val scale = maxSize.toFloat() / maxOf(w, h)
        return Bitmap.createScaledBitmap(
            bitmap,
            (w * scale).toInt(),
            (h * scale).toInt(),
            true
        )
    }

    private fun bitmapToJpegPart(bitmap: Bitmap, index: Int): MultipartBody.Part {
        val scaled = downscaleBitmap(bitmap)
        val stream = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, 85, stream)
        val bytes = stream.toByteArray()
        val requestBody = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
        return MultipartBody.Part.createFormData("images", "face_$index.jpg", requestBody)
    }

    fun uploadFaceImages(reregister: Boolean = false) {
        val faces = _uiState.value.capturedFaces
        if (faces.isEmpty()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isUploading = true,
                uploadError = null
            )

            try {
                val parts = faces.mapIndexed { index, bitmap ->
                    bitmapToJpegPart(bitmap, index)
                }

                val response = if (reregister) {
                    apiService.reregisterFace(parts)
                } else {
                    apiService.registerFace(parts)
                }

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

    /**
     * Emergency fallback: save captured face images to app-internal storage.
     * Only called when the immediate post-registration upload fails and the
     * user taps "Skip for Now". StudentHomeViewModel re-attempts the upload
     * on next login via PendingFaceUploadManager.
     */
    fun savePendingFaceImages() {
        val faces = _uiState.value.capturedFaces
        if (faces.isEmpty()) return

        try {
            val dir = java.io.File(appContext.filesDir, "pending_faces")
            dir.mkdirs()
            // Clear any previous pending images
            dir.listFiles()?.forEach { it.delete() }

            var savedCount = 0
            faces.forEachIndexed { index, bitmap ->
                try {
                    if (!bitmap.isRecycled) {
                        val scaled = downscaleBitmap(bitmap)
                        val file = java.io.File(dir, "face_$index.jpg")
                        file.outputStream().use { out ->
                            scaled.compress(Bitmap.CompressFormat.JPEG, 85, out)
                        }
                        savedCount++
                    }
                } catch (_: Exception) {
                    // Skip bitmaps that can't be saved (recycled, etc.)
                }
            }

            if (savedCount > 0) {
                // Mark that we have pending face images
                appContext.getSharedPreferences("iams_registration", Context.MODE_PRIVATE)
                    .edit()
                    .putBoolean("has_pending_faces", true)
                    .putInt("pending_face_count", savedCount)
                    .apply()
            }
        } catch (_: Exception) {
            // Don't let face saving crash the registration flow
        }
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
            accountCreated = false,
            registrationComplete = false,
            error = null
        )
    }
}
