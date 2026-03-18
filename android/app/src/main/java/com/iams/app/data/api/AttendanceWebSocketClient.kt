package com.iams.app.data.api

import com.google.gson.Gson
import com.iams.app.data.model.Detection
import com.iams.app.data.model.ScanResultMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

class AttendanceWebSocketClient(private val baseUrl: String) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    private val gson = Gson()
    private var targetScheduleId: String? = null

    private val _scanResults = MutableStateFlow<ScanResultMessage?>(null)
    val scanResults = _scanResults.asStateFlow()

    private val _detections = MutableStateFlow<List<Detection>>(emptyList())
    val detections = _detections.asStateFlow()

    private val _isConnected = MutableStateFlow(false)
    val isConnected = _isConnected.asStateFlow()

    fun connect(scheduleId: String) {
        targetScheduleId = scheduleId
        val request = Request.Builder()
            .url("$baseUrl/attendance/$scheduleId")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                _isConnected.value = true
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (text == "pong") return
                try {
                    val msg = gson.fromJson(text, ScanResultMessage::class.java)
                    if (msg.type == "scan_result") {
                        _scanResults.value = msg
                        _detections.value = msg.detections
                    }
                } catch (_: Exception) {}
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                _isConnected.value = false
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                _isConnected.value = false
                // Auto-reconnect after 3s
                Thread {
                    Thread.sleep(3000)
                    targetScheduleId?.let { connect(it) }
                }.start()
            }
        })
    }

    fun disconnect() {
        targetScheduleId = null
        webSocket?.close(1000, "Closing")
        webSocket = null
        _isConnected.value = false
    }
}
