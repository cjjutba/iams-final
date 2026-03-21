package com.iams.app.data.api

import com.iams.app.BuildConfig
import com.iams.app.data.model.RefreshRequest
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import javax.inject.Inject
import javax.inject.Singleton

/**
 * OkHttp Authenticator that automatically refreshes expired JWT tokens.
 * Only called on 401 responses — retries the original request with the new token.
 * If refresh fails, clears tokens so the UI redirects to login.
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokenManager: TokenManager
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        // Don't refresh during logout
        if (tokenManager.isLoggingOut) return null

        // Don't retry if we've already tried refreshing (prevent infinite loop)
        if (response.request.header("X-Token-Refreshed") != null) {
            runBlocking { tokenManager.clearTokens() }
            return null
        }

        val refreshToken = tokenManager.refreshToken ?: run {
            runBlocking { tokenManager.clearTokens() }
            return null
        }

        // Use a separate Retrofit instance to avoid circular dependency
        val freshTokens = runBlocking {
            try {
                val baseUrl = "http://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}/api/v1/"
                val tempApi = Retrofit.Builder()
                    .baseUrl(baseUrl)
                    .client(OkHttpClient.Builder().build())
                    .addConverterFactory(GsonConverterFactory.create())
                    .build()
                    .create(ApiService::class.java)

                val result = tempApi.refreshToken(RefreshRequest(refreshToken))
                if (result.isSuccessful) result.body() else null
            } catch (_: Exception) {
                null
            }
        }

        return try {
            if (freshTokens?.accessToken != null && freshTokens.user != null) {
                runBlocking {
                    tokenManager.saveTokens(
                        access = freshTokens.accessToken,
                        refresh = freshTokens.refreshToken,
                        role = freshTokens.user.role,
                        userId = freshTokens.user.id
                    )
                }
                // Retry the original request with the new token
                response.request.newBuilder()
                    .header("Authorization", "Bearer ${freshTokens.accessToken}")
                    .header("X-Token-Refreshed", "true")
                    .build()
            } else {
                // Refresh failed — clear tokens so UI navigates to login
                runBlocking { tokenManager.clearTokens() }
                null
            }
        } catch (_: Exception) {
            runBlocking { tokenManager.clearTokens() }
            null
        }
    }
}
