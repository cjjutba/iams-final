package com.iams.app.ui.navigation

import androidx.lifecycle.ViewModel
import com.iams.app.data.api.TokenManager
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class NavViewModel @Inject constructor(
    val tokenManager: TokenManager
) : ViewModel()
