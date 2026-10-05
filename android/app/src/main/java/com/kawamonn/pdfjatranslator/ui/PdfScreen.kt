package com.kawamonn.pdfjatranslator.ui

import android.graphics.Bitmap
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.kawamonn.pdfjatranslator.export.PdfTextExporter
import com.kawamonn.pdfjatranslator.pdf.MupdfDocument
import com.kawamonn.pdfjatranslator.pdf.copyToCache
import com.kawamonn.pdfjatranslator.settings.ApiKeyStore
import com.kawamonn.pdfjatranslator.translate.ClaudeTranslator
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** ページ画像の解像度(1pt あたりのピクセル数) */
private const val RENDER_SCALE = 2f

/** 調整中の段落。ページ番号と段落の並び順で指す */
private data class EditTarget(val page: Int, val index: Int)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PdfScreen(incoming: Uri?) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { ApiKeyStore(context) }

    var document by remember { mutableStateOf<MupdfDocument?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var status by remember { mutableStateOf<String?>(null) }
    var translations by remember { mutableStateOf<Map<Int, List<TranslatedParagraph>>>(emptyMap()) }
    var translating by remember { mutableStateOf(false) }
    var showKeyDialog by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<EditTarget?>(null) }

    fun openUri(uri: Uri) {
        scope.launch {
            runCatching {
                val path = withContext(Dispatchers.IO) { copyToCache(context, uri) }
                MupdfDocument.open(path)
            }.onSuccess { opened ->
                document?.close()
                document = opened
                translations = emptyMap()
                error = null
                status = null
            }.onFailure { e ->
                error = e.message ?: "PDFを開けませんでした"
            }
        }
    }

    fun translateAll(doc: MupdfDocument, apiKey: String) {
        translating = true
        status = "翻訳を始めます…"
        scope.launch {
            runCatching {
                val translator = ClaudeTranslator(apiKey)
                val result = linkedMapOf<Int, List<TranslatedParagraph>>()
                for (index in 0 until doc.pageCount) {
                    status = "翻訳中 ${index + 1} / ${doc.pageCount} ページ"
                    val paragraphs = doc.paragraphs(index)
                    if (paragraphs.isEmpty()) continue
                    val translated = withContext(Dispatchers.IO) {
                        translator.translate(paragraphs.map { it.id to it.source })
                    }
                    result[index] = paragraphs.mapNotNull { p ->
                        translated[p.id]?.let { ja ->
                            TranslatedParagraph(p.left, p.top, p.right, p.bottom, p.fontSize, ja)
                        }
                    }
                    translations = result.toMap()
                }
                status = "翻訳が終わりました(${result.values.sumOf { it.size }} 件)。訳文をタップすると直せます"
            }.onFailure { e ->
                status = "翻訳できませんでした: ${e.message ?: "原因不明のエラー"}"
            }
            translating = false
        }
    }

    fun startTranslation() {
        val doc = document ?: return
        val apiKey = store.load()
        if (apiKey == null) {
            showKeyDialog = true
        } else {
            translateAll(doc, apiKey)
        }
    }

    fun updateParagraph(target: EditTarget, ja: String, scale: Float) {
        val list = translations[target.page] ?: return
        translations = translations + (target.page to list.mapIndexed { i, p ->
            if (i == target.index) p.copy(ja = ja, scale = scale) else p
        })
    }

    fun exportTo(uri: Uri) {
        val doc = document ?: return
        val snapshot = translations
        translating = true
        status = "書き出しています…"
        scope.launch {
            runCatching {
                val temp = File(context.filesDir, "translated.pdf")
                PdfTextExporter(doc.path).exportTo(temp, snapshot)
                withContext(Dispatchers.IO) {
                    context.contentResolver.openOutputStream(uri)?.use { out ->
                        temp.inputStream().use { it.copyTo(out) }
                    } ?: error("保存先を開けませんでした")
                }
                status = "保存しました"
            }.onFailure { e ->
                status = "書き出せませんでした: ${e.message ?: "原因不明のエラー"}"
            }
            translating = false
        }
    }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri: Uri? ->
        if (uri != null) exportTo(uri)
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) openUri(uri)
    }

    LaunchedEffect(incoming) {
        incoming?.let { openUri(it) }
    }

    if (showKeyDialog) {
        ApiKeyDialog(
            onDismiss = { showKeyDialog = false },
            onSaved = {
                showKeyDialog = false
                document?.let { doc -> store.load()?.let { translateAll(doc, it) } }
            },
        )
    }

    editing?.let { target ->
        translations[target.page]?.getOrNull(target.index)?.let { paragraph ->
            ParagraphEditDialog(
                paragraph = paragraph,
                onDismiss = { editing = null },
                onSave = { ja, scale ->
                    updateParagraph(target, ja, scale)
                    editing = null
                },
            )
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("PDF日本語化ツール") }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            FlowRow(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(onClick = { picker.launch(arrayOf("application/pdf")) }) {
                    Text("PDFを開く")
                }
                Button(
                    enabled = document != null && !translating,
                    onClick = { startTranslation() },
                ) {
                    Text("翻訳")
                }
                OutlinedButton(onClick = { showKeyDialog = true }) {
                    Text("APIキー")
                }
                Button(
                    enabled = document != null && translations.isNotEmpty() && !translating,
                    onClick = { exportLauncher.launch("translated.pdf") },
                ) {
                    Text("書き出し")
                }
            }
            status?.let {
                Text(it, modifier = Modifier.padding(horizontal = 16.dp))
            }
            error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp))
            }
            document?.let { doc ->
                PageList(doc, translations, onParagraphClick = { page, index -> editing = EditTarget(page, index) })
            }
        }
    }
}

@Composable
private fun PageList(
    document: MupdfDocument,
    translations: Map<Int, List<TranslatedParagraph>>,
    onParagraphClick: (page: Int, index: Int) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(document.pageCount) { index ->
            PageImage(document, index, translations[index].orEmpty(), onParagraphClick)
        }
    }
}

@Composable
private fun PageImage(
    document: MupdfDocument,
    index: Int,
    paragraphs: List<TranslatedParagraph>,
    onParagraphClick: (page: Int, index: Int) -> Unit,
) {
    val bitmap by produceState<Bitmap?>(initialValue = null, document, index) {
        value = document.renderPage(index, RENDER_SCALE)
    }
    val current = bitmap
    if (current != null) {
        Box(Modifier.fillMaxWidth()) {
            Image(
                bitmap = current.asImageBitmap(),
                contentDescription = "${index + 1}ページ",
                modifier = Modifier.fillMaxWidth(),
            )
            if (paragraphs.isNotEmpty()) {
                TranslationOverlay(
                    paragraphs = paragraphs,
                    pageWidthPt = current.width / RENDER_SCALE,
                    onParagraphClick = { paragraphIndex -> onParagraphClick(index, paragraphIndex) },
                    modifier = Modifier.matchParentSize(),
                )
            }
        }
    } else {
        Box(Modifier.fillMaxWidth().height(400.dp), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
    }
}
