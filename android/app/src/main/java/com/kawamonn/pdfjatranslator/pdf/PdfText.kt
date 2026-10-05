package com.kawamonn.pdfjatranslator.pdf

import com.artifex.mupdf.fitz.StructuredText
import kotlin.math.abs

/** 翻訳の単位(MuPDF のテキストブロック1つ)。座標はページの pt 単位 */
data class Paragraph(
    val id: String,
    val source: String,
    val left: Float,
    val top: Float,
    val right: Float,
    val bottom: Float,
    val fontSize: Float,
)

private val SENTENCE_END = Regex("[.!?:;。]$")
private val BULLET = Regex("^\\s*([•·・▪■●◦\\-–—]|\\d+[.)]|\\(\\d+\\)|[a-zA-Z][.)])\\s")
private val LATIN_LETTER = Regex("[A-Za-z]")
private val CJK = Regex("[\\u3040-\\u30ff\\u3400-\\u9fff]")

/** 英字が3文字以上あり、日本語がほとんど無い段落だけ翻訳対象にする(PC版と同じ条件) */
fun needsTranslation(text: String): Boolean {
    val latin = LATIN_LETTER.findAll(text).count()
    return latin >= 3 && CJK.findAll(text).count() < latin
}

fun buildParagraphs(pageIndex: Int, text: StructuredText): List<Paragraph> {
    val result = mutableListOf<Paragraph>()
    text.getBlocks().forEachIndexed { blockIndex, block ->
        val lines = block.lines.orEmpty().map { line ->
            line.chars.orEmpty().filter { it.c > 0 }.joinToString("") { String(Character.toChars(it.c)) }.trim()
        }.filter { it.isNotEmpty() }
        if (lines.isEmpty()) return@forEachIndexed
        val source = joinLines(lines)
        if (!needsTranslation(source)) return@forEachIndexed

        val heights = block.lines.orEmpty()
            .flatMap { it.chars.orEmpty().toList() }
            .map { abs(it.quad.ll_y - it.quad.ul_y) }
            .filter { it > 0f }
            .sorted()
        val fontSize = heights.getOrNull(heights.size / 2) ?: 10f

        result += Paragraph(
            id = "p${pageIndex + 1}-b$blockIndex",
            source = source,
            left = block.bbox.x0,
            top = block.bbox.y0,
            right = block.bbox.x1,
            bottom = block.bbox.y1,
            fontSize = fontSize,
        )
    }
    return result
}

/** 行をつなぐ。文末や箇条書きの行頭では改行、それ以外は空白でつなぐ */
internal fun joinLines(lines: List<String>): String {
    val out = StringBuilder()
    lines.forEachIndexed { i, line ->
        if (i == 0) {
            out.append(line)
        } else if (SENTENCE_END.containsMatchIn(lines[i - 1].trimEnd()) || BULLET.containsMatchIn(line)) {
            out.append('\n').append(line)
        } else {
            out.append(' ').append(line)
        }
    }
    return out.toString()
}
