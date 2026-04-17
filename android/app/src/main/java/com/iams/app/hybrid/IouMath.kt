package com.iams.app.hybrid

/** IoU between two normalized [x1,y1,x2,y2] boxes. Returns 0f if either has zero area. */
fun iou(a: FloatArray, b: FloatArray): Float =
    iou(a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3])

/** IoU between [x1,y1,x2,y2] scalars (avoids array alloc on hot path). */
fun iou(
    ax1: Float, ay1: Float, ax2: Float, ay2: Float,
    bx1: Float, by1: Float, bx2: Float, by2: Float,
): Float {
    val areaA = (ax2 - ax1) * (ay2 - ay1)
    val areaB = (bx2 - bx1) * (by2 - by1)
    if (areaA <= 0f || areaB <= 0f) return 0f

    val ix1 = if (ax1 > bx1) ax1 else bx1
    val iy1 = if (ay1 > by1) ay1 else by1
    val ix2 = if (ax2 < bx2) ax2 else bx2
    val iy2 = if (ay2 < by2) ay2 else by2

    val iw = ix2 - ix1
    val ih = iy2 - iy1
    if (iw <= 0f || ih <= 0f) return 0f

    val intersection = iw * ih
    val union = areaA + areaB - intersection
    return if (union <= 0f) 0f else intersection / union
}
