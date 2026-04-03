package com.iams.app.ui.auth

import android.content.Context
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.LoginRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import javax.inject.Inject

private const val TAG = "LoginViewModel"

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
    @ApplicationContext private val appContext: Context
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

                    // Navigate immediately — don't block on face upload
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        loginSuccess = true,
                        userRole = body.user.role,
                        successMessage = "Welcome back!"
                    )

                    // Upload pending face images in the background (fire-and-forget)
                    viewModelScope.launch { uploadPendingFaceImages() }
                } else {
                    val errorBody = response.errorBody()?.string()
                    val message = when (response.code()) {
                        401 -> "Invalid credentials"
                        403 -> "Account not verified. Please check your email."
                        404 -> "Account not found"
                        else -> errorBody ?: "Login failed"
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

    /**
     * Upload face images saved during registration.
     * In Supabase mode, face images are captured in Step 3 but can't be uploaded
     * until the user verifies their email and logs in (needs auth token).
     * Matches React Native's auto-upload on login pattern.
     */
    private suspend fun uploadPendingFaceImages() {
        val prefs = appContext.getSharedPreferences("iams_registration", Context.MODE_PRIVATE)
        if (!prefs.getBoolean("has_pending_faces", false)) return

        val dir = File(appContext.filesDir, "pending_faces")
        val imageFiles = dir.listFiles()?.filter { it.extension == "jpg" } ?: return

        if (imageFiles.isEmpty()) {
            prefs.edit().remove("has_pending_faces").remove("pending_face_count").apply()
            return
        }

        try {
            val parts = imageFiles.mapIndexed { index, file ->
                val bytes = file.readBytes()
                val requestBody = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
                MultipartBody.Part.createFormData("images", "face_$index.jpg", requestBody)
            }

            Log.i(TAG, "Uploading ${imageFiles.size} pending face images...")
            val response = apiService.registerFace(parts)
            if (response.isSuccessful) {
                Log.i(TAG, "Pending face images uploaded successfully (${imageFiles.size} images)")
            } else {
                val errorBody = response.errorBody()?.string() ?: "no body"
                Log.w(TAG, "Pending face upload failed: ${response.code()} - $errorBody")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Pending face upload error: ${e.message}")
        } finally {
            // Clean up regardless of success (don't retry endlessly)
            imageFiles.forEach { it.delete() }
            dir.delete()
            prefs.edit().remove("has_pending_faces").remove("pending_face_count").apply()
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccessMessage() {
        _uiState.value = _uiState.value.copy(successMessage = null)
    }
}
