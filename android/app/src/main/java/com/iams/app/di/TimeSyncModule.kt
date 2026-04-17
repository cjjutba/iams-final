package com.iams.app.di

import com.iams.app.data.sync.DefaultTimeSyncClient
import com.iams.app.data.sync.TimeSyncClient
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class TimeSyncModule {
    @Binds
    @Singleton
    abstract fun bindTimeSyncClient(impl: DefaultTimeSyncClient): TimeSyncClient
}
