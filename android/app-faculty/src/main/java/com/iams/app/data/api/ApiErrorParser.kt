package com.iams.app.data.api

import org.json.JSONArray
import org.json.JSONObject
import retrofit2.Response

/**
 * Converts FastAPI error payloads into user-facing messages.
 *
 * FastAPI returns two distinct error shapes:
 *   - [HTTPException]   → {"detail": "some string"}
 *   - [RequestValidationError] → {"detail": [{"loc":[...], "msg":"...", "type":"..."}, ...]}
 *
 * Retrofit responses can also be plain-text or HTML (e.g. from a reverse
 * proxy 502), so we fall back to trimmed raw text when JSON parsing fails
 * and finally to a generic per-status-code message.
 */
object ApiErrorParser {

    /**
     * Build a human-friendly error message from a failed Retrofit [response].
     * [fallback] is used when every extraction strategy fails.
     */
    fun parse(response: Response<*>, fallback: String = "Something went wrong. Please try again."): String {
        val rawBody = runCatching { response.errorBody()?.string() }.getOrNull().orEmpty()
        val fromBody = parseBody(rawBody)
        if (!fromBody.isNullOrBlank()) return fromBody
        return messageForStatus(response.code(), fallback)
    }

    /**
     * Extract a readable message from an arbitrary error-body string. Returns
     * null if nothing usable could be extracted (caller should fall back).
     */
    fun parseBody(body: String?): String? {
        val trimmed = body?.trim().orEmpty()
        if (trimmed.isEmpty()) return null

        // Attempt JSON parsing — FastAPI always responds with JSON on 4xx/5xx.
        val parsed = runCatching { JSONObject(trimmed) }.getOrNull()
        if (parsed != null) {
            val detail = parsed.opt("detail")
            when (detail) {
                is String -> return detail.takeIf { it.isNotBlank() }
                is JSONArray -> return formatValidationErrors(detail)
                is JSONObject -> {
                    // Nested detail objects are unusual but possible.
                    detail.optString("msg").takeIf { it.isNotBlank() }?.let { return it }
                }
            }
            // IAMS custom exception envelope:
            //   {"success": false, "error": {"code": "...", "message": "..."}}
            // Drill into the nested error.message before the flat-key fallback.
            val errorObj = parsed.optJSONObject("error")
            if (errorObj != null) {
                listOf("message", "msg", "detail").forEach { key ->
                    val value = errorObj.optString(key)
                    if (value.isNotBlank()) return value
                }
            }
            // Flat services using {"message": "..."} or {"error": "..."} as a string.
            listOf("message", "error", "errorMessage").forEach { key ->
                val value = parsed.optString(key)
                if (value.isNotBlank()) return value
            }
        }

        // JSON parse failed — return trimmed plain text if it's short enough
        // to be a meaningful message rather than an HTML dump.
        return if (trimmed.length in 1..200 && !looksLikeHtml(trimmed)) trimmed else null
    }

    private fun formatValidationErrors(array: JSONArray): String? {
        if (array.length() == 0) return null
        val messages = mutableListOf<String>()
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            val msg = item.optString("msg").trim()
            if (msg.isBlank()) continue
            val field = extractFieldName(item.optJSONArray("loc"))
            messages += if (field != null) "$field: ${humanize(msg)}" else humanize(msg)
        }
        return messages.distinct().joinToString(separator = "\n").ifBlank { null }
    }

    private fun extractFieldName(loc: JSONArray?): String? {
        if (loc == null || loc.length() == 0) return null
        // loc is typically ["body", "<field>"] — take the last non-"body" element.
        for (i in (loc.length() - 1) downTo 0) {
            val part = loc.optString(i)
            if (part.isNotBlank() && part != "body") {
                return part.replace('_', ' ').replaceFirstChar { it.uppercase() }
            }
        }
        return null
    }

    /**
     * Pydantic error messages often start with a lowercase "ensure" / "value"
     * / "string" prefix. Normalize to sentence-case and strip noisy prefixes.
     */
    private fun humanize(message: String): String {
        val cleaned = message
            .removePrefix("ensure this value ")
            .removePrefix("value ")
            .trim()
            .replaceFirstChar { it.uppercase() }
        return cleaned.trimEnd('.') + "."
    }

    private fun looksLikeHtml(text: String): Boolean {
        val head = text.take(40).lowercase()
        return head.startsWith("<!doctype") || head.startsWith("<html") || head.startsWith("<?xml")
    }

    private fun messageForStatus(code: Int, fallback: String): String = when (code) {
        400 -> "The request was invalid. Please review your details."
        401 -> "Your session has expired. Please sign in again."
        403 -> "You don't have permission to perform this action."
        404 -> "We couldn't find what you're looking for."
        408 -> "The request timed out. Please try again."
        409 -> "This record already exists."
        413 -> "The file you sent is too large."
        422 -> "Some of the information you entered is invalid."
        429 -> "Too many attempts. Please wait a moment and try again."
        in 500..599 -> "The server is having trouble right now. Please try again in a moment."
        else -> fallback
    }
}
