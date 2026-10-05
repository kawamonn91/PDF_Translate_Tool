package com.kawamonn.pdfjatranslator.pdf

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.artifex.mupdf.fitz.ColorSpace
import com.artifex.mupdf.fitz.Document
import com.artifex.mupdf.fitz.Matrix
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * MuPDF の呼び出しを1本のスレッドに集める。MuPDF は同時に呼ぶと壊れるため、
 * 表示・抽出・書き出しのすべてがこのスレッドを使う。
 */
object MupdfThread {
    val dispatcher = Dispatchers.IO.limitedParallelism(1)
}

/** MuPDF の文書。すべての呼び出しは [MupdfThread] で行う */
class MupdfDocument private constructor(private val doc: Document) : AutoCloseable {

    val pageCount: Int = doc.countPages()

    suspend fun pageSize(index: Int): Pair<Float, Float> = withContext(MupdfThread.dispatcher) {
        val page = doc.loadPage(0, index)
        try {
            val bounds = page.bounds
            (bounds.x1 - bounds.x0) to (bounds.y1 - bounds.y0)
        } finally {
            page.destroy()
        }
    }

    suspend fun renderPage(index: Int, scale: Float): Bitmap = withContext(MupdfThread.dispatcher) {
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

    suspend fun paragraphs(index: Int): List<Paragraph> = withContext(MupdfThread.dispatcher) {
        val page = doc.loadPage(0, index)
        try {
            val text = page.toStructuredText()
            try {
                buildParagraphs(index, text)
            } finally {
                text.destroy()
            }
        } finally {
            page.destroy()
        }
    }

    override fun close() {
        doc.destroy()
    }

    companion object {
        suspend fun open(path: String): MupdfDocument = withContext(MupdfThread.dispatcher) {
            MupdfDocument(Document.openDocument(path))
        }
    }
}
