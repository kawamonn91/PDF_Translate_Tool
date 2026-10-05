package com.kawamonn.pdfjatranslator.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt

private const val MIN_SCALE = 0.5f
private const val MAX_SCALE = 1.5f
private const val SCALE_STEPS = 19

/** 訳文を直し、文字の大きさを調整する画面 */
@Composable
fun ParagraphEditDialog(
    paragraph: TranslatedParagraph,
    onDismiss: () -> Unit,
    onSave: (ja: String, scale: Float) -> Unit,
) {
    var text by remember { mutableStateOf(paragraph.ja) }
    var scale by remember { mutableFloatStateOf(paragraph.scale) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("訳文の調整") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    label = { Text("訳文") },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text("文字の大きさ: ${(scale * 100).roundToInt()}%")
                Slider(
                    value = scale,
                    onValueChange = { scale = it },
                    valueRange = MIN_SCALE..MAX_SCALE,
                    steps = SCALE_STEPS,
                )
                TextButton(onClick = { scale = 1f }) {
                    Text("大きさを自動に戻す")
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = text.isNotBlank(),
                onClick = { onSave(text.trim(), scale) },
            ) {
                Text("保存")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("キャンセル")
            }
        },
    )
}
