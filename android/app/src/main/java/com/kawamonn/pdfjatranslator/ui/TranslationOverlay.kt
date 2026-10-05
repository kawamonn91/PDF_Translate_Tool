package com.kawamonn.pdfjatranslator.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * 翻訳済みの段落。座標はページの pt 単位。
 * [scale] は利用者が調整した文字の大きさの倍率(1 が自動の大きさ)
 */
data class TranslatedParagraph(
    val left: Float,
    val top: Float,
    val right: Float,
    val bottom: Float,
    val fontSize: Float,
    val ja: String,
    val scale: Float = 1f,
)

private const val MIN_FONT_SP = 5f

/**
 * 元の段落の位置に、訳文を白い下地つきで重ねて表示する。
 * 文字は枠に収まるまで小さくする(自動調整)。タップすると [onParagraphClick] に段落の番号を渡す。
 */
@Composable
fun TranslationOverlay(
    paragraphs: List<TranslatedParagraph>,
    pageWidthPt: Float,
    onParagraphClick: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    BoxWithConstraints(modifier = modifier) {
        val dpPerPt = maxWidth.value / pageWidthPt
        val density = LocalDensity.current
        val measurer = rememberTextMeasurer()
        paragraphs.forEachIndexed { index, item ->
            val widthDp = (item.right - item.left) * dpPerPt
            val heightDp = (item.bottom - item.top) * dpPerPt
            val fittedSp = remember(item.ja, widthDp, heightDp, item.fontSize, item.scale, dpPerPt) {
                fitFontSize(
                    measurer = measurer,
                    text = item.ja,
                    maxWidthPx = with(density) { widthDp.dp.roundToPx() },
                    maxHeightPx = with(density) { heightDp.dp.roundToPx() },
                    startSp = item.fontSize * item.scale * dpPerPt,
                )
            }
            Box(
                modifier = Modifier
                    .offset(x = (item.left * dpPerPt).dp, y = (item.top * dpPerPt).dp)
                    .size(width = widthDp.dp, height = heightDp.dp)
                    .background(Color.White)
                    .clickable { onParagraphClick(index) },
            ) {
                Text(
                    text = item.ja,
                    style = TextStyle(fontSize = fittedSp.sp, color = Color.Black),
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}

/** 枠に収まる最大の文字の大きさ(sp)を探す。収まらなければ最小の大きさ */
private fun fitFontSize(
    measurer: TextMeasurer,
    text: String,
    maxWidthPx: Int,
    maxHeightPx: Int,
    startSp: Float,
): Float {
    var size = startSp.coerceAtLeast(MIN_FONT_SP)
    while (size > MIN_FONT_SP) {
        val layout = measurer.measure(
            text = AnnotatedString(text),
            style = TextStyle(fontSize = size.sp),
            constraints = Constraints(maxWidth = maxWidthPx.coerceAtLeast(1)),
        )
        if (layout.size.height <= maxHeightPx) return size
        size -= 0.5f
    }
    return MIN_FONT_SP
}
