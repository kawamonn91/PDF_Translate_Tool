package com.kawamonn.pdfjatranslator.translate

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.addJsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

class ClaudeApiException(val status: Int, message: String) : IOException(message)

/**
 * Claude API で英日翻訳する。PC版(ja_translator/translate.py)と同じ指示文と、同じ入出力(ID で対応付け)を使う。
 */
class ClaudeTranslator(
    private val apiKey: String,
    private val model: String = DEFAULT_MODEL,
    private val client: OkHttpClient = OkHttpClient(),
) {
    /** (ID, 原文) の列を受け取り、ID -> 訳文 を返す。返らなかった ID は含まれない */
    suspend fun translate(items: List<Pair<String, String>>): Map<String, String> = withContext(Dispatchers.IO) {
        val result = linkedMapOf<String, String>()
        for (batch in batches(items)) {
            var remaining = batch
            repeat(MAX_RETRIES + 1) {
                if (remaining.isEmpty()) return@repeat
                val got = callOnce(remaining)
                result.putAll(got)
                remaining = remaining.filter { it.first !in got }
            }
        }
        result
    }

    private fun callOnce(batch: List<Pair<String, String>>): Map<String, String> {
        val payload = JsonArray(
            batch.map { (id, text) -> buildJsonObject { put("id", id); put("text", text) } },
        )
        val userText = "次の英文を日本語に訳してください。\n\n" + payload.toString()
        val body = buildJsonObject {
            put("model", model)
            put("max_tokens", 8000)
            put("system", SYSTEM_PROMPT)
            putJsonArray("messages") {
                addJsonObject {
                    put("role", "user")
                    put("content", userText)
                }
            }
        }.toString()

        val request = Request.Builder()
            .url(ENDPOINT)
            .header("x-api-key", apiKey)
            .header("anthropic-version", "2023-06-01")
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()

        client.newCall(request).execute().use { response ->
            val text = response.body.string()
            if (!response.isSuccessful) {
                throw ClaudeApiException(response.code, errorMessage(text) ?: "Claude API がエラーを返しました (${response.code})")
            }
            val root = Json.parseToJsonElement(text).jsonObject
            val reply = root["content"]?.jsonArray.orEmpty()
                .mapNotNull { block -> (block as? JsonObject)?.get("text")?.jsonPrimitive?.content }
                .joinToString("")
            val wanted = batch.map { it.first }.toSet()
            return parseTranslations(reply).filterKeys { it in wanted }
        }
    }

    companion object {
        const val DEFAULT_MODEL = "claude-sonnet-5-5"
        private const val ENDPOINT = "https://api.anthropic.com/v1/messages"
        private const val BATCH_CHARS = 5000
        private const val MAX_RETRIES = 2

        private val SYSTEM_PROMPT = """
            あなたは英日翻訳の専門家です。PDFやスライドの画面上の文言を日本語に訳します。

            守ること:
            - 訳文は元の文と同じ役割(見出し・箇条書き・ラベル・本文)が分かる自然な日本語にする
            - 元の文字数より大きく増えないよう、簡潔にまとめる(レイアウトの枠に収めるため)
            - 数字・単位・記号・固有名詞(製品名・人名・会社名)・URL・メールアドレスは変えない
            - 専門用語は一般的な日本語訳を使う
            - 入力の "id" と出力の "id" を一致させ、欠けた項目を作らない

            出力は JSON 配列のみ。説明文やコードブロックは付けない。
            形式: [{"id": "...", "ja": "訳文"}]
        """.trimIndent()

        internal fun batches(items: List<Pair<String, String>>): List<List<Pair<String, String>>> {
            val batches = mutableListOf<List<Pair<String, String>>>()
            var current = mutableListOf<Pair<String, String>>()
            var size = 0
            for (item in items) {
                if (current.isNotEmpty() && size + item.second.length > BATCH_CHARS) {
                    batches += current
                    current = mutableListOf()
                    size = 0
                }
                current += item
                size += item.second.length
            }
            if (current.isNotEmpty()) batches += current
            return batches
        }

        internal fun parseTranslations(reply: String): Map<String, String> {
            val start = reply.indexOf('[')
            val end = reply.lastIndexOf(']')
            if (start < 0 || end < start) return emptyMap()
            val array = runCatching { Json.parseToJsonElement(reply.substring(start, end + 1)).jsonArray }
                .getOrNull() ?: return emptyMap()
            val out = linkedMapOf<String, String>()
            for (element in array) {
                val obj = element as? JsonObject ?: continue
                val id = obj["id"]?.jsonPrimitive?.content ?: continue
                val ja = obj["ja"]?.jsonPrimitive?.content?.trim() ?: continue
                if (ja.isNotEmpty()) out[id] = ja
            }
            return out
        }

        private fun errorMessage(body: String): String? = runCatching {
            Json.parseToJsonElement(body).jsonObject["error"]?.jsonObject?.get("message")?.jsonPrimitive?.content
        }.getOrNull()
    }
}
