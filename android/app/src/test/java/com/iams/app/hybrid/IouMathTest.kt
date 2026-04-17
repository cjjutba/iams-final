package com.iams.app.hybrid

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class IouMathTest {

    @Test
    fun identicalBoxesYieldIouOne() {
        val a = floatArrayOf(0.1f, 0.1f, 0.3f, 0.3f)
        val b = floatArrayOf(0.1f, 0.1f, 0.3f, 0.3f)
        assertThat(iou(a, b)).isWithin(EPS).of(1.0f)
    }

    @Test
    fun disjointBoxesYieldIouZero() {
        val a = floatArrayOf(0.0f, 0.0f, 0.2f, 0.2f)
        val b = floatArrayOf(0.5f, 0.5f, 0.7f, 0.7f)
        assertThat(iou(a, b)).isWithin(EPS).of(0.0f)
    }

    @Test
    fun halfOverlapYieldsOneThird() {
        // Two 1×1 boxes offset by 0.5 on X → intersection 0.5, union 1.5, IoU=1/3.
        val a = floatArrayOf(0.0f, 0.0f, 1.0f, 1.0f)
        val b = floatArrayOf(0.5f, 0.0f, 1.5f, 1.0f)
        assertThat(iou(a, b)).isWithin(EPS).of(1.0f / 3.0f)
    }

    @Test
    fun zeroAreaFirstBoxYieldsZero() {
        val a = floatArrayOf(0.5f, 0.5f, 0.5f, 0.8f) // width = 0
        val b = floatArrayOf(0.0f, 0.0f, 1.0f, 1.0f)
        assertThat(iou(a, b)).isEqualTo(0.0f)
    }

    @Test
    fun zeroAreaSecondBoxYieldsZero() {
        val a = floatArrayOf(0.0f, 0.0f, 1.0f, 1.0f)
        val b = floatArrayOf(0.3f, 0.3f, 0.6f, 0.3f) // height = 0
        assertThat(iou(a, b)).isEqualTo(0.0f)
    }

    @Test
    fun scalarOverloadMatchesArrayOverload() {
        val a = floatArrayOf(0.1f, 0.2f, 0.4f, 0.5f)
        val b = floatArrayOf(0.3f, 0.3f, 0.6f, 0.7f)
        val arrResult = iou(a, b)
        val scalarResult = iou(a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3])
        assertThat(scalarResult).isWithin(EPS).of(arrResult)
    }

    @Test
    fun touchingBoxesYieldIouZero() {
        // Right edge of A meets left edge of B — zero-area intersection.
        val a = floatArrayOf(0.0f, 0.0f, 0.5f, 0.5f)
        val b = floatArrayOf(0.5f, 0.0f, 1.0f, 0.5f)
        assertThat(iou(a, b)).isEqualTo(0.0f)
    }

    private companion object {
        const val EPS = 1e-5f
    }
}
