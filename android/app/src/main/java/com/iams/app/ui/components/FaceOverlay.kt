package com.iams.app.ui.components

import android.graphics.RectF
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.sp
import com.iams.app.data.model.Detection

@Composable
fun FaceOverlay(
    localFaces: List<DetectedFaceLocal>,
    recognitions: List<Detection>,
    modifier: Modifier = Modifier
) {
    Canvas(modifier = modifier.fillMaxSize()) {
        val canvasW = size.width
        val canvasH = size.height

        for (face in localFaces) {
            val left = face.boundingBox.left * canvasW
            val top = face.boundingBox.top * canvasH
            val right = face.boundingBox.right * canvasW
            val bottom = face.boundingBox.bottom * canvasH

            // Draw bounding box
            drawRect(
                color = Color.Green,
                topLeft = Offset(left, top),
                size = Size(right - left, bottom - top),
                style = Stroke(width = 3f)
            )

            // Find matching name via IoU
            val matchedName = findMatchingName(face.boundingBox, recognitions)
            if (matchedName != null) {
                // Draw name label background
                drawRect(
                    color = Color.Black.copy(alpha = 0.6f),
                    topLeft = Offset(left, top - 40f),
                    size = Size(right - left, 36f)
                )
                // Draw name text
                drawContext.canvas.nativeCanvas.drawText(
                    matchedName,
                    left + 4f,
                    top - 12f,
                    android.graphics.Paint().apply {
                        color = android.graphics.Color.GREEN
                        textSize = 13.sp.toPx()
                        isAntiAlias = true
                    }
                )
            }
        }
    }
}

private fun findMatchingName(faceBox: RectF, recognitions: List<Detection>): String? {
    var bestMatch: Detection? = null
    var bestIoU = 0f
    for (rec in recognitions) {
        if (rec.bbox.size < 4) continue
        val recBox = RectF(rec.bbox[0], rec.bbox[1], rec.bbox[2], rec.bbox[3])
        val iou = calculateIoU(faceBox, recBox)
        if (iou > bestIoU && iou > 0.2f) {
            bestIoU = iou
            bestMatch = rec
        }
    }
    return bestMatch?.name
}

private fun calculateIoU(a: RectF, b: RectF): Float {
    val interLeft = maxOf(a.left, b.left)
    val interTop = maxOf(a.top, b.top)
    val interRight = minOf(a.right, b.right)
    val interBottom = minOf(a.bottom, b.bottom)
    if (interRight <= interLeft || interBottom <= interTop) return 0f
    val interArea = (interRight - interLeft) * (interBottom - interTop)
    val aArea = (a.right - a.left) * (a.bottom - a.top)
    val bArea = (b.right - b.left) * (b.bottom - b.top)
    return interArea / (aArea + bArea - interArea)
}
