package com.iams.app.ui.faculty

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.model.AlertResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

enum class AlertFilter(val value: String, val label: String) {
    TODAY("today", "Today"),
    WEEK("week", "This Week"),
    ALL("all", "All"),
}

data class FacultyAlertsUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val alerts: List<AlertResponse> = emptyList(),
    val selectedFilter: AlertFilter = AlertFilter.TODAY,
    val isExporting: Boolean = false,
    val exportSuccess: String? = null,
)

@HiltViewModel
class FacultyAlertsViewModel @Inject constructor(
    private val apiService: ApiService,
    val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyAlertsUiState())
    val uiState: StateFlow<FacultyAlertsUiState> = _uiState.asStateFlow()

    init {
        loadAlerts()
    }

    fun loadAlerts(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            }
            try {
                val response = apiService.getAlerts(filter = _uiState.value.selectedFilter.value)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        alerts = response.body() ?: emptyList(),
                        isLoading = false,
                        isRefreshing = false,
                        error = null,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load alerts",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Unable to load alerts. Please try again.",
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadAlerts(silent = true)
    }

    fun selectFilter(filter: AlertFilter) {
        if (filter != _uiState.value.selectedFilter) {
            _uiState.value = _uiState.value.copy(selectedFilter = filter)
            loadAlerts()
        }
    }

    fun exportPdf(context: Context) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isExporting = true, error = null)
            try {
                val response = apiService.exportAlertsPdf(
                    filter = _uiState.value.selectedFilter.value,
                )

                if (response.isSuccessful && response.body() != null) {
                    val timestamp = System.currentTimeMillis()
                    val fileName = "alerts_report_${_uiState.value.selectedFilter.value}_${timestamp}.pdf"
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

    fun clearExportSuccess() {
        _uiState.value = _uiState.value.copy(exportSuccess = null)
    }
}
