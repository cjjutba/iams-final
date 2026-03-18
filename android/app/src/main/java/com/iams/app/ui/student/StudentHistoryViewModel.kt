package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.AttendanceRecordResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class StudentHistoryUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val records: List<AttendanceRecordResponse> = emptyList(),
    val startDate: String? = null,
    val endDate: String? = null,
)

@HiltViewModel
class StudentHistoryViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentHistoryUiState())
    val uiState: StateFlow<StudentHistoryUiState> = _uiState.asStateFlow()

    init {
        loadHistory()
    }

    fun loadHistory(startDate: String? = null, endDate: String? = null) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                error = null,
                startDate = startDate,
                endDate = endDate
            )

            try {
                val response = apiService.getMyAttendance(
                    startDate = startDate,
                    endDate = endDate
                )

                if (response.isSuccessful) {
                    val records = response.body() ?: emptyList()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        records = records.sortedByDescending { it.date }
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load attendance history"
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

    fun setDateFilter(startDate: String?, endDate: String?) {
        loadHistory(startDate, endDate)
    }

    fun clearFilter() {
        loadHistory()
    }
}
