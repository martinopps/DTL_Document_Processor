import calendar
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from io import BytesIO
from .storage import digest, DEFAULT_WORKBOOK
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QCheckBox,
    QListWidget, QSplitter, QScrollArea, QMessageBox, QFileDialog, QDialog,
    QDialogButtonBox, QCompleter, QGroupBox)
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from .models import UserError
from .ui_backend import Copay, names, sheets, headers, stamp
from .excel import import_clients
from .pdf import read_pdf

def button(text, action, layout):
    b = QPushButton(text)
    b.clicked.connect(action)
    layout.addWidget(b)
    return b


class MappingDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle('Local workbook • approval and column mapping')
        self.resize(650, 600)
        layout = QVBoxLayout(self)
        warning = QLabel('Read the workbook only after employer approval. It is opened locally, read-only.\nOnly names, client numbers and contract numbers are imported.')
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.approved = QCheckBox('Employer has approved this local workbook and workstation')
        layout.addWidget(self.approved)
        form = QFormLayout()
        layout.addLayout(form)
        settings = store.load_settings()
        self.path = QLineEdit(settings.get('workbook', DEFAULT_WORKBOOK))
        form.addRow('Workbook', self.path)
        button('Choose workbook…', self.browse, layout)
        button('Load worksheets (requires approval)', self.load_sheets, layout)
        self.sheet = QComboBox()
        form.addRow('Worksheet', self.sheet)
        self.row = QSpinBox()
        self.row.setRange(1, 1000)
        self.row.setValue(settings.get('header_row', 1))
        form.addRow('Header row', self.row)
        button('Load column headers', self.load_headers, layout)
        self.columns = {}
        for key, label in [('full','Full Name (or map First + Last)'), ('first','First Name'), ('last','Last Name'), ('number','Client Number'), ('contract','Contract Number')]:
            combo = QComboBox()
            combo.addItem('— Not mapped —', None)
            self.columns[key] = combo
            form.addRow(label, combo)
        note = QLabel('For full names, “Last, First” is recognized; otherwise the final word\n(and common suffix) is used. Verify the editable filing last name on every save.\nNo workbook copay columns are used.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.loaded = None
        boxes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        boxes.accepted.connect(self.validate)
        boxes.rejected.connect(self.reject)
        layout.addWidget(boxes)

    def browse(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Choose approved local workbook', str(self.store.root), 'Excel workbook (*.xlsx)')
        if p:
            self.path.setText(p)

    def load_sheets(self):
        if not self.approved.isChecked():
            QMessageBox.information(self, 'Approval required', 'Confirm employer approval before reading the workbook.')
            return
        try:
            self.sheet.clear()
            self.sheet.addItems(sheets(self.path.text()))
            saved = self.store.load_settings().get('sheet', '')
            if saved:
                self.sheet.setCurrentText(saved)
        except Exception:
            QMessageBox.warning(self, 'Workbook unavailable', 'Cannot read this workbook. Check its path, format and permissions.')

    def load_headers(self):
        if not self.approved.isChecked() or not self.sheet.currentText():
            return
        try:
            columns = headers(self.path.text(), self.sheet.currentText(), self.row.value())
            for key, combo in self.columns.items():
                combo.clear()
                combo.addItem('— Not mapped —', None)
                for i, name in enumerate(columns):
                    combo.addItem(f'Column {i+1}: {name}', i)
                index = self.store.load_settings().get('mapping', {}).get(key)
                combo.setCurrentIndex(index + 1 if index is not None and index < len(columns) else 0)
            self.loaded = (self.path.text(), self.sheet.currentText(), self.row.value())
        except Exception:
            QMessageBox.warning(self, 'Mapping unavailable', 'Cannot read headers. Verify the worksheet and header row.')

    def validate(self):
        mapping = {k: c.currentData() for k, c in self.columns.items()}
        if not self.approved.isChecked() or self.loaded != (self.path.text(), self.sheet.currentText(), self.row.value()):
            QMessageBox.warning(self, 'Load headers', 'Load headers for the current workbook, sheet and header row first.')
            return
        if mapping['number'] is None or mapping['contract'] is None or (mapping['full'] is None and (mapping['first'] is None or mapping['last'] is None)):
            QMessageBox.warning(self, 'Mapping incomplete', 'Map a full name or both first and last names, plus client and contract numbers.')
            return
        chosen = [x for x in mapping.values() if x is not None]
        if len(set(chosen)) != len(chosen):
            QMessageBox.warning(self, 'Mapping conflict', 'Map each role to a separate column.')
            return
        self.result_settings = {'workbook': self.path.text(), 'sheet': self.sheet.currentText(), 'header_row': self.row.value(), 'mapping': mapping, 'employer_approved': True}
        self.accept()


class Window(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.settings = store.load_settings()
        self.clients = []
        self.entries = []
        self.current_source = None
        self.preview_valid = False
        self.preview_path = store.root / 'Config' / 'preview.pdf'
        self.setWindowTitle('DTL Document Processor • Local only')
        self.resize(self.settings.get('width', 1400), self.settings.get('height', 900))
        split = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(split)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel('<b>Intake queue</b>'))
        self.progress = QLabel()
        ll.addWidget(self.progress)
        self.queue_list = QListWidget()
        self.queue_list.currentRowChanged.connect(self.select_document)
        ll.addWidget(self.queue_list)
        button('Refresh Intake', self.refresh_queue, ll)
        button('Previous', self.previous, ll)
        button('Skip / Flag', self.flag, ll)
        button('Undo Last Processing Action', self.undo, ll)
        button('Return flagged PDF to queue', self.unflag, ll)
        button('Folder settings…', self.folder_settings, ll)
        split.addWidget(left)
        center = QWidget()
        cl = QVBoxLayout(center)
        toolbar = QHBoxLayout()
        cl.addLayout(toolbar)
        self.pdf_document = QPdfDocument(self)
        self.viewer = QPdfView()
        self.viewer.setDocument(self.pdf_document)
        self.viewer.setPageMode(QPdfView.PageMode.MultiPage)
        self.viewer.setZoomMode(QPdfView.ZoomMode.FitInView)
        button('−', lambda: self.zoom(.8), toolbar)
        button('+', lambda: self.zoom(1.25), toolbar)
        button('Fit Page', lambda: self.viewer.setZoomMode(QPdfView.ZoomMode.FitInView), toolbar)
        button('Fit Width', lambda: self.viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth), toolbar)
        button('◀ Page', lambda: self.page(-1), toolbar)
        button('Page ▶', lambda: self.page(1), toolbar)
        self.page_label = QLabel('0 pages')
        cl.addWidget(self.page_label)
        cl.addWidget(self.viewer, 1)
        button('Show untouched original', self.show_original, cl)
        split.addWidget(center)
        right = QWidget()
        rl = QVBoxLayout(right)
        form = QFormLayout()
        rl.addLayout(form)
        form.addRow(QLabel('<b>Processing period</b>'))
        self.month = QComboBox()
        self.month.addItems(list(calendar.month_name)[1:])
        self.month.setCurrentIndex(self.settings.get('month', datetime.now().month)-1)
        self.year = QSpinBox()
        self.year.setRange(1900, 2200)
        self.year.setValue(self.settings.get('year', datetime.now().year))
        form.addRow('Month', self.month)
        form.addRow('Year', self.year)
        button('Workbook mapping…', self.map_workbook, rl)
        button('Refresh approved client list', self.load_clients, rl)
        form.addRow(QLabel('<b>Client information</b>'))
        self.client_name = QComboBox()
        self.client_name.setEditable(True)
        self.client_name.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.client_name.activated.connect(self.select_name)
        self.client_name.editTextChanged.connect(self.name_edited)
        form.addRow('Client Name', self.client_name)
        self.record = QComboBox()
        self.record.currentIndexChanged.connect(self.select_record)
        form.addRow('Verify identity', self.record)
        self.contract_choice = QComboBox()
        self.contract_choice.currentIndexChanged.connect(self.select_contract)
        form.addRow('Confirm contract', self.contract_choice)
        self.client_number = QLineEdit()
        self.client_number.setReadOnly(True)
        self.contract_number = QLineEdit()
        self.contract_number.setReadOnly(True)
        form.addRow('Client Number', self.client_number)
        form.addRow('Contract Number', self.contract_number)
        self.last = QLineEdit()
        form.addRow('Verified filing last name', self.last)
        form.addRow(QLabel('<b>Manual copay • confirm each document</b>'))
        self.required = QComboBox()
        self.required.addItems(['— Choose —', 'Yes', 'No'])
        self.amount = QLineEdit()
        self.amount.setPlaceholderText('Required, e.g. 0.00')
        self.paid = QLineEdit()
        self.paid.setPlaceholderText('Blank = unknown; 0.00 = checked')
        form.addRow('Copay Required', self.required)
        form.addRow('Copay Amount', self.amount)
        form.addRow('Copay Paid', self.paid)
        self.position = QComboBox()
        self.position.addItems(['Upper left', 'Upper right', 'Add top margin'])
        self.position.setCurrentText(self.settings.get('position', 'Upper left'))
        self.font = QSpinBox()
        self.font.setRange(7, 14)
        self.font.setValue(self.settings.get('font', 10))
        form.addRow('Stamp location', self.position)
        form.addRow('Stamp font size', self.font)
        self.single = QCheckBox('I verified all pages belong to this single client')
        self.single.setToolTip('Sheets containing different clients must be flagged for approved manual separation.')
        rl.addWidget(self.single)
        self.preview_button = button('Preview permanent stamp', self.preview, rl)
        self.confirm = QCheckBox('Preview checked: period, IDs, copay and no covered writing')
        self.confirm.setWordWrap(True) if hasattr(self.confirm, 'setWordWrap') else None
        rl.addWidget(self.confirm)
        self.save_button = button('Save & Next', self.save, rl)
        self.save_button.setDefault(True)
        self.auto_next = QCheckBox('Open next queued PDF after saving')
        self.auto_next.setChecked(self.settings.get('auto_next', True))
        rl.addWidget(self.auto_next)
        button('Generate Master Contract PDFs', self.generate_masters, rl)
        stale = self.store.db.execute('SELECT COUNT(*) FROM masters WHERE stale=1').fetchone()[0]
        self.feedback = QLabel('Masters need regeneration.' if stale else 'Choose a document and map an approved workbook to begin.')
        self.feedback.setWordWrap(True)
        rl.addWidget(self.feedback)
        rl.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(right)
        split.addWidget(scroll)
        split.setSizes(self.settings.get('splitter', [250, 700, 450]))
        self.splitter = split
        for widget in (self.month, self.year, self.last, self.required, self.amount, self.paid, self.position, self.font):
            signal = getattr(widget, 'textChanged', None) or getattr(widget, 'valueChanged', None) or widget.currentIndexChanged
            signal.connect(self.invalidate)
        self.single.stateChanged.connect(self.invalidate)
        self.confirm.stateChanged.connect(self.update_save)
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.save)
        self.refresh_queue()
        # Deliberately do not read a workbook at startup. The refresh button is an explicit local runtime action.
        self.update_save()

    def failure(self, exc):
        message = str(exc) if isinstance(exc, UserError) else 'The operation could not finish. Check available disk space, local file access and permissions, then retry. Your original remains recoverable.'
        QMessageBox.warning(self, 'Action needs attention', message)

    def persist(self):
        self.settings.update(month=self.month.currentIndex()+1, year=self.year.value(), position=self.position.currentText(), font=self.font.value(), auto_next=self.auto_next.isChecked(), width=self.width(), height=self.height(), splitter=self.splitter.sizes())
        self.store.settings(self.settings)

    def invalidate(self, *args):
        self.preview_valid = False
        self.preview_digest = None
        self.confirm.setChecked(False)
        if hasattr(self, 'save_button'):
            self.update_save()

    def update_save(self, *args):
        self.save_button.setEnabled(bool(self.current_source and self.selected_client() and self.preview_valid and self.confirm.isChecked() and self.single.isChecked()))

    def selected_client(self):
        c = self.contract_choice.currentData()
        if c and self.client_name.currentText() == c.name and self.last.text().strip():
            return replace(c, last=self.last.text().strip())
        return None

    def name_edited(self, *args):
        self.record.clear()
        self.contract_choice.clear()
        self.client_number.clear()
        self.contract_number.clear()
        self.invalidate()

    def select_name(self, *args):
        name = self.client_name.currentText()
        self.record.clear()
        self.record.addItem('— Verify identity —', None)
        identities = sorted({(c.number, c.first, c.last) for c in self.clients if c.name == name})
        for number, first, last in identities:
            self.record.addItem(f'Client #: {number} • {first} {last}', (number, first, last))
        # Always explicit, including unique matches; duplicate visible names remain name-only above.
        self.record.setCurrentIndex(0)

    def select_record(self, *args):
        self.contract_choice.clear()
        self.contract_choice.addItem('— Confirm contract —', None)
        item = self.record.currentData()
        self.client_number.clear()
        self.contract_number.clear()
        self.last.clear()
        if item:
            number, first, last = item
            self.client_number.setText(number)
            self.last.setText(last)
            for c in self.clients:
                if c.name == self.client_name.currentText() and (c.number,c.first,c.last) == item:
                    self.contract_choice.addItem(c.contract, c)
        self.invalidate()

    def select_contract(self, *args):
        c = self.contract_choice.currentData()
        self.contract_number.setText(c.contract if c else '')
        self.invalidate()

    def map_workbook(self):
        dialog = MappingDialog(self.store, self)
        if dialog.exec():
            self.settings.update(dialog.result_settings)
            self.persist()
            self.load_clients()

    def load_clients(self):
        if not self.settings.get('employer_approved') or not self.settings.get('mapping'):
            self.map_workbook()
            return
        try:
            self.clients, warnings = import_clients(self.settings['workbook'], self.settings['sheet'], self.settings['mapping'], self.settings.get('header_row', 1))
            # One identifier cannot silently represent different names.
            by_id = {}
            for c in self.clients:
                by_id.setdefault(c.number, set()).add(c.name.casefold())
            if any(len(v) > 1 for v in by_id.values()):
                self.clients = []
                raise UserError('A client number maps to different names. Resolve the source records before processing.')
            self.client_name.clear()
            self.client_name.addItems(names(self.clients))
            self.client_name.setCurrentIndex(-1)
            complete = QCompleter(names(self.clients), self)
            complete.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            complete.setFilterMode(Qt.MatchFlag.MatchContains)
            complete.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self.client_name.setCompleter(complete)
            complete.activated[str].connect(self.complete_name)
            self.feedback.setText(f'{len(names(self.clients))} client names loaded locally.')
            if warnings:
                QMessageBox.warning(self, 'Workbook review', '\n\n'.join(warnings))
        except Exception as exc:
            self.clients = []
            self.client_name.clear()
            self.failure(exc)

    def complete_name(self, text):
        self.client_name.setCurrentText(text)
        self.select_name()

    def refresh_queue(self, keep=None):
        try:
            self.entries = self.store.queue()
            self.queue_list.blockSignals(True)
            self.queue_list.clear()
            for p, state, h in self.entries:
                self.queue_list.addItem(f'[{state}] {p.name}')
            self.queue_list.blockSignals(False)
            selected = next((i for i,e in enumerate(self.entries) if keep and e[0] == keep), None)
            if selected is None:
                selected = next((i for i,e in enumerate(self.entries) if e[1] == 'queued'), -1)
            self.queue_list.setCurrentRow(selected)
            if selected == -1:
                self.select_document(-1)
            done = sum(e[1]=='processed' for e in self.entries)
            self.progress.setText(f'Document {selected+1 if selected >= 0 else 0} of {len(self.entries)} • {done} completed')
        except Exception as exc:
            self.failure(exc)

    def select_document(self, index):
        self.current_source = None
        self.pdf_document.close()
        self.required.setCurrentIndex(0)
        self.amount.clear()
        self.paid.clear()
        self.single.setChecked(False)
        self.client_name.setCurrentIndex(-1)
        self.client_name.setEditText('')
        self.name_edited()
        self.invalidate()
        if index < 0 or index >= len(self.entries):
            return
        path, state, h = self.entries[index]
        self.progress.setText(f'Document {index+1} of {len(self.entries)} • {sum(e[1]=="processed" for e in self.entries)} completed')
        try:
            read_pdf(path)
            self.load_view(path)
            if state == 'queued':
                self.current_source = path
            self.feedback.setText('Visually verify every page. Multiple clients on one scan? Flag for manual review.' if state == 'queued' else f'Status: {state}. Saving is disabled; undo to reclassify a completed action.')
        except Exception as exc:
            self.feedback.setText('Unreadable or incomplete PDF. Wait and refresh, or flag for review.')
            # Flagging remains available for unreadable queued documents.
            self.current_source = path if state == 'queued' else None
        self.update_save()

    def load_view(self, path):
        self.pdf_document.close()
        error = self.pdf_document.load(str(path))
        if error != QPdfDocument.Error.None_:
            raise UserError('The embedded viewer could not open this PDF. Wait and refresh, or flag it.')
        self.page_label.setText(f'{self.pdf_document.pageCount()} pages • scroll to inspect all pages')
        self.viewer.pageNavigator().jump(0, self.viewer.pageNavigator().currentLocation())

    def show_original(self):
        index = self.queue_list.currentRow()
        if index >= 0:
            try:
                self.load_view(self.entries[index][0])
                self.invalidate()
            except Exception as exc:
                self.failure(exc)

    def zoom(self, factor):
        current = self.viewer.zoomFactor()
        self.viewer.setZoomMode(QPdfView.ZoomMode.Custom)
        self.viewer.setZoomFactor(max(.1, min(5., current*factor)))

    def page(self, delta):
        nav = self.viewer.pageNavigator()
        page = max(0, min(self.pdf_document.pageCount()-1, nav.currentPage()+delta))
        nav.jump(page, nav.currentLocation())

    def previous(self):
        self.queue_list.setCurrentRow(max(0, self.queue_list.currentRow()-1))

    def preview(self):
        try:
            c = self.selected_client()
            if not self.current_source or not c:
                raise UserError('Choose a queued document, client identity and contract; verify the filing last name.')
            if not self.single.isChecked():
                raise UserError('Verify that all pages belong to this single client. Flag documents with different clients.')
            copay = Copay.parse(self.required.currentText(), self.amount.text(), self.paid.text())
            self.pdf_document.close()
            source_data = self.current_source.read_bytes()
            stamp(BytesIO(source_data), self.preview_path, c, copay, self.position.currentText(), self.font.value())
            self.load_view(self.preview_path)
            self.preview_digest = digest(source_data)
            self.preview_valid = True
            self.confirm.setChecked(False)
            self.feedback.setText(f'Preview only • {self.month.currentText()} {self.year.value()}. Check stamp, all pages and writing; choose Add top margin if needed. Then confirm below.')
            self.update_save()
        except Exception as exc:
            self.invalidate()
            self.failure(exc)

    def save(self):
        try:
            if not self.save_button.isEnabled():
                raise UserError('Complete verification, preview the stamp and confirm the preview before saving.')
            self.save_button.setEnabled(False)
            c = self.selected_client()
            copay = Copay.parse(self.required.currentText(), self.amount.text(), self.paid.text())
            old = self.current_source
            self.store.process(old, c, copay, self.month.currentIndex()+1, self.year.value(), self.position.currentText(), self.font.value(), expected_digest=self.preview_digest)
            self.persist()
            self.refresh_queue(None if self.auto_next.isChecked() else self.store.archived_for(old))
            self.feedback.setText('Saved and verified. Original preserved. Monthly masters must be regenerated after changes.')
        except Exception as exc:
            self.failure(exc)
            self.update_save()

    def flag(self):
        index = self.queue_list.currentRow()
        if index < 0:
            return
        try:
            self.store.flag(self.entries[index][0])
            self.refresh_queue()
            self.feedback.setText('Flagged for manual review; untouched original retained in Intake.')
        except Exception as exc:
            self.failure(exc)

    def unflag(self):
        index = self.queue_list.currentRow()
        if index < 0 or self.entries[index][1] != 'flagged':
            return
        try:
            source = self.entries[index][0]
            self.store.unflag(source)
            self.refresh_queue(source)
        except Exception as exc:
            self.failure(exc)

    def undo(self):
        try:
            self.pdf_document.close()
            self.store.undo()
            self.refresh_queue()
            self.feedback.setText('Last action reversed. Earlier appended pages preserved. Regenerate stale masters.')
        except Exception as exc:
            self.failure(exc)

    def generate_masters(self):
        try:
            pending = sum(e[1] != 'processed' for e in self.store.queue())
            if pending and QMessageBox.question(self, 'Documents remain', f'{pending} documents are unprocessed, flagged or unavailable. Generate masters from completed outputs only?') != QMessageBox.StandardButton.Yes:
                return
            summary = self.store.masters(self.month.currentIndex()+1, self.year.value())
            QMessageBox.information(self, 'Master PDFs', '\n'.join(f'{contract}: {count} client PDF(s)' for contract,count in summary) or 'No completed client PDFs for this period.')
        except Exception as exc:
            self.failure(exc)

    def folder_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Local folders inside application root')
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Use relative paths under the application root. Keep folders separate.'))
        form = QFormLayout()
        layout.addLayout(form)
        fields = {}
        for name in ('Intake','Processed_Originals','Contract_Output','Flagged','Master_Contracts'):
            fields[name] = QLineEdit(self.settings.get('folders', {}).get(name, name))
            form.addRow(name, fields[name])
        boxes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        boxes.accepted.connect(dialog.accept)
        boxes.rejected.connect(dialog.reject)
        layout.addWidget(boxes)
        if dialog.exec():
            try:
                values = {name: self.store.within(self.store.root / edit.text().strip()) for name,edit in fields.items()}
                protected = [self.store.root / name for name in ('Config','Logs','Source','Tests','Build','.venv')]
                paths = list(values.values())
                if any(a==b or a in b.parents or b in a.parents for i,a in enumerate(paths) for b in paths[i+1:]) or any(a==b or b in a.parents or a in b.parents for a in paths for b in protected):
                    raise UserError('Choose separate data folders outside application code, configuration and build folders.')
                self.settings['folders'] = {k:str(v.relative_to(self.store.root)) for k,v in values.items()}
                self.persist()
                self.refresh_queue()
            except Exception as exc:
                self.failure(exc)

    def closeEvent(self, event):
        try:
            self.persist()
            self.pdf_document.close()
            self.preview_path.unlink(missing_ok=True)
        except Exception:
            pass
        self.store.close()
        event.accept()
