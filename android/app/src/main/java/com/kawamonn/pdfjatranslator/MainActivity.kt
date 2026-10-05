package com.kawamonn.pdfjatranslator

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import com.kawamonn.pdfjatranslator.pdf.MupdfDocument
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {

    private val incomingUri = mutableStateOf<Uri?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        incomingUri.value = pdfUriFrom(intent)
        setContent {
            MaterialTheme {
                PdfScreen(incomingUri.value)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        pdfUriFrom(intent)?.let { incomingUri.value = it }
    }

    private fun pdfUriFrom(intent: Intent?): Uri? =
        if (intent?.action == Intent.ACTION_VIEW) intent.data else null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PdfScreen(incoming: Uri?) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var document by remember { mutableStateOf<MupdfDocument?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    fun openUri(uri: Uri) {
        scope.launch {
            runCatching {
                val path = withContext(Dispatchers.IO) { copyToCache(context, uri) }
                withContext(Dispatchers.IO) { MupdfDocument.open(path) }
            }.onSuccess { opened ->
                document?.close()
                document = opened
                error = null
            }.onFailure { e ->
                error = e.message ?: "PDFを開けませんでした"
            }
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) openUri(uri)
    }

    LaunchedEffect(incoming) {
        incoming?.let { openUri(it) }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("PDF日本語化ツール") }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            Button(
                onClick = { picker.launch(arrayOf("application/pdf")) },
                modifier = Modifier.padding(16.dp),
            ) {
                Text("PDFを開く")
            }
            error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp))
            }
            document?.let { PageList(it) }
        }
    }
}

@Composable
private fun PageList(document: MupdfDocument) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(document.pageCount) { index ->
            PageImage(document, index)
        }
    }
}

@Composable
private fun PageImage(document: MupdfDocument, index: Int) {
    val bitmap by produceState<Bitmap?>(initialValue = null, document, index) {
        value = document.renderPage(index, 2f)
    }
    val current = bitmap
    if (current != null) {
        Image(
            bitmap = current.asImageBitmap(),
            contentDescription = "${index + 1}ページ",
            modifier = Modifier.fillMaxWidth(),
        )
    } else {
        Box(Modifier.fillMaxWidth().height(400.dp), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
    }
}

private fun copyToCache(context: Context, uri: Uri): String {
    val target = File(context.cacheDir, "input.pdf")
    context.contentResolver.openInputStream(uri)?.use { input ->
        target.outputStream().use { input.copyTo(it) }
    } ?: error("ファイルを読み込めませんでした")
    return target.absolutePath
}
