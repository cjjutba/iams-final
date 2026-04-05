package com.iams.app.ui.faculty

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.LiveAttendanceResponse
import com.iams.app.data.model.StudentAttendanceStatus
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FacultyClassDetailUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val classData: LiveAttendanceResponse? = null,
    val students: List<StudentAttendanceStatus> = emptyList(),
    val presentCount: Int = 0,
    val lateCount: Int = 0,
    val absentCount: Int = 0,
    val earlyLeaveCount: Int = 0,
)

@HiltViewModel
class FacultyClassDetailViewModel @Inject constructor(
    private val apiService: ApiService,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    val scheduleId: String = savedStateHandle["scheduleId"] ?: ""
    val date: String = savedStateHandle["date"] ?: ""

    private val _uiState = MutableStateFlow(FacultyClassDetailUiState())
    val uiState: StateFlow<FacultyClassDetailUiState> = _uiState.asStateFlow()

    init {
        loadClassDetails()
    }

    fun loadClassDetails(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            }
            try {
                val response = apiService.getLiveAttendance(scheduleId)
                if (response.isSuccessful) {
                    val data = response.body()
                    _uiState.value = _uiState.value.copy(
                        classData = data,
                        students = data?.students ?: emptyList(),
                        presentCount = data?.presentCount ?: 0,
                        lateCount = data?.lateCount ?: 0,
                        absentCount = data?.absentCount ?: 0,
                        earlyLeaveCount = data?.earlyLeaveCount ?: 0,
                        isLoading = false,
                        isRefreshing = false,
                        error = null,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load class details",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Unable to load class details. Please try again.",
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadClassDetails(silent = true)
    }
}
