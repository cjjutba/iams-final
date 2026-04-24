package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.BuildConfig
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.RoomResponse
import com.iams.app.data.model.ScheduleResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Faculty live-feed ViewModel — minimal pure-viewer variant (2026-04-22 split).
 *
 * Responsibilities:
 *   1. Resolve schedule + room from IDs to get a stream_key.
 *   2. Build the WHEP URL pointing at the public VPS mediamtx.
 *
 * Intentionally NOT included (these live in the admin portal on-prem):
 *   - Attendance WebSocket / frame-update tracks / bounding boxes
 *   - Session start/end controls
 *   - Hybrid detection / ML Kit / identity matcher
 *   - Early-leave timeout config slider
 *   - Diagnostic HUD / time-sync client
 *
 * The faculty user watches the video. Attendance is the admin's job.
 */
data class FacultyLiveFeedUiState(
    val isLoading: Boolean = true,
    val error: String? = null,
    val schedule: ScheduleResponse? = null,
    val room: RoomResponse? = null,
    val whepUrl: String = "",
)

@HiltViewModel
class FacultyLiveFeedViewModel @Inject constructor(
    private val apiService: ApiService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyLiveFeedUiState())
    val uiState: StateFlow<FacultyLiveFeedUiState> = _uiState.asStateFlow()

    fun load(scheduleId: String, roomId: String) {
        if (scheduleId.isBlank() || roomId.isBlank()) {
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                error = "Missing schedule or room ID",
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val schedResp = apiService.getSchedule(scheduleId)
                val roomResp = apiService.getRoomById(roomId)
                val schedule = schedResp.body()
                val room = roomResp.body()
                if (schedule == null || room == null) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Schedule or room not found",
                    )
                    return@launch
                }

                val streamKey = room.streamKey?.takeIf { it.isNotBlank() }
                    ?: room.name.lowercase().replace(Regex("\\s+"), "")

                // Faculty app always hits the VPS public WHEP — see build.gradle.kts.
                val url = "http://${BuildConfig.STREAM_HOST}:${BuildConfig.STREAM_WEBRTC_PORT}/$streamKey/whep"

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    schedule = schedule,
                    room = room,
                    whepUrl = url,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.localizedMessage ?: "Failed to load live feed",
                )
            }
        }
    }
}
