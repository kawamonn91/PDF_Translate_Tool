package com.kawamonn.pdfjatranslator.pdf

import android.content.Context
import android.net.Uri
import java.io.File

/**
 * 受け取った PDF を、MuPDF が読める場所へコピーし、そのパスを返す。
 * キャッシュは端末の空き容量が少ないと消されるため、作業中のファイルは保存領域に置く
 */
fun copyToCache(context: Context, uri: Uri): String {
    val target = File(context.filesDir, "input.pdf")
    context.contentResolver.openInputStream(uri)?.use { input ->
        target.outputStream().use { input.copyTo(it) }
    } ?: error("ファイルを読み込めませんでした")
    return target.absolutePath
}
