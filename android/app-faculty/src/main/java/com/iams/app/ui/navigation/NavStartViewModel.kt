package com.iams.app.ui.navigation

import androidx.lifecycle.ViewModel
import com.iams.app.data.api.TokenManager
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

/**
 * Lightweight ViewModel used by [FacultyNavHost] to decide the start
 * destination (already-authenticated → schedules, otherwise → login).
 *
 * Exists because Hilt's `hiltViewModel()` is the cleanest way to inject
 * a [TokenManager] into a `@Composable` without wrapping in an `EntryPoint`.
 */
@HiltViewModel
class NavStartViewModel @Inject constructor(
    val tokenManager: TokenManager,
) : ViewModel()
