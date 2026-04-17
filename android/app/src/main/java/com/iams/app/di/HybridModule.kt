package com.iams.app.di

import com.iams.app.hybrid.DefaultFaceIdentityMatcher
import com.iams.app.hybrid.FaceIdentityMatcher
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.components.ViewModelComponent
import dagger.hilt.android.scopes.ViewModelScoped

/**
 * Hilt bindings for the hybrid detection rollout (master-plan §5.2).
 *
 * The matcher holds per-session mutable state (sticky bindings, identity hold)
 * so it MUST be scoped to the Live Feed ViewModel, NOT @Singleton. A fresh
 * instance is created each time the faculty opens a live feed.
 */
@Module
@InstallIn(ViewModelComponent::class)
object HybridModule {

    @Provides
    @ViewModelScoped
    fun provideFaceIdentityMatcher(): FaceIdentityMatcher = DefaultFaceIdentityMatcher()
}
