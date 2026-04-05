package com.iams.app.ui.onboarding

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.ViewModel
import com.iams.app.data.api.TokenManager
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject

private val Context.onboardingDataStore by preferencesDataStore("onboarding")

@HiltViewModel
class SplashViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    val tokenManager: TokenManager,
) : ViewModel() {

    companion object {
        private val ONBOARDING_COMPLETE = booleanPreferencesKey("onboarding_complete")
    }

    suspend fun isOnboardingComplete(): Boolean {
        return context.onboardingDataStore.data
            .map { it[ONBOARDING_COMPLETE] ?: false }
            .first()
    }

    suspend fun setOnboardingComplete() {
        context.onboardingDataStore.edit {
            it[ONBOARDING_COMPLETE] = true
        }
    }

    fun hasTokens(): Boolean = tokenManager.accessToken != null

    fun userRole(): String? = tokenManager.userRole
}
