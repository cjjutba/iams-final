package com.iams.app.ui.components

import android.graphics.RectF
import android.view.TextureView
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.atomic.AtomicBoolean

data class DetectedFaceLocal(
    val boundingBox: RectF,  // normalized 0-1
    val trackingId: Int?,
)

class FaceDetectionProcessor {
    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .enableTracking()
            .setMinFaceSize(0.1f)
            .build()
    )

    private val _detectedFaces = MutableStateFlow<List<DetectedFaceLocal>>(emptyList())
    val detectedFaces = _detectedFaces.asStateFlow()

    private val isProcessing = AtomicBoolean(false)

    fun processFrame(textureView: TextureView) {
        if (!isProcessing.compareAndSet(false, true)) return
        val bitmap = textureView.bitmap ?: run { isProcessing.set(false); return }
        val image = InputImage.fromBitmap(bitmap, 0)

        detector.process(image)
            .addOnSuccessListener { faces ->
                val w = bitmap.width.toFloat()
                val h = bitmap.height.toFloat()
                _detectedFaces.value = faces.map { face ->
                    DetectedFaceLocal(
                        boundingBox = RectF(
                            face.boundingBox.left / w,
                            face.boundingBox.top / h,
                            face.boundingBox.right / w,
                            face.boundingBox.bottom / h
                        ),
                        trackingId = face.trackingId
                    )
                }
                bitmap.recycle()
                isProcessing.set(false)
            }
            .addOnFailureListener {
                bitmap.recycle()
                isProcessing.set(false)
            }
    }

    fun close() {
        detector.close()
    }
}
