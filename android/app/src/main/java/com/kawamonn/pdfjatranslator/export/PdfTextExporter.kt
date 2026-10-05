package com.kawamonn.pdfjatranslator.export

import com.artifex.mupdf.fitz.Document
import com.artifex.mupdf.fitz.Font
import com.artifex.mupdf.fitz.Matrix
import com.artifex.mupdf.fitz.PDFAnnotation
import com.artifex.mupdf.fitz.PDFDocument
import com.artifex.mupdf.fitz.PDFObject
import com.artifex.mupdf.fitz.PDFPage
import com.artifex.mupdf.fitz.Rect
import com.kawamonn.pdfjatranslator.pdf.MupdfThread
import com.kawamonn.pdfjatranslator.ui.TranslatedParagraph
import java.io.File
import java.util.Locale
import kotlinx.coroutines.withContext

/**
 * 元のPDFの翻訳した段落を墨消しして、訳文を文字として書き直したPDFを作る。
 * 画像や線は残し、書き出したPDFでも文字を選んだり検索したりできる。
 * 日本語フォントは埋め込まず、読む端末の日本語フォントで表示する(PC版より軽くするため)。
 * 回転したページには対応していない。
 */
class PdfTextExporter(private val sourcePath: String) {

    /** [translations] はページ番号(0始まり)ごとの訳文。訳文の無いページは元のまま残す */
    suspend fun exportTo(output: File, translations: Map<Int, List<TranslatedParagraph>>) =
        withContext(MupdfThread.dispatcher) {
            val document = Document.openDocument(sourcePath).asPDF() ?: error("PDFとして開けませんでした")
            try {
                val fontRef = addJapaneseFont(document)
                for ((index, paragraphs) in translations) {
                    if (paragraphs.isEmpty()) continue
                    val page = document.loadPage(index) as PDFPage
                    try {
                        writePage(document, page, fontRef, paragraphs)
                    } finally {
                        page.destroy()
                    }
                }
                document.save(output.absolutePath, "compress,garbage")
            } finally {
                document.destroy()
            }
        }

    private fun addJapaneseFont(document: PDFDocument): PDFObject {
        // addCJKFont は埋め込まず、読み手の日本語フォント(ゴシック)を指す。Font は並び替えのキーにだけ使う
        val font = Font(BASE_FONT)
        val fontRef = try {
            document.addCJKFont(font, Font.ADOBE_JAPAN, 0, false)
        } finally {
            font.destroy()
        }
        // 文字を選ぶ・検索するために、文字コード(UTF-16 の符号)と Unicode の対応を付ける
        fontRef.put("ToUnicode", document.addStream(TO_UNICODE, null))
        return fontRef
    }

    private fun writePage(document: PDFDocument, page: PDFPage, fontRef: PDFObject, paragraphs: List<TranslatedParagraph>) {
        for (item in paragraphs) {
            val redaction = page.createAnnotation(PDFAnnotation.TYPE_REDACT)
            try {
                redaction.setRect(Rect(item.left, item.top, item.right, item.bottom))
            } finally {
                redaction.destroy()
            }
        }
        page.applyRedactions(false, PDFPage.REDACT_IMAGE_NONE, PDFPage.REDACT_LINE_ART_NONE, PDFPage.REDACT_TEXT_REMOVE)

        val pageObject = page.getObject()
        val resources = resourcesOf(document, pageObject)
        val fonts = resources.get("Font").present() ?: document.newDictionary().also { resources.put("Font", it) }
        fonts.put(FONT_NAME, fontRef)

        // ページ座標(左上が原点)から PDF の座標(左下が原点)へ変換する
        val toPdf = page.getTransform().invert()
        val drawing = StringBuilder("q\n0 g\n")
        for (item in paragraphs) {
            appendParagraph(drawing, item, toPdf)
        }
        drawing.append("Q\n")

        // 元の描画を q/Q で挟み、その後ろに訳文を描く。元の描画が状態を残しても訳文に影響しないようにする
        val contents = document.newArray()
        contents.push(document.addStream("q\n", null))
        pageObject.get("Contents").present()?.let { old ->
            if (old.resolve().isArray()) {
                val list = old.resolve()
                for (i in 0 until list.size()) contents.push(list.get(i))
            } else {
                contents.push(old)
            }
        }
        contents.push(document.addStream("Q\n", null))
        contents.push(document.addStream(drawing.toString(), null))
        pageObject.put("Contents", contents)
    }

