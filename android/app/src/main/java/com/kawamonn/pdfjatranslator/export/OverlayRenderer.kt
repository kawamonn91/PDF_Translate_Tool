package com.kawamonn.pdfjatranslator.export

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import com.kawamonn.pdfjatranslator.ui.TranslatedParagraph

private const val MIN_FONT_PT = 5f

/**
 * ページの画像の上に、訳文を元の位置へ描き込む。
 * 元の文字は白い下地で隠し、訳文は枠に収まるまで小さくする。
 */
fun drawTranslations(bitmap: Bitmap, paragraphs: List<TranslatedParagraph>, pageWidthPt: Float) {
    if (paragraphs.isEmpty()) return
    val canvas = Canvas(bitmap)
    val pxPerPt = bitmap.width / pageWidthPt
    val background = Paint().apply { color = Color.WHITE; style = Paint.Style.FILL }

    for (item in paragraphs) {
        val left = item.left * pxPerPt
        val top = item.top * pxPerPt
        val width = (item.right - item.left) * pxPerPt
        val height = (item.bottom - item.top) * pxPerPt
        canvas.drawRect(left, top, left + width, top + height, background)

        val maxWidth = width.toInt().coerceAtLeast(1)
        var size = item.fontSize * pxPerPt
        val minSize = MIN_FONT_PT * pxPerPt
        var layout = layoutFor(item.ja, size, maxWidth)
        while (layout.height > height && size > minSize) {
            size -= 0.5f * pxPerPt
            layout = layoutFor(item.ja, size, maxWidth)
        }

        canvas.save()
        canvas.translate(left, top)
        layout.draw(canvas)
        canvas.restore()
    }
}

private fun layoutFor(text: String, textSizePx: Float, width: Int): StaticLayout {
    val paint = TextPaint().apply {
        isAntiAlias = true
        color = Color.BLACK
        textSize = textSizePx
        typeface = Typeface.DEFAULT
    }
    return StaticLayout.Builder.obtain(text, 0, text.length, paint, width)
        .setAlignment(Layout.Alignment.ALIGN_NORMAL)
        .setIncludePad(false)
        .build()
}
