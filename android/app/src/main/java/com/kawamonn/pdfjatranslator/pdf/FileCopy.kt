package com.kawamonn.pdfjatranslator.pdf

import android.content.Context
import android.net.Uri
import java.io.File

/** 受け取った PDF を、MuPDF が読める場所(キャッシュ)へコピーし、そのパスを返す */
fun copyToCache(context: Context, uri: Uri): String {
    val target = File(context.cacheDir, "input.pdf")
    context.contentResolver.openInputStream(uri)?.use { input ->
        target.outputStream().use { input.copyTo(it) }
    } ?: error("ファイルを読み込めませんでした")
    return target.absolutePath
}
