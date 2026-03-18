package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.RoomResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale
import javax.inject.Inject

data class FacultyHomeUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val todaySchedules: List<ScheduleResponse> = emptyList(),
    val rooms: Map<String, RoomResponse> = emptyMap(),
)

@HiltViewModel
class FacultyHomeViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyHomeUiState())
    val uiState: StateFlow<FacultyHomeUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                // Fetch user info
                val userJob = viewModelScope.launch {
                    try {
                        val response = apiService.getMe()
                        if (response.isSuccessful) {
                            _uiState.value = _uiState.value.copy(user = response.body())
                        }
                    } catch (_: Exception) {}
                }

                // Fetch schedules — filter to today
                val schedulesJob = viewModelScope.launch {
                    try {
                        val response = apiService.getSchedules()
                        if (response.isSuccessful) {
                            val allSchedules = response.body() ?: emptyList()
                            val today = LocalDate.now().dayOfWeek
                                .getDisplayName(TextStyle.FULL, Locale.ENGLISH)
                            val todaySchedules = allSchedules.filter {
                                it.dayOfWeek.equals(today, ignoreCase = true)
                            }
                            _uiState.value = _uiState.value.copy(todaySchedules = todaySchedules)
                        }
                    } catch (_: Exception) {}
                }

                // Fetch rooms — build roomId -> RoomResponse map
                val roomsJob = viewModelScope.launch {
                    try {
                        val response = apiService.getRooms()
                        if (response.isSuccessful) {
                            val roomList = response.body() ?: emptyList()
                            val roomMap = roomList.associateBy { it.id }
                            _uiState.value = _uiState.value.copy(rooms = roomMap)
                        }
                    } catch (_: Exception) {}
                }

                userJob.join()
                schedulesJob.join()
                roomsJob.join()

                _uiState.value = _uiState.value.copy(isLoading = false)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load data. Pull to refresh."
                )
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            loadData()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun logout() {
        viewModelScope.launch {
            try {
                apiService.logout()
            } catch (_: Exception) {}
            tokenManager.clearTokens()
        }
    }
}
