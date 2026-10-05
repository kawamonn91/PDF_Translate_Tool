package com.kawamonn.pdfjatranslator.pdf

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.artifex.mupdf.fitz.ColorSpace
import com.artifex.mupdf.fitz.Document
import com.artifex.mupdf.fitz.Matrix
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * MuPDF の文書。MuPDF は同時に呼ぶと壊れるため、すべての呼び出しを1本のスレッドに集める。
 */
class MupdfDocument private constructor(private val doc: Document) : AutoCloseable {

    private val mupdf = Dispatchers.IO.limitedParallelism(1)

    val pageCount: Int = doc.countPages()

    suspend fun renderPage(index: Int, scale: Float): Bitmap = withContext(mupdf) {
        val page = doc.loadPage(0, index)
        try {
            val pixmap = page.toPixmap(Matrix(scale, scale), ColorSpace.DeviceRGB, false, true)
            try {
                val png = pixmap.asPNG()
                try {
                    val bytes = png.asByteArray()
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                } finally {
                    png.destroy()
                }
            } finally {
                pixmap.destroy()
            }
        } finally {
            page.destroy()
        }
    }

    override fun close() {
        doc.destroy()
    }

    companion object {
        fun open(path: String): MupdfDocument = MupdfDocument(Document.openDocument(path))
    }
}
