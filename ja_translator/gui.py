"""Windows 向けの画面。左: ページのプレビュー(項目をクリックで選ぶ) / 右: 項目の一覧と調整。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pymupdf as fitz
from PySide6.QtCore import QObject, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont, QImage, QKeySequence, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import pdf_engine, pptx_engine, preview
from .model import TextUnit
from .project import Project
from .settings import delete_api_key, get_api_key, key_source, save_api_key, verify_api_key
from .translate import ClaudeTranslator

RENDER_SCALE = 2.0  # プレビューの解像度(pt → ピクセルの倍率)
ALIGN_LABELS = {"left": "左揃え", "center": "中央揃え", "right": "右揃え"}
FILE_FILTER = "PDF / PowerPoint (*.pdf *.pptx)"


class Job(QThread):
    """時間のかかる処理を、画面を止めずに実行する"""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self._fn())
        except Exception as e:  # 画面に理由を出すため、どんな失敗も拾う
            self.failed.emit(str(e))


CONSOLE_KEYS_URL = "https://console.anthropic.com/settings/keys"


class ApiKeyDialog(QDialog):
    """初めての人でも迷わないように、取得から登録までを手順で案内する"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Claude APIキーの登録")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)

        guide = QLabel(
            "<b>翻訳には Claude API のキーが必要です。次の手順で登録してください。</b><br>"
            "1. 下の「Anthropic Console を開く」を押し、Anthropic のアカウントでログインします。<br>"
            "2. 「Create Key」(キーを作成)を押し、表示された <b>sk-ant-</b> で始まる文字列をコピーします。<br>"
            "3. コピーした文字列を下の欄に貼り付けます(「貼り付け」ボタンでも入ります)。<br>"
            "4. 「接続テストして保存」を押します。OK と出れば登録完了です。<br><br>"
            "<span style='color:#666'>キーは Windows の資格情報マネージャーに暗号化して保存され、翻訳のときだけ Claude API に送られます。"
            "API の利用料金は Anthropic の従量課金です(使った分だけ)。Console で利用上限を設定すると安心です。</span>"
        )
        guide.setWordWrap(True)
        layout.addWidget(guide)

        open_row = QHBoxLayout()
        open_btn = QPushButton("Anthropic Console を開く")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CONSOLE_KEYS_URL)))
        open_row.addWidget(open_btn)
        open_row.addStretch(1)
        layout.addLayout(open_row)

        entry_row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("ここに sk-ant- で始まるキーを貼り付け")
        self.edit.setClearButtonEnabled(True)
        entry_row.addWidget(self.edit, 1)
        paste_btn = QPushButton("貼り付け")
        paste_btn.clicked.connect(self._paste)
        entry_row.addWidget(paste_btn)
        layout.addLayout(entry_row)

        self.show_check = QCheckBox("キーを画面に表示する")
        self.show_check.toggled.connect(
            lambda on: self.edit.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password)
        )
        layout.addWidget(self.show_check)

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QDialogButtonBox()
        self.save_btn = buttons.addButton("接続テストして保存", QDialogButtonBox.ButtonRole.AcceptRole)
        self.delete_btn = buttons.addButton("保存済みのキーを削除", QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton("閉じる", QDialogButtonBox.ButtonRole.RejectRole)
        self.save_btn.clicked.connect(self._save)
        self.delete_btn.clicked.connect(self._delete)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_status()

    def _paste(self) -> None:
        text = QApplication.clipboard().text().strip()
        if not text:
            QMessageBox.information(self, "貼り付けできません", "クリップボードに文字がありません。Console でキーをコピーしてから押してください。")
            return
        self.edit.setText(text)

    def _refresh_status(self) -> None:
        source = key_source()
        if source == "env":
            text = "今は環境変数 ANTHROPIC_API_KEY のキーが使われています(こちらが優先されます)。"
        elif source == "stored":
            text = "登録済みです。このまま翻訳に使えます。"
        else:
            text = "まだ登録されていません。"
        self.status.setText(text)
        self.delete_btn.setEnabled(source == "stored")

    def _save(self) -> None:
        key = self.edit.text().strip()
        if not key:
            QMessageBox.information(self, "キーが空です", "上の欄にキーを貼り付けてから、もう一度押してください。")
            return
        self.save_btn.setEnabled(False)
        self.status.setText("Claude API に接続して確かめています…")
        QApplication.processEvents()
        try:
            verify_api_key(key)
            save_api_key(key)
        except ValueError as e:
            QMessageBox.warning(self, "登録できませんでした", str(e))
            self.save_btn.setEnabled(True)
            self._refresh_status()
            return
        except Exception as e:
            QMessageBox.warning(self, "登録できませんでした", f"資格情報マネージャーへの保存に失敗しました。\n{e}")
            self.save_btn.setEnabled(True)
            self._refresh_status()
            return
        self.save_btn.setEnabled(True)
        self.edit.clear()
        self._refresh_status()
        QMessageBox.information(self, "登録できました", "Claude API キーを登録しました。翻訳を始められます。")

    def _delete(self) -> None:
        if QMessageBox.question(self, "削除しますか", "保存済みのキーを削除します。よろしいですか?") != QMessageBox.StandardButton.Yes:
            return
        delete_api_key()
        self._refresh_status()


class PageView(QGraphicsView):
    unitClicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QColor("#e9ecef"))
        self._overlays: dict[str, QGraphicsRectItem] = {}

    def show_image(self, image: QImage, boxes: dict[str, tuple[float, float, float, float]], warnings: set[str]) -> None:
        self._scene.clear()
        self._overlays = {}
        pix = QPixmap.fromImage(image)
        self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(0, 0, pix.width(), pix.height()))
        for unit_id, (x0, y0, x1, y1) in boxes.items():
            rect = QRectF(x0 * RENDER_SCALE, y0 * RENDER_SCALE, (x1 - x0) * RENDER_SCALE, (y1 - y0) * RENDER_SCALE)
            item = self._scene.addRect(rect, QPen(QColor("#d9480f" if unit_id in warnings else "#1c7ed6"), 1.5))
            item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            item.setData(0, unit_id)
            item.setToolTip(unit_id)
            self._overlays[unit_id] = item
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def highlight(self, unit_id: str | None) -> None:
        for uid, item in self._overlays.items():
            selected = uid == unit_id
            item.setBrush(QBrush(QColor(28, 126, 214, 60)) if selected else QBrush(Qt.BrushStyle.NoBrush))
            item.setPen(QPen(QColor("#1c7ed6"), 2.5 if selected else 1.5))
        if unit_id in self._overlays:
            self.ensureVisible(self._overlays[unit_id], 80, 80)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        for item in self.items(event.position().toPoint()):
            unit_id = item.data(0)
            if unit_id:
                self.unitClicked.emit(str(unit_id))
                return

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.scale(1.15 if event.angleDelta().y() > 0 else 1 / 1.15, 1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
            event.accept()
            return
        super().wheelEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF・PPTX 日本語化ツール")
        self.resize(1400, 860)
        self.project: Project | None = None
        self.page_index = 0
        self.selected_id: str | None = None
        self._jobs: list[Job] = []
        self._pptx_preview: Path | None = None
        self._loading = False

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(300)
        self._render_timer.timeout.connect(self.refresh_preview)

        self._build_ui()
        self._build_actions()
        self._update_enabled()
        self.statusBar().showMessage("ファイルを開いてください (Ctrl+O)")

    # ---------- 画面の組み立て ----------

    def _build_ui(self) -> None:
        self.view = PageView()
        self.view.unitClicked.connect(self.select_unit)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.page_label = QLabel("ページ -")
        self.refresh_btn = QPushButton("プレビュー更新")
        self.prev_btn.clicked.connect(lambda: self.go_page(-1))
        self.next_btn.clicked.connect(lambda: self.go_page(1))
        self.refresh_btn.clicked.connect(self.force_refresh)
        for w in (self.prev_btn, self.page_label, self.next_btn):
            nav.addWidget(w)
        nav.addStretch(1)
        nav.addWidget(self.refresh_btn)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(nav)
        left_layout.addWidget(self.view, 1)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["場所", "原文", "訳文", "状態"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_select)

        self.editor = QGroupBox("選択中の項目")
        form = QFormLayout(self.editor)
        self.original = QPlainTextEdit()
        self.original.setReadOnly(True)
        self.original.setMaximumHeight(90)
        self.translation = QPlainTextEdit()
        self.translation.setMaximumHeight(120)
        self.translation.textChanged.connect(self._on_editor_changed)
        self.scale = QSpinBox()
        self.scale.setRange(0, 160)
        self.scale.setSingleStep(5)
        self.scale.setSuffix(" %")
        self.scale.setSpecialValueText("自動(枠に合わせる)")
        self.scale.setValue(0)
        self.scale.valueChanged.connect(self._on_editor_changed)
        self.dx = QDoubleSpinBox()
        self.dx.setRange(-200, 200)
        self.dx.setSuffix(" pt")
        self.dx.valueChanged.connect(self._on_editor_changed)
        self.dy = QDoubleSpinBox()
        self.dy.setRange(-200, 200)
        self.dy.setSuffix(" pt")
        self.dy.valueChanged.connect(self._on_editor_changed)
        self.align = QComboBox()
        for key, label in ALIGN_LABELS.items():
            self.align.addItem(label, key)
        self.align.currentIndexChanged.connect(self._on_editor_changed)
        self.reset_btn = QPushButton("機械翻訳と初期配置に戻す")
        self.reset_btn.clicked.connect(self.reset_selected)
        self.retranslate_btn = QPushButton("この項目を翻訳し直す")
        self.retranslate_btn.clicked.connect(self.retranslate_selected)
        form.addRow("原文", self.original)
        form.addRow("訳文", self.translation)
        form.addRow("文字サイズ", self.scale)
        form.addRow("横位置の補正", self.dx)
        form.addRow("縦位置の補正", self.dy)
        form.addRow("揃え", self.align)
        form.addRow(self.reset_btn)
        form.addRow(self.retranslate_btn)
        self.editor.setEnabled(False)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.table, 1)
        right_layout.addWidget(self.editor)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

    def _build_actions(self) -> None:
        tb = self.addToolBar("操作")
        tb.setMovable(False)

        def add(text: str, shortcut: str | None, slot) -> QAction:
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(slot)
            tb.addAction(action)
            self.addAction(action)
            return action

        self.open_action = add("開く", "Ctrl+O", self.open_file)
        self.translate_action = add("すべて翻訳", "Ctrl+T", self.translate_all)
        self.export_action = add("日本語版を保存", "Ctrl+S", self.export)
        tb.addSeparator()
        add("APIキー登録", None, self.open_api_key_dialog)
        tb.addSeparator()
        self.key_label = QLabel()
        tb.addWidget(self.key_label)
        self._refresh_key_label()

    # ---------- ファイル・翻訳 ----------

    def _refresh_key_label(self) -> None:
        has_key = get_api_key() is not None
        self.key_label.setText(" 翻訳: Claude API " + ("(登録済み)" if has_key else "(APIキーが未登録です)"))

    def open_api_key_dialog(self) -> None:
        ApiKeyDialog(self).exec()
        self._refresh_key_label()

    def _require_api_key(self) -> bool:
        if get_api_key() is not None:
            return True
        QMessageBox.information(self, "APIキーの登録が必要です", "翻訳には Claude API キーが必要です。登録画面を開きますので、手順に沿って登録してください。")
        self.open_api_key_dialog()
        return get_api_key() is not None

    def _update_enabled(self) -> None:
        loaded = self.project is not None
        self.translate_action.setEnabled(loaded)
        self.export_action.setEnabled(loaded)
        self.refresh_btn.setEnabled(loaded)
        self.prev_btn.setEnabled(loaded)
        self.next_btn.setEnabled(loaded)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "文書を開く", "", FILE_FILTER)
        if not path:
            return
        try:
            project = Project.open(path)
        except Exception as e:
            QMessageBox.warning(self, "開けませんでした", str(e))
            return
        self.project = project
        self.page_index = 0
        self.selected_id = None
        self._pptx_preview = None
        self._reload_table()
        self._update_enabled()
        self.refresh_preview()
        msg = f"{project.source.name}: 項目 {len(project.units)} 件"
        if project.translated_count():
            msg += f" (翻訳済み {project.translated_count()} 件)"
        self.statusBar().showMessage(msg)

    def translate_all(self) -> None:
        if self.project is None:
            return
        if not self._require_api_key():
            return
        self._busy(True, "翻訳しています…")
        project = self.project

        def work():
            translator = ClaudeTranslator()
            count = project.translate(translator, model=translator.model)
            project.save_sidecar()
            return count

        self._run(work, self._on_translated)

    def _on_translated(self, count: int) -> None:
        self._busy(False, f"{count} 件を翻訳しました")
        self._reload_table()
        self.refresh_preview()

    def export(self) -> None:
        if self.project is None:
            return
        suffix = self.project.source.suffix
        default = str(self.project.source.with_name(f"{self.project.source.stem}_ja{suffix}"))
        path, _ = QFileDialog.getSaveFileName(self, "日本語版を保存", default, f"*{suffix}")
        if not path:
            return
        self._busy(True, "書き出しています…")
        project = self.project
        self._run(lambda: project.export(path) or path, lambda p: self._busy(False, f"保存しました: {p}"))

    # ---------- 項目の一覧と調整 ----------

    def _reload_table(self) -> None:
        self._loading = True
        self.table.setRowCount(0)
        if self.project is None:
            self._loading = False
            return
        warnings = self.project.warnings()
        for unit in self.project.units:
            row = self.table.rowCount()
            self.table.insertRow(row)
            location = self._location_label(unit)
            status = "未翻訳" if unit.translation is None else ("注意: 枠に収まりません" if unit.id in warnings else "翻訳済み")
            if unit.translation is not None and unit.scale != 1.0:
                status += " / 手動調整"
            values = [location, _short(unit.source), _short(unit.translation or ""), status]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, unit.id)
                if unit.id in warnings:
                    item.setForeground(QBrush(QColor("#d9480f")))
                self.table.setItem(row, col, item)
        self._loading = False

    def _location_label(self, unit: TextUnit) -> str:
        if self.project and self.project.kind == "pdf":
            return f"p.{unit.location['page'] + 1}"
        return f"スライド{unit.location['slide'] + 1}"

    def select_unit(self, unit_id: str) -> None:
        if self.project is None:
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == unit_id:
                self.table.selectRow(row)
                return

    def _on_table_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows or self.project is None:
            self.editor.setEnabled(False)
            self.selected_id = None
            self.view.highlight(None)
            return
        unit_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self.selected_id = unit_id
        unit = self.project.unit(unit_id)
        if self.project.kind == "pdf" and unit.location["page"] != self.page_index:
            self.page_index = unit.location["page"]
            self.refresh_preview()
        elif self.project.kind == "pptx" and unit.location["slide"] != self.page_index:
            self.page_index = unit.location["slide"]
            self.refresh_preview()
        self._show_editor(unit)
        self.view.highlight(unit_id)

    def _show_editor(self, unit: TextUnit) -> None:
        self._loading = True
        self.editor.setEnabled(True)
        self.original.setPlainText(unit.source)
        self.translation.setPlainText(unit.translation or "")
        self.scale.setValue(0 if unit.scale == 1.0 else round(unit.scale * 100))
        self.dx.setValue(unit.dx)
        self.dy.setValue(unit.dy)
        self.align.setCurrentIndex(max(0, self.align.findData(unit.align)))
        is_pdf = self.project is not None and self.project.kind == "pdf"
        self.dx.setEnabled(is_pdf)
        self.dy.setEnabled(is_pdf)
        self.align.setEnabled(is_pdf)
        self._loading = False

    def _on_editor_changed(self, *_args) -> None:
        if self._loading or self.selected_id is None or self.project is None:
            return
        unit = self.project.unit(self.selected_id)
        unit.translation = self.translation.toPlainText()
        unit.scale = 1.0 if self.scale.value() == 0 else self.scale.value() / 100
        unit.dx = self.dx.value()
        unit.dy = self.dy.value()
        unit.align = self.align.currentData()
        self._update_row(unit)
        if self.project.kind == "pdf":
            self._render_timer.start()
        else:
            self._pptx_preview = None
            self.statusBar().showMessage("PowerPoint 版は「プレビュー更新」で反映されます")

    def _update_row(self, unit: TextUnit) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == unit.id:
                self.table.item(row, 2).setText(_short(unit.translation or ""))
                warnings = self.project.warnings() if self.project else {}
                status = "未翻訳" if unit.translation is None else ("注意: 枠に収まりません" if unit.id in warnings else "翻訳済み")
                if unit.translation is not None and unit.scale != 1.0:
                    status += " / 手動調整"
                self.table.item(row, 3).setText(status)
                color = QColor("#d9480f") if unit.id in warnings else QColor("#000000")
                for col in range(4):
                    self.table.item(row, col).setForeground(QBrush(color))
                return

    def reset_selected(self) -> None:
        if self.project is None or self.selected_id is None:
            return
        self.project.reset_unit(self.selected_id)
        self._show_editor(self.project.unit(self.selected_id))
        self._reload_table()
        self.select_unit(self.selected_id)
        self.refresh_preview()

    def retranslate_selected(self) -> None:
        if self.project is None or self.selected_id is None:
            return
        if not self._require_api_key():
            return
        unit_id = self.selected_id
        project = self.project
        self._busy(True, "翻訳し直しています…")

        def work():
            translator = ClaudeTranslator()
            unit = project.unit(unit_id)
            results = translator.translate([(unit.id, unit.source)])
            if unit.id not in results:
                raise RuntimeError("翻訳結果を受け取れませんでした。もう一度お試しください")
            unit.machine = results[unit.id]
            unit.translation = results[unit.id]
            unit.scale, unit.dx, unit.dy = 1.0, 0.0, 0.0
            project.save_sidecar()
            return unit_id

        self._run(work, self._on_retranslated)

    def _on_retranslated(self, unit_id: str) -> None:
        self._busy(False, "翻訳し直しました")
        self._reload_table()
        self.select_unit(unit_id)
        self.refresh_preview()

    # ---------- プレビュー ----------

    def go_page(self, step: int) -> None:
        if self.project is None:
            return
        pages = self._page_count()
        target = min(max(self.page_index + step, 0), pages - 1)
        if target != self.page_index:
            self.page_index = target
            self.refresh_preview()

    def _page_count(self) -> int:
        if self.project is None:
            return 0
        if self.project.kind == "pdf":
            with fitz.open(self.project.source) as doc:
                return doc.page_count
        return _pptx_slide_count(self.project.source)

    def force_refresh(self) -> None:
        self._pptx_preview = None
        self.refresh_preview()

    def refresh_preview(self) -> None:
        if self.project is None:
            return
        self.page_label.setText(f"{self.page_index + 1} / {self._page_count()}")
        if self.project.kind == "pdf":
            self._show_pdf_preview()
        else:
            self._show_pptx_preview()

    def _show_pdf_preview(self) -> None:
        project = self.project
        page_no = self.page_index
        doc = pdf_engine.render(project.source, project.units)
        try:
            page = doc[page_no]
            pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
            image = QImage(bytes(pix.samples), pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        finally:
            doc.close()
        boxes = {u.id: u.bbox for u in project.units if u.location["page"] == page_no}
        self.view.show_image(image, boxes, set(project.warnings()))
        self.view.highlight(self.selected_id)

    def _show_pptx_preview(self) -> None:
        if self._pptx_preview is None or not self._pptx_preview.exists():
            self._busy(True, "PowerPoint でプレビューを作っています…")
            project = self.project
            temp_dir = Path(tempfile.mkdtemp(prefix="jt-preview-"))

            def work():
                translated = temp_dir / "deck.pptx"
                pptx_engine.render(project.source, project.units, translated)
                return preview.pptx_to_pdf(translated, temp_dir / "deck.pdf")

            self._run(work, self._on_pptx_preview_ready)
            return
        self._draw_pptx_page()

    def _on_pptx_preview_ready(self, pdf_path: Path) -> None:
        self._pptx_preview = pdf_path
        self._busy(False, "プレビューを更新しました")
        self._draw_pptx_page()

    def _draw_pptx_page(self) -> None:
        project = self.project
        if project is None or self._pptx_preview is None:
            return
        with fitz.open(self._pptx_preview) as doc:
            page = doc[min(self.page_index, doc.page_count - 1)]
            pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
            image = QImage(bytes(pix.samples), pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        boxes = {
            u.id: (u.extra["rect"][0], u.extra["rect"][1], u.extra["rect"][0] + u.extra["rect"][2], u.extra["rect"][1] + u.extra["rect"][3])
            for u in project.units
            if u.location["slide"] == self.page_index
        }
        self.view.show_image(image, boxes, set(project.warnings()))
        self.view.highlight(self.selected_id)

    # ---------- 作業中の表示・非同期 ----------

    def _busy(self, busy: bool, message: str) -> None:
        for w in (self.open_action, self.translate_action, self.export_action):
            w.setEnabled(not busy and (w is self.open_action or self.project is not None))
        self.statusBar().showMessage(message)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor) if busy else QApplication.restoreOverrideCursor()

    def _run(self, fn, on_done) -> None:
        job = Job(fn, self)
        job.done.connect(lambda result: self._finish(job, on_done, result))
        job.failed.connect(lambda message: self._fail(job, message))
        self._jobs.append(job)
        job.start()

    def _finish(self, job: Job, on_done, result) -> None:
        self._jobs.remove(job)
        on_done(result)

    def _fail(self, job: Job, message: str) -> None:
        if job in self._jobs:
            self._jobs.remove(job)
        self._busy(False, "失敗しました")
        QMessageBox.warning(self, "処理に失敗しました", message)

    def closeEvent(self, event) -> None:
        if self.project is not None and self.project.translated_count():
            try:
                self.project.save_sidecar()
            except OSError:
                pass
        super().closeEvent(event)


def _short(text: str, limit: int = 60) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _pptx_slide_count(path: Path) -> int:
    from pptx import Presentation

    return len(Presentation(str(path)).slides)


def run() -> int:
    app = QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Yu Gothic UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()
