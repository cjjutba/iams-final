package com.iams.app.ui.faculty

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.ScheduleResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject

data class SessionSummary(
    val date: String,
    val scheduleId: String,
    val subjectCode: String?,
    val subjectName: String,
    val presentCount: Int,
    val lateCount: Int,
    val absentCount: Int,
    val earlyLeaveCount: Int,
    val records: List<AttendanceRecordResponse>,
)

data class OverallSummary(
    val totalSessions: Int = 0,
    val totalPresent: Int = 0,
    val totalLate: Int = 0,
    val totalAbsent: Int = 0,
    val attendanceRate: Float = 0f,
)

data class FacultyHistoryUiState(
    val isLoading: Boolean = false,
    val isExporting: Boolean = false,
    val hasLoaded: Boolean = false,
    val error: String? = null,
    val exportSuccess: String? = null,
    val schedules: List<ScheduleResponse> = emptyList(),
    val selectedScheduleIds: Set<String> = emptySet(),
    val selectAll: Boolean = true,
    val startDate: LocalDate = LocalDate.now().withDayOfMonth(1),
    val endDate: LocalDate = LocalDate.now(),
    val sessions: List<SessionSummary> = emptyList(),
    val overallSummary: OverallSummary = OverallSummary(),
)

@HiltViewModel
class FacultyHistoryViewModel @Inject constructor(
    private val apiService: ApiService,
    val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyHistoryUiState())
    val uiState: StateFlow<FacultyHistoryUiState> = _uiState.asStateFlow()

    private val dateFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    init {
        loadSchedules()
    }

    fun loadSchedules() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = apiService.getMySchedules()
                if (response.isSuccessful) {
                    val schedules = response.body() ?: emptyList()
                    val allIds = schedules.map { it.id }.toSet()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        schedules = schedules,
                        selectedScheduleIds = allIds,
                        selectAll = true,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load schedules",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Network error. Please check your connection.",
                )
            }
        }
    }

    fun toggleScheduleSelection(id: String) {
        val current = _uiState.value.selectedScheduleIds.toMutableSet()
        if (current.contains(id)) {
            current.remove(id)
        } else {
            current.add(id)
        }
        val allScheduleIds = _uiState.value.schedules.map { it.id }.toSet()
        _uiState.value = _uiState.value.copy(
            selectedScheduleIds = current,
            selectAll = current == allScheduleIds,
        )
    }

    fun toggleSelectAll() {
        val newSelectAll = !_uiState.value.selectAll
        val allIds = if (newSelectAll) {
            _uiState.value.schedules.map { it.id }.toSet()
        } else {
            emptySet()
        }
        _uiState.value = _uiState.value.copy(
            selectAll = newSelectAll,
            selectedScheduleIds = allIds,
        )
    }

    fun setStartDate(date: LocalDate) {
        _uiState.value = _uiState.value.copy(startDate = date)
    }

    fun setEndDate(date: LocalDate) {
        _uiState.value = _uiState.value.copy(endDate = date)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearExportSuccess() {
        _uiState.value = _uiState.value.copy(exportSuccess = null)
    }

    fun loadHistory() {
        val state = _uiState.value
        if (state.selectedScheduleIds.isEmpty()) {
            _uiState.value = state.copy(error = "Please select at least one class")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val startStr = state.startDate.format(dateFormatter)
                val endStr = state.endDate.format(dateFormatter)

                // Fetch attendance records for each selected schedule in parallel
                val deferreds = state.selectedScheduleIds.map { scheduleId ->
                    async {
                        try {
                            val resp = apiService.getAttendanceRecords(
                                scheduleId = scheduleId,
                                startDate = startStr,
                                endDate = endStr,
                            )
                            if (resp.isSuccessful) {
                                resp.body() ?: emptyList()
                            } else {
                                emptyList()
                            }
                        } catch (_: Exception) {
                            emptyList<AttendanceRecordResponse>()
                        }
                    }
                }

                val allRecords = deferreds.awaitAll().flatten()

                // Group by date + scheduleId to form sessions
                val scheduleMap = state.schedules.associateBy { it.id }
                val sessions = allRecords
                    .groupBy { "${it.date}|${it.scheduleId}" }
                    .map { (key, records) ->
                        val parts = key.split("|")
                        val date = parts[0]
                        val scheduleId = parts.getOrElse(1) { "" }
                        val schedule = scheduleMap[scheduleId]
                        SessionSummary(
                            date = date,
                            scheduleId = scheduleId,
                            subjectCode = schedule?.subjectCode,
                            subjectName = schedule?.subjectName ?: "Unknown",
                            presentCount = records.count { it.status.equals("present", ignoreCase = true) },
                            lateCount = records.count { it.status.equals("late", ignoreCase = true) },
                            absentCount = records.count { it.status.equals("absent", ignoreCase = true) },
                            earlyLeaveCount = records.count { it.status.equals("early_leave", ignoreCase = true) },
                            records = records,
                        )
                    }
                    .sortedByDescending { it.date }

                val totalPresent = sessions.sumOf { it.presentCount }
                val totalLate = sessions.sumOf { it.lateCount }
                val totalAbsent = sessions.sumOf { it.absentCount }
                val totalStudentRecords = totalPresent + totalLate + totalAbsent + sessions.sumOf { it.earlyLeaveCount }
                val rate = if (totalStudentRecords > 0) {
                    (totalPresent + totalLate).toFloat() / totalStudentRecords.toFloat()
                } else 0f

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    hasLoaded = true,
                    sessions = sessions,
                    overallSummary = OverallSummary(
                        totalSessions = sessions.size,
                        totalPresent = totalPresent,
                        totalLate = totalLate,
                        totalAbsent = totalAbsent,
                        attendanceRate = rate,
                    ),
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load attendance history",
                )
            }
        }
    }

    fun exportPdf(context: Context) {
        val state = _uiState.value
        if (state.selectedScheduleIds.isEmpty()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isExporting = true, error = null)
            try {
                val scheduleIdsStr = state.selectedScheduleIds.joinToString(",")
                val startStr = state.startDate.format(dateFormatter)
                val endStr = state.endDate.format(dateFormatter)

                val response = apiService.exportAttendancePdf(
                    scheduleIds = scheduleIdsStr,
                    startDate = startStr,
                    endDate = endStr,
                )

                if (response.isSuccessful && response.body() != null) {
                    val fileName = "attendance_report_${startStr}_${endStr}.pdf"
                    val file = File(context.cacheDir, fileName)
                    response.body()!!.byteStream().use { inputStream ->
                        file.outputStream().use { outputStream ->
                            inputStream.copyTo(outputStream)
                        }
                    }

                    val uri = FileProvider.getUriForFile(
                        context,
                        "${context.packageName}.fileprovider",
                        file
                    )

                    val intent = Intent(Intent.ACTION_VIEW).apply {
                        setDataAndType(uri, "application/pdf")
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    context.startActivity(intent)

                    _uiState.value = _uiState.value.copy(
                        isExporting = false,
                        exportSuccess = "PDF exported successfully",
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isExporting = false,
                        error = "Failed to export PDF",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isExporting = false,
                    error = "Failed to export PDF: ${e.message}",
                )
            }
        }
    }
}
