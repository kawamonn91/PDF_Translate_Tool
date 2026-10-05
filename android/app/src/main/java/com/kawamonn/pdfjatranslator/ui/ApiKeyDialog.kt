package com.kawamonn.pdfjatranslator.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.kawamonn.pdfjatranslator.settings.ApiKeyStore
import com.kawamonn.pdfjatranslator.translate.ClaudeTranslator
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val CONSOLE_URL = "https://console.anthropic.com/settings/keys"

/**
 * Claude API キーの登録画面。保存の前に、実際にAPIへ問い合わせて使えるかを確かめる。
 */
@Composable
fun ApiKeyDialog(onDismiss: () -> Unit, onSaved: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { ApiKeyStore(context) }
    var key by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = { if (!busy) onDismiss() },
        title = { Text("Claude APIキーの登録") },
        text = {
            Column {
                Text(
                    "翻訳には Claude API のキーが必要です。\n" +
                        "1. 下のボタンで Anthropic Console を開き、キーを作成します。\n" +
                        "2. 表示された sk-ant- で始まる文字列をコピーして、下の欄に貼り付けます。\n" +
                        "3. 「確認して保存」を押します。\n\n" +
                        "キーは、この端末の中で暗号化して保存されます。",
                )
                OutlinedButton(
                    onClick = {
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(CONSOLE_URL)))
                    },
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Text("Anthropic Console を開く")
                }
                OutlinedTextField(
                    value = key,
                    onValueChange = { key = it.trim() },
                    label = { Text("APIキー") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.padding(top = 8.dp),
                )
                message?.let { Text(it, modifier = Modifier.padding(top = 8.dp)) }
            }
        },
        confirmButton = {
            Button(
                enabled = !busy && key.startsWith("sk-ant-"),
                onClick = {
                    busy = true
                    message = "Claude API に接続して確かめています…"
                    scope.launch {
                        val result = runCatching {
                            withContext(Dispatchers.IO) {
                                val translated = ClaudeTranslator(key)
                                    .translate(listOf("test" to "Hello, this is a connection test."))
                                check(translated.isNotEmpty()) { "APIからの応答を読み取れませんでした" }
                            }
                        }
                        result.onSuccess {
                            withContext(Dispatchers.IO) { store.save(key) }
                            busy = false
                            onSaved()
                        }.onFailure { e ->
                            busy = false
                            message = "登録できませんでした: ${e.message ?: "原因不明のエラー"}"
                        }
                    }
                },
            ) {
                Text("確認して保存")
            }
        },
        dismissButton = {
            TextButton(onClick = { if (!busy) onDismiss() }) {
                Text("閉じる")
            }
        },
    )
}
