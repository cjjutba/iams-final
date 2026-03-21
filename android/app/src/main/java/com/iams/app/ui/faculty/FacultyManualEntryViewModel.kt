package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.ManualEntryRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject

data class FacultyManualEntryUiState(
    val studentId: String = "",
    val selectedStatus: String = "present",
    val remarks: String = "",
    val isSubmitting: Boolean = false,
    val error: String? = null,
    val studentIdError: String? = null,
)

@HiltViewModel
class FacultyManualEntryViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyManualEntryUiState())
    val uiState: StateFlow<FacultyManualEntryUiState> = _uiState.asStateFlow()

    fun updateStudentId(value: String) {
        _uiState.value = _uiState.value.copy(
            studentId = value,
            studentIdError = null
        )
    }

    fun updateStatus(value: String) {
        _uiState.value = _uiState.value.copy(selectedStatus = value)
    }

    fun updateRemarks(value: String) {
        _uiState.value = _uiState.value.copy(remarks = value)
    }

    fun submit(
        scheduleId: String,
        onSuccess: () -> Unit,
        onError: (String) -> Unit
    ) {
        val state = _uiState.value

        // Validate
        if (state.studentId.isBlank()) {
            _uiState.value = state.copy(studentIdError = "Student ID is required")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSubmitting = true, error = null)

            try {
                val today = LocalDate.now().format(DateTimeFormatter.ISO_LOCAL_DATE)
                val request = ManualEntryRequest(
                    scheduleId = scheduleId,
                    studentId = state.studentId,
                    date = today,
                    status = state.selectedStatus,
                    remarks = state.remarks.ifBlank { null },
                )

                val response = apiService.createManualEntry(request)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(isSubmitting = false)
                    onSuccess()
                } else {
                    _uiState.value = _uiState.value.copy(isSubmitting = false)
                    onError("Failed to record attendance")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isSubmitting = false)
                onError(e.message ?: "An error occurred")
            }
        }
    }

    fun resetForm() {
        _uiState.value = FacultyManualEntryUiState()
    }
}
