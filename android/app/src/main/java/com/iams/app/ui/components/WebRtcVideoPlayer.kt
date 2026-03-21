package com.iams.app.ui.components

import android.annotation.SuppressLint
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.viewinterop.AndroidView

private const val TAG = "WebRtcPlayer"

/**
 * JS injected after page loads to monitor video state and force autoplay.
 * mediamtx's WHEP page creates a <video> element — this ensures it plays
 * even if the WebView's autoplay policy is stricter than a normal browser.
 */
private const val VIDEO_MONITOR_JS = """
(function() {
  function monitor() {
    var videos = document.querySelectorAll('video');
    videos.forEach(function(v) {
      if (v._mon) return;
      v._mon = true;
      console.log('Video element found, readyState=' + v.readyState + ' paused=' + v.paused);
      v.addEventListener('playing', function() { console.log('Video: playing'); });
      v.addEventListener('error', function() { console.log('Video: error code=' + (v.error ? v.error.code : '?')); });
      v.muted = true;
      v.play().catch(function(e) { console.log('Play attempt: ' + e); });
    });
  }
  monitor();
  setTimeout(monitor, 1000);
  setTimeout(monitor, 3000);
})();
"""

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun WebRtcVideoPlayer(
    whepUrl: String,
    modifier: Modifier = Modifier,
    onError: ((String) -> Unit)? = null
) {
    val webView = remember { mutableListOf<WebView?>(null) }

    DisposableEffect(Unit) {
        onDispose {
            webView[0]?.destroy()
            webView[0] = null
        }
    }

    AndroidView(
        factory = { context ->
            WebView(context).apply {
                webView[0] = this
                setBackgroundColor(Color.Black.toArgb())

                settings.apply {
                    javaScriptEnabled = true
                    mediaPlaybackRequiresUserGesture = false
                    mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                    domStorageEnabled = true
                }

                webChromeClient = object : WebChromeClient() {
                    override fun onPermissionRequest(request: PermissionRequest?) {
                        request?.grant(request.resources)
                        Log.i(TAG, "Granted WebRTC permissions: ${request?.resources?.joinToString()}")
                    }

                    override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                        consoleMessage?.let {
                            Log.d(TAG, "JS [${it.messageLevel()}] ${it.message()} (${it.sourceId()}:${it.lineNumber()})")
                        }
                        return true
                    }
                }

                webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView?, url: String?) {
                        Log.i(TAG, "Page loaded: $url")
                        view?.evaluateJavascript(VIDEO_MONITOR_JS, null)
                    }

                    override fun onReceivedError(
                        view: WebView?,
                        request: WebResourceRequest?,
                        error: WebResourceError?
                    ) {
                        if (request?.isForMainFrame == true) {
                            val msg = error?.description?.toString() ?: "WebView load failed"
                            Log.e(TAG, "Load error: $msg")
                            onError?.invoke(msg)
                        }
                    }
                }

                Log.i(TAG, "Loading WHEP player: $whepUrl")
                loadUrl(whepUrl)
            }
        },
        update = { view ->
            if (view.url != whepUrl) {
                Log.i(TAG, "Reloading WHEP player: $whepUrl")
                view.loadUrl(whepUrl)
            }
        },
        modifier = modifier
    )
}
