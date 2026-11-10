"""Synthetic-only UI acceptance tests, including the complete employee flow."""
from dataclasses import replace
import os
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from pypdf import PdfReader
from dtl.ui_backend import Store, Copay
from dtl.ui import Window
from dtl.models import Client, UserError
from dtl.storage import digest

@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    return app

@pytest.fixture
def window(tmp_path, app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: QMessageBox.StandardButton.Ok)
    backend = Store(tmp_path/'gui')
    win = Window(backend)
    yield win
    win.close()


def setup_document(win, pdf_factory):
    p = pdf_factory(win.store.folder('Intake')/'fictional.pdf', 'SYNTHETIC UI FLOW', 2)
    win.refresh_queue()
    cs = [Client('Synthetic Alpha','Synthetic','Alpha','0007','TEST-A'),
          Client('Synthetic Alpha','Synthetic','Alpha','0007','TEST-B'),
          Client('Synthetic Alpha','Synthetic','Alpha','0008','TEST-A')]
    win.clients = cs
    win.client_name.addItems(['Synthetic Alpha'])
    win.client_name.setCurrentText('Synthetic Alpha')
    win.select_name()
    return p


def confirm_form(win):
    win.record.setCurrentIndex(1)
    assert win.contract_choice.currentIndex() == 0
    win.contract_choice.setCurrentIndex(1)
    win.required.setCurrentText('Yes')
    win.amount.setText('0.00')
    win.paid.setText('')
    win.single.setChecked(True)
    win.position.setCurrentText('Add top margin')
    win.preview()
    assert win.preview_valid
    win.confirm.setChecked(True)
    assert win.save_button.isEnabled()


def test_full_gui_flow_name_only_ambiguity_manual_fields(window,pdf_factory):
    p=setup_document(window,pdf_factory)
    original=p.read_bytes()
    assert [window.client_name.itemText(i) for i in range(window.client_name.count())] == ['Synthetic Alpha']
    assert window.record.count()==3  # placeholder plus two explicit identities
    assert window.record.currentIndex()==0
    assert not window.save_button.isEnabled()
    confirm_form(window)
    assert window.client_number.text()=='0007'
    assert window.contract_number.text()=='TEST-A'
    assert window.paid.text()==''
    window.save()
    outputs=list(window.store.folder('Contract_Output').glob('*/*.pdf'))
    assert len(outputs)==1 and len(PdfReader(outputs[0]).pages)==2
    text=PdfReader(outputs[0]).pages[0].extract_text()
    assert 'COPAY AMOUNT: $0.00' in text and 'UNKNOWN' in text
    assert next(window.store.folder('Processed_Originals').glob('*.pdf')).read_bytes()==original
    assert not window.save_button.isEnabled()
    assert window.required.currentIndex()==0 and window.amount.text()=='' and window.paid.text()==''
    assert any(state=='processed' for path,state,h in window.entries)
    window.undo()
    assert p.read_bytes()==original and not outputs[0].exists()


def test_validation_retains_document(window,pdf_factory):
    p=setup_document(window,pdf_factory)
    window.record.setCurrentIndex(1)
    window.contract_choice.setCurrentIndex(1)
    window.single.setChecked(True)
    window.amount.setText('25.00')
    window.preview()  # required Yes/No unconfirmed
    assert window.current_source==p and not window.preview_valid
    assert not window.save_button.isEnabled()
    window.required.setCurrentText('No')
    window.amount.setText('-1')
    window.preview()
    assert window.current_source==p and not window.preview_valid


def test_changed_form_invalidates_preview(window,pdf_factory):
    setup_document(window,pdf_factory)
    confirm_form(window)
    window.amount.setText('25.00')
    assert not window.preview_valid and not window.confirm.isChecked() and not window.save_button.isEnabled()


def test_source_changed_after_preview_is_rejected(window,pdf_factory):
    p=setup_document(window,pdf_factory)
    confirm_form(window)
    pdf_factory(p, 'SYNTHETIC CHANGED INPUT', 3)
    window.save()
    assert p.exists() and window.current_source==p
    assert not list(window.store.folder('Contract_Output').glob('*/*.pdf'))


def test_paid_unknown_and_zero():
    assert Copay.parse('No','0','').paid is None
    assert Copay.parse('No','0','0').paid == 0
    with pytest.raises(UserError): Copay.parse('— Choose —','0','0')
