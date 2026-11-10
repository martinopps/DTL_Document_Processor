"""Workbook mapping and search tests against the current GUI API."""
from openpyxl import Workbook
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from dtl.ui import MappingDialog, Window
from dtl.ui_backend import Store


def test_mapping_dialog_synthetic_approval_and_mapping(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: QMessageBox.StandardButton.Ok)
    store=Store(tmp_path/'workspace')
    win=Window(store)
    try:
        p=tmp_path/'synthetic.xlsx'
        b=Workbook();s=b.active;s.title='Fixtures'
        s.append(['Name','ID','Contract']);s.append(['Synthetic Alpha','0007','TEST-A']);b.save(p)
        d=MappingDialog(store,win)
        d.path.setText(str(p))
        d.load_sheets()
        assert d.sheet.count()==0  # approval is required even for reading schema
        d.approved.setChecked(True)
        d.load_sheets();d.load_headers()
        assert d.sheet.currentText()=='Fixtures'
        for key,idx in [('full',0),('number',1),('contract',2)]:
            d.columns[key].setCurrentIndex(d.columns[key].findData(idx))
        d.validate()
        assert d.result_settings['mapping']['number']==1
        win.settings.update(d.result_settings)
        win.persist();win.load_clients()
        assert len(win.clients)==1 and win.clients[0].number=='0007'
        assert win.client_name.itemText(0)=='Synthetic Alpha'
        complete=win.client_name.completer()
        assert complete.filterMode()==Qt.MatchFlag.MatchContains
        assert complete.caseSensitivity()==Qt.CaseSensitivity.CaseInsensitive
        complete.setCompletionPrefix('Alpha')
        assert complete.completionCount()==1
        complete.setCompletionPrefix('Synthetic')
        assert complete.completionCount()==1
        d.close()
    finally:
        win.close()
