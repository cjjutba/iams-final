package com.iams.app.data.api

import android.content.Context
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

sealed class PendingUploadState {
    data object Idle : PendingUploadState()
    data object Uploading : PendingUploadState()
    data object Success : PendingUploadState()
    data class Failed(val message: String) : PendingUploadState()
}

/**
 * Manages pending face image uploads that were captured during registration
 * but couldn't be uploaded until the user logs in (needs auth token).
 *
 * This is a singleton so it survives ViewModel scope changes during navigation.
 */
@Singleton
class PendingFaceUploadManager @Inject constructor(
    @ApplicationContext private val appContext: Context,
    private val apiService: ApiService
) {
    private val _uploadState = MutableStateFlow<PendingUploadState>(PendingUploadState.Idle)
    val uploadState: StateFlow<PendingUploadState> = _uploadState.asStateFlow()

    private val prefs get() = appContext.getSharedPreferences("iams_registration", Context.MODE_PRIVATE)

    fun hasPendingFaces(): Boolean {
        if (!prefs.getBoolean("has_pending_faces", false)) return false
        val dir = File(appContext.filesDir, "pending_faces")
        val files = dir.listFiles()?.filter { it.extension == "jpg" } ?: emptyList()
        return files.isNotEmpty()
    }

    /**
     * Upload pending face images. Returns true if upload succeeded or no pending faces.
     */
    suspend fun uploadPendingFaces(): Boolean {
        if (!hasPendingFaces()) return true

        _uploadState.value = PendingUploadState.Uploading

        val dir = File(appContext.filesDir, "pending_faces")
        val imageFiles = dir.listFiles()?.filter { it.extension == "jpg" }?.sortedBy { it.name }
            ?: run {
                cleanup()
                _uploadState.value = PendingUploadState.Idle
                return true
            }

        return try {
            val parts = imageFiles.mapIndexed { index, file ->
                val bytes = file.readBytes()
                val requestBody = bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
                MultipartBody.Part.createFormData("images", "face_$index.jpg", requestBody)
            }

            Log.i(TAG, "Uploading ${imageFiles.size} pending face images...")
            val response = apiService.registerFace(parts)

            if (response.isSuccessful) {
                Log.i(TAG, "Pending face images uploaded successfully")
                cleanup()
                _uploadState.value = PendingUploadState.Success
                true
            } else {
                val errorBody = response.errorBody()?.string() ?: "unknown error"
                Log.w(TAG, "Pending face upload failed: ${response.code()} - $errorBody")
                // Don't cleanup on failure — keep files for retry
                _uploadState.value = PendingUploadState.Failed("Upload failed: ${response.code()}")
                false
            }
        } catch (e: Exception) {
            Log.w(TAG, "Pending face upload error: ${e.message}")
            // Don't cleanup on failure — keep files for retry
            _uploadState.value = PendingUploadState.Failed(e.message ?: "Upload failed")
            false
        }
    }

    private fun cleanup() {
        val dir = File(appContext.filesDir, "pending_faces")
        dir.listFiles()?.forEach { it.delete() }
        dir.delete()
        prefs.edit().remove("has_pending_faces").remove("pending_face_count").apply()
    }

    fun resetState() {
        _uploadState.value = PendingUploadState.Idle
    }

    companion object {
        private const val TAG = "PendingFaceUpload"
    }
}
