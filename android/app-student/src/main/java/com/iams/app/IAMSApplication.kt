package com.iams.app

import android.app.Application
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import coil.ImageLoader
import coil.ImageLoaderFactory
import com.iams.app.data.api.NotificationService
import com.iams.app.data.api.TokenManager
import dagger.hilt.android.HiltAndroidApp
import okhttp3.OkHttpClient
import javax.inject.Inject

@HiltAndroidApp
class IAMSApplication : Application(), ImageLoaderFactory {

    @Inject lateinit var notificationService: NotificationService
    @Inject lateinit var tokenManager: TokenManager
    // Reuse the Retrofit-bound client so authed image fetches go through
    // the same AuthInterceptor + TokenAuthenticator (= refresh-on-401).
    // Without this, AsyncImage requests to /api/v1/face/registrations/.../images
    // arrive without a Bearer header and return 401.
    @Inject lateinit var okHttpClient: OkHttpClient

    override fun onCreate() {
        super.onCreate()

        // OkHttp WebSockets are killed within minutes of backgrounding on
        // Android. Accept that and reconnect on foreground instead of
        // fighting Doze with a foreground service. If the user isn't
        // logged in yet the reconnect is a no-op (userId null).
        ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) {
                if (!tokenManager.userId.isNullOrBlank()) {
                    notificationService.connect()
                }
            }
        })
    }

    // Coil pulls this on first ImageLoader access and caches the result for
    // the rest of the process. Sharing the Retrofit OkHttpClient gives every
    // AsyncImage call in the app the bearer token + auto-refresh path for free.
    override fun newImageLoader(): ImageLoader {
        return ImageLoader.Builder(this)
            .okHttpClient(okHttpClient)
            .crossfade(true)
            .build()
    }
}
