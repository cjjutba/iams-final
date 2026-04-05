package com.iams.app.ui.faculty

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.StudentAttendanceSummaryResponse
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FacultyStudentDetailUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val student: UserResponse? = null,
    val summary: StudentAttendanceSummaryResponse? = null,
    val recentRecords: List<AttendanceRecordResponse> = emptyList(),
)

@HiltViewModel
class FacultyStudentDetailViewModel @Inject constructor(
    private val apiService: ApiService,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    val studentId: String = savedStateHandle["studentId"] ?: ""
    val scheduleId: String = savedStateHandle["scheduleId"] ?: ""

    private val _uiState = MutableStateFlow(FacultyStudentDetailUiState())
    val uiState: StateFlow<FacultyStudentDetailUiState> = _uiState.asStateFlow()

    init {
        loadStudentDetails()
    }

    fun loadStudentDetails(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            }

            try {
                // Fetch all three in parallel
                val studentDeferred = async {
                    try {
                        val response = apiService.getUser(studentId)
                        if (response.isSuccessful) response.body() else null
                    } catch (_: Exception) { null }
                }

                val summaryDeferred = async {
                    try {
                        val response = apiService.getStudentAttendanceSummary(studentId, scheduleId)
                        if (response.isSuccessful) response.body() else null
                    } catch (_: Exception) { null }
                }

                val historyDeferred = async {
                    try {
                        val response = apiService.getStudentAttendanceHistory(
                            studentId = studentId,
                            scheduleId = scheduleId,
                            limit = 10,
                        )
                        if (response.isSuccessful) response.body() ?: emptyList() else emptyList()
                    } catch (_: Exception) { emptyList<AttendanceRecordResponse>() }
                }

                val student = studentDeferred.await()
                val summary = summaryDeferred.await()
                val history = historyDeferred.await()

                _uiState.value = _uiState.value.copy(
                    student = student ?: _uiState.value.student,
                    summary = summary ?: _uiState.value.summary,
                    recentRecords = history,
                    isLoading = false,
                    isRefreshing = false,
                    error = null,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Unable to load student details. Please try again.",
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadStudentDetails(silent = true)
    }
}
