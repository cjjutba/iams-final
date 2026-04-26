package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.BuildConfig
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class StudentProfileUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val faceRegistered: Boolean = false,
    // Absolute URL of the student's profile photo (registered face, center
    // angle preferred, first available otherwise). Null = fall back to the
    // initials-circle avatar — covers both "not registered" and "registration
    // exists but no image bytes were persisted" (older registrations).
    val profilePhotoUrl: String? = null,
    val loggedOut: Boolean = false,
)

@HiltViewModel
class StudentProfileViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
    val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentProfileUiState())
    val uiState: StateFlow<StudentProfileUiState> = _uiState.asStateFlow()

    init {
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                // Fetch user info
                val userResponse = apiService.getMe()
                val user = userResponse.body()
                if (userResponse.isSuccessful) {
                    _uiState.value = _uiState.value.copy(user = user)
                }

                // Fetch face registration status
                val faceResponse = apiService.getFaceStatus()
                val isRegistered = faceResponse.body()?.faceRegistered ?: false
                if (faceResponse.isSuccessful) {
                    _uiState.value = _uiState.value.copy(faceRegistered = isRegistered)
                }

                // Resolve profile photo URL when both prerequisites are met:
                //   1. /auth/me returned a user (we need user.id for the path)
                //   2. /face/status said face is registered (else the
                //      registration call would just return available=false)
                // On any failure here we silently fall back to the initials
                // avatar — a missing photo isn't worth a screen-level error.
                val photoUrl = if (user != null && isRegistered) {
                    runCatching { resolveProfilePhotoUrl(user.id) }
                        .getOrNull()
                } else null

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    profilePhotoUrl = photoUrl,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Failed to load profile"
                )
            }
        }
    }

    /**
     * Asks the backend for the student's per-angle registration metadata and
     * returns the absolute URL of the best angle for an avatar — `center` if
     * present, otherwise the first angle whose image bytes were persisted.
     *
     * Returns null when the registration is missing, the backend response
     * has no usable angles, or the network call fails. The caller treats
     * null as "show initials".
     *
     * The backend returns `image_url` as a path like
     * `/api/v1/face/registrations/<uid>/images/center`. Coil needs an
     * absolute URL, so we glue on the same `BACKEND_HOST:PORT` scheme that
     * Retrofit's baseUrl uses (see NetworkModule).
     */
    private suspend fun resolveProfilePhotoUrl(userId: String): String? {
        val resp = apiService.getFaceRegistration(userId)
        if (!resp.isSuccessful) return null
        val body = resp.body() ?: return null
        if (!body.available) return null
        val angles = body.angles ?: return null
        val best = angles.firstOrNull { it.angleLabel.equals("center", ignoreCase = true) }
            ?: angles.firstOrNull { !it.imageUrl.isNullOrBlank() }
            ?: return null
        val path = best.imageUrl?.takeIf { it.isNotBlank() } ?: return null
        // Backend returns server-relative paths starting with `/api/v1/...`.
        // Coil will refuse "http:" + that without an explicit host.
        return "http://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}$path"
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        loadProfile()
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun logout() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            // Set flag FIRST so TokenAuthenticator stops refreshing
            tokenManager.isLoggingOut = true
            // Stop the real-time WebSocket *before* clearing tokens so any
            // in-flight reconnect coroutine can't race and read a null
            // userId. `disconnectAndAwait` joins the reconnect job.
            notificationService.disconnectAndAwait()
            tokenManager.clearTokens()
            // Fire-and-forget API logout (will fail since token is cleared, that's fine)
            try { apiService.logout() } catch (_: Exception) {}
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                loggedOut = true
            )
        }
    }
}
