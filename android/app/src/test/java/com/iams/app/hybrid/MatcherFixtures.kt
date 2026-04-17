package com.iams.app.hybrid

import com.iams.app.data.model.TrackInfo
import com.iams.app.webrtc.MlKitFace

internal fun mlkit(id: Int?, x1: Float, y1: Float, x2: Float, y2: Float): MlKitFace =
    MlKitFace(x1 = x1, y1 = y1, x2 = x2, y2 = y2, faceId = id)

internal fun backend(
    trackId: Int,
    x1: Float, y1: Float, x2: Float, y2: Float,
    name: String? = null,
    status: String = "pending",
    userId: String? = null,
    confidence: Float = 0f,
): TrackInfo = TrackInfo(
    trackId = trackId,
    bbox = listOf(x1, y1, x2, y2),
    velocity = listOf(0f, 0f, 0f, 0f),
    name = name,
    confidence = confidence,
    userId = userId,
    status = status,
)

internal class FakeClock(private var now: Long = 0L) : () -> Long {
    override fun invoke(): Long = now
    fun advanceMs(ms: Long) { now += ms * 1_000_000L }
    fun advanceNs(ns: Long) { now += ns }
    fun setMs(ms: Long) { now = ms * 1_000_000L }
}
