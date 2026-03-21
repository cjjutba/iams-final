package com.iams.app.webrtc

sealed interface WhepConnectionState {
    data object Disconnected : WhepConnectionState
    data object Connecting : WhepConnectionState
    data object Connected : WhepConnectionState
    data object Reconnecting : WhepConnectionState
    data class Failed(val reason: String) : WhepConnectionState
}
