package com.iams.app.data.api

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore("auth")

@Singleton
class TokenManager @Inject constructor(@ApplicationContext private val context: Context) {
    private val ACCESS_TOKEN = stringPreferencesKey("access_token")
    private val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
    private val USER_ROLE = stringPreferencesKey("user_role")
    private val USER_ID = stringPreferencesKey("user_id")

    /** Set to true during logout to prevent TokenAuthenticator from refreshing. */
    @Volatile
    var isLoggingOut: Boolean = false

    @Volatile
    private var _accessToken: String? = null
    @Volatile
    private var _refreshToken: String? = null
    @Volatile
    private var _userRole: String? = null
    @Volatile
    private var _userId: String? = null

    init {
        CoroutineScope(Dispatchers.IO + SupervisorJob()).launch {
            val prefs = context.dataStore.data.first()
            _accessToken = prefs[ACCESS_TOKEN]
            _refreshToken = prefs[REFRESH_TOKEN]
            _userRole = prefs[USER_ROLE]
            _userId = prefs[USER_ID]
        }
    }

    val accessToken: String? get() = _accessToken
    val refreshToken: String? get() = _refreshToken
    val userRole: String? get() = _userRole
    val userId: String? get() = _userId

    suspend fun saveTokens(access: String, refresh: String, role: String, userId: String) {
        isLoggingOut = false
        _accessToken = access
        _refreshToken = refresh
        _userRole = role
        _userId = userId
        context.dataStore.edit {
            it[ACCESS_TOKEN] = access
            it[REFRESH_TOKEN] = refresh
            it[USER_ROLE] = role
            it[USER_ID] = userId
        }
    }

    suspend fun clearTokens() {
        _accessToken = null
        _refreshToken = null
        _userRole = null
        _userId = null
        context.dataStore.edit { it.clear() }
    }
}
