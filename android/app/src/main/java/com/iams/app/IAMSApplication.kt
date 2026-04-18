package com.iams.app

import android.app.Application
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import com.iams.app.data.api.NotificationService
import com.iams.app.data.api.TokenManager
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class IAMSApplication : Application() {

    @Inject lateinit var notificationService: NotificationService
    @Inject lateinit var tokenManager: TokenManager

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
}