    private fun resourcesOf(document: PDFDocument, pageObject: PDFObject): PDFObject {
        pageObject.getInheritable("Resources").present()?.let { return it }
        return document.newDictionary().also { pageObject.put("Resources", it) }
    }

    private fun appendParagraph(sb: StringBuilder, item: TranslatedParagraph, toPdf: Matrix) {
        val layout = fitLayout(item.ja, item.right - item.left, item.bottom - item.top, item.fontSize * item.scale)
        layout.lines.forEachIndexed { i, line ->
            val baseline = item.top + layout.size * BASELINE_RATIO + i * layout.size * LINE_RATIO
            val x = toPdf.a * item.left + toPdf.c * baseline + toPdf.e
            val y = toPdf.b * item.left + toPdf.d * baseline + toPdf.f
            sb.append("BT /").append(FONT_NAME).append(' ').append(number(layout.size)).append(" Tf 1 0 0 1 ")
                .append(number(x)).append(' ').append(number(y)).append(" Tm <")
            // 日本語のエンコーディング(UniJIS-UTF16)は UTF-16 の符号をそのまま使う
            line.forEach { sb.append(String.format(Locale.ROOT, "%04X", it.code)) }
            sb.append("> Tj ET\n")
        }
    }

    private class Layout(val size: Float, val lines: List<String>)

    /**
     * 枠に収まる文字の大きさと行を決める。文字は1em幅として扱う
     * (埋め込みなしの日本語フォントは、読み手の端末でも1文字1emで並ぶため)
     */
    private fun fitLayout(text: String, width: Float, height: Float, startSize: Float): Layout {
        var size = startSize.coerceAtLeast(MIN_SIZE)
        while (true) {
            val lines = wrap(text, width, size)
            if (lines.size * size * LINE_RATIO <= height || size <= MIN_SIZE) return Layout(size, lines)
            size = (size - SIZE_STEP).coerceAtLeast(MIN_SIZE)
        }
    }

    private fun wrap(text: String, width: Float, size: Float): List<String> {
        val perLine = (width / size).toInt().coerceAtLeast(1)
        return text.replace("\r", "").split('\n').flatMap { segment ->
            if (segment.isEmpty()) listOf("") else segment.chunked(perLine)
        }
    }

    private fun number(value: Float): String = String.format(Locale.ROOT, "%.2f", value)

    private fun PDFObject?.present(): PDFObject? = if (this == null || isNull()) null else this

    private companion object {
        // 符号がそのまま Unicode になる対応表(書き出しで使う UTF-16 の符号と同じ)
        val TO_UNICODE = """
            /CIDInit /ProcSet findresource begin
            12 dict begin
            begincmap
            /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
            /CMapName /Adobe-Identity-UCS def
            /CMapType 2 def
            1 begincodespacerange <0000> <FFFF> endcodespacerange
            1 beginbfrange <0000> <FFFF> <0000> endbfrange
            endcmap
            CMapName currentdict /CMap defineresource pop
            end
            end
        """.trimIndent()
        const val BASE_FONT = "Helvetica"
        const val FONT_NAME = "JaTrans"
        const val MIN_SIZE = 5f
        const val SIZE_STEP = 0.5f
        const val LINE_RATIO = 1.2f
        const val BASELINE_RATIO = 0.9f
    }
}
