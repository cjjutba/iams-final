package com.iams.app.ui.navigation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.api.TokenManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class NavViewModel @Inject constructor(
    val tokenManager: TokenManager,
    val notificationService: NotificationService,
    private val apiService: ApiService,
) : ViewModel() {

    init {
        // If the user is already authenticated, connect the notification WS
        // and fetch the initial unread count from REST
        if (tokenManager.accessToken != null) {
            notificationService.connect()

            viewModelScope.launch {
                notificationService.fetchUnreadCount(apiService)
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        notificationService.disconnect()
    }
}
