package com.iams.app.data.api

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
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

    val accessToken get() = runBlocking {
        context.dataStore.data.map { it[ACCESS_TOKEN] }.first()
    }
    val refreshToken get() = runBlocking {
        context.dataStore.data.map { it[REFRESH_TOKEN] }.first()
    }
    val userRole get() = runBlocking {
        context.dataStore.data.map { it[USER_ROLE] }.first()
    }
    val userId get() = runBlocking {
        context.dataStore.data.map { it[USER_ID] }.first()
    }

    suspend fun saveTokens(access: String, refresh: String, role: String, userId: String) {
        isLoggingOut = false
        context.dataStore.edit {
            it[ACCESS_TOKEN] = access
            it[REFRESH_TOKEN] = refresh
            it[USER_ROLE] = role
            it[USER_ID] = userId
        }
    }

    suspend fun clearTokens() {
        context.dataStore.edit { it.clear() }
    }
}
