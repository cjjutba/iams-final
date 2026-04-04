package com.iams.app.webrtc

import android.util.Log
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.face.Face
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.webrtc.VideoFrame
import org.webrtc.VideoSink
import java.io.Closeable
import java.nio.ByteBuffer
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * Face detected by ML Kit on-device, with normalized bounding box.
 */
data class MlKitFace(
    val x1: Float,       // normalized 0..1
    val y1: Float,
    val x2: Float,
    val y2: Float,
    val faceId: Int?     // ML Kit tracking ID (stable across frames)
)

/**
 * Custom VideoSink that captures WebRTC frames and runs ML Kit face detection.
 *
 * Designed for dual-sink usage: attach to the same VideoTrack as SurfaceViewRenderer.
 * The video rendering thread is never blocked — frames are dropped when ML Kit is busy.
 *
 * Threading:
 * - onFrame() called on WebRTC decode thread → fast byte copy only (<1ms)
 * - ML Kit processing runs on a dedicated single-thread executor
 * - Results emitted via StateFlow on the executor thread (Compose collects on main)
 */
class MlKitFrameSink : VideoSink, Closeable {

    companion object {
        private const val TAG = "MlKitFrameSink"
    }

    private val executor = Executors.newSingleThreadExecutor()
    private val isProcessing = AtomicBoolean(false)
    private val frameCounter = AtomicInteger(0)

    // Process every Nth frame to reduce ML Kit load (2 = every other frame ≈ 15fps detection)
    private val processEveryN = 2

    private val faceDetector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
            .setContourMode(FaceDetectorOptions.CONTOUR_MODE_NONE)
            .setMinFaceSize(0.13f)
            .enableTracking()
            .build()
    )

    private val _faces = MutableStateFlow<List<MlKitFace>>(emptyList())
    val faces: StateFlow<List<MlKitFace>> = _faces.asStateFlow()

    /** Effective video dimensions after rotation (needed for aspect-fit overlay alignment). */
    private val _frameSize = MutableStateFlow(Pair(0, 0))
    val frameSize: StateFlow<Pair<Int, Int>> = _frameSize.asStateFlow()

    // Reusable NV21 buffer (allocated once per resolution)
    private var nv21Buffer: ByteArray? = null

    override fun onFrame(frame: VideoFrame) {
        // Skip frames to reduce ML Kit load — process every Nth frame only
        if (frameCounter.getAndIncrement() % processEveryN != 0) {
            return
        }

        // Drop frame if ML Kit is still processing the previous one
        if (!isProcessing.compareAndSet(false, true)) {
            return
        }

        // Retain the frame so it survives until we finish copying
        frame.retain()

        try {
            val i420 = frame.buffer.toI420() ?: run {
                frame.release()
                isProcessing.set(false)
                return
            }

            val width = i420.width
            val height = i420.height
            val rotation = frame.rotation

            // Ensure NV21 buffer is sized for this resolution
            val nv21Size = width * height * 3 / 2
            if (nv21Buffer == null || nv21Buffer!!.size != nv21Size) {
                nv21Buffer = ByteArray(nv21Size)
            }

            // Convert I420 → NV21 (fast byte copy, <1ms)
            i420ToNv21(i420, nv21Buffer!!, width, height)

            // Release WebRTC buffers immediately
            i420.release()
            frame.release()

            // Submit ML Kit processing to background executor
            val nv21 = nv21Buffer!!
            val w = width
            val h = height
            val rot = rotation
            executor.execute { processFrame(nv21, w, h, rot) }

        } catch (e: Exception) {
            Log.e(TAG, "Frame capture failed: ${e.message}")
            try { frame.release() } catch (_: Exception) {}
            isProcessing.set(false)
        }
    }

    private fun processFrame(nv21: ByteArray, width: Int, height: Int, rotation: Int) {
        try {
            // Compute effective dimensions after rotation (needed for normalization
            // and for the overlay to know the video aspect ratio)
            val (effW, effH) = if (rotation == 90 || rotation == 270) {
                height.toFloat() to width.toFloat()
            } else {
                width.toFloat() to height.toFloat()
            }

            // Publish immediately — overlay needs this even before ML Kit finishes
            _frameSize.value = Pair(effW.toInt(), effH.toInt())

            val inputImage = InputImage.fromByteArray(
                nv21, width, height, rotation, InputImage.IMAGE_FORMAT_NV21
            )

            faceDetector.process(inputImage)
                .addOnSuccessListener { faces ->
                    val validFaces = faces.filter { isValidFace(it) }

                    _faces.value = validFaces.map { face ->
                        val b = face.boundingBox
                        val x1 = (b.left / effW).coerceIn(0f, 1f)
                        val y1 = (b.top / effH).coerceIn(0f, 1f)
                        val x2 = (b.right / effW).coerceIn(0f, 1f)
                        val y2 = (b.bottom / effH).coerceIn(0f, 1f)

                        val mlFace = MlKitFace(
                            x1 = x1, y1 = y1, x2 = x2, y2 = y2,
                            faceId = face.trackingId
                        )
                        Log.d(TAG, "raw=${width}x${height} rot=$rotation eff=${effW.toInt()}x${effH.toInt()} face=[${b.left},${b.top},${b.right},${b.bottom}] norm=[${mlFace.x1},${mlFace.y1},${mlFace.x2},${mlFace.y2}]")
                        mlFace
                    }

                    isProcessing.set(false)
                }
                .addOnFailureListener { e ->
                    Log.w(TAG, "Face detection failed: ${e.message}")
                    isProcessing.set(false)
                }
        } catch (e: Exception) {
            Log.e(TAG, "processFrame error: ${e.message}")
            isProcessing.set(false)
        }
    }

    /**
     * Filters out false positive face detections using aspect ratio.
     * Valid faces are roughly square (0.5–1.5 width/height ratio).
     */
    private fun isValidFace(face: Face): Boolean {
        val b = face.boundingBox
        val width = b.width().toFloat()
        val height = b.height().toFloat()
        if (height <= 0f || width <= 0f) return false

        val aspectRatio = width / height
        return aspectRatio in 0.5f..1.5f
    }

    override fun close() {
        faceDetector.close()
        executor.shutdown()
        _faces.value = emptyList()
    }
}

// Converts I420 (YUV420 planar) to NV21 (YUV420 semi-planar).
// Stride-aware: handles decoder padding (e.g., stride 672 for width 640).
private fun i420ToNv21(
    i420: VideoFrame.I420Buffer,
    output: ByteArray,
    width: Int,
    height: Int
) {
    val yPlane = i420.dataY
    val uPlane = i420.dataU
    val vPlane = i420.dataV
    val yStride = i420.strideY
    val uStride = i420.strideU
    val vStride = i420.strideV

    val chromaWidth = width / 2
    val chromaHeight = height / 2

    // Copy Y plane (row by row to handle stride padding)
    var yOffset = 0
    for (row in 0 until height) {
        yPlane.position(row * yStride)
        yPlane.get(output, yOffset, width)
        yOffset += width
    }

    // Interleave V and U into NV21 chroma section
    var chromaOffset = width * height
    for (row in 0 until chromaHeight) {
        val uRowStart = row * uStride
        val vRowStart = row * vStride
        for (col in 0 until chromaWidth) {
            output[chromaOffset++] = vPlane.get(vRowStart + col)  // V first (NV21)
            output[chromaOffset++] = uPlane.get(uRowStart + col)  // then U
        }
    }
}
