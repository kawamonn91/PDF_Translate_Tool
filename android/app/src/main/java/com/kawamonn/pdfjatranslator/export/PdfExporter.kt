package com.kawamonn.pdfjatranslator.export

import android.graphics.Bitmap
import com.artifex.mupdf.fitz.Image
import com.artifex.mupdf.fitz.PDFDocument
import com.artifex.mupdf.fitz.Rect
import com.kawamonn.pdfjatranslator.pdf.MupdfThread
import java.io.ByteArrayOutputStream
import java.io.File
import kotlinx.coroutines.withContext

/**
 * 訳文を描き込んだページ画像から、PDF を作る。1ページずつ追加するので、ページを全部メモリに置かない。
 * MuPDF の呼び出しは [MupdfThread] で行う。
 */
class PdfExporter {

    private var doc: PDFDocument? = null
    private var pageNumber = 0

    /** [bitmap] はページの画像。[widthPt] と [heightPt] は元のページの大きさ(pt) */
    suspend fun addPage(bitmap: Bitmap, widthPt: Float, heightPt: Float) = withContext(MupdfThread.dispatcher) {
        val target = doc ?: PDFDocument().also { doc = it }
        val jpeg = ByteArrayOutputStream().use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
            out.toByteArray()
        }
        val image = Image(jpeg)
        try {
            val name = "Im${pageNumber++}"
            val imageRef = target.addImage(image)
            val xObjects = target.newDictionary()
            xObjects.put(name, imageRef)
            val resources = target.newDictionary()
            resources.put("XObject", xObjects)
            val page = target.addPage(Rect(0f, 0f, widthPt, heightPt), 0, resources, "q $widthPt 0 0 $heightPt 0 0 cm /$name Do Q")
            target.insertPage(target.countPages(), page)
        } finally {
            image.destroy()
        }
    }

    /** PDF を保存して、使った文書を閉じる。ページが1つも無ければ何もしない */
    suspend fun saveTo(file: File) = withContext(MupdfThread.dispatcher) {
        val target = doc ?: return@withContext
        try {
            target.save(file.absolutePath, "compress")
        } finally {
            target.destroy()
            doc = null
        }
    }

    private companion object {
        const val JPEG_QUALITY = 92
    }
}
