"""Generate only fictional QA artifacts; never run against production folders."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from reportlab.pdfgen import canvas
from PySide6.QtWidgets import QApplication
from dtl.ui_backend import Store
from dtl.ui import Window
from dtl.models import Client

root=Path(__file__).resolve().parents[1]/'Build/QA'
app=QApplication([]);app.setStyle('Fusion')
store=Store(root/'workspace');w=Window(store)
p=store.folder('Intake')/'fictional-attendance.pdf'
c=canvas.Canvas(str(p),pagesize=(612,792))
for page in range(2):
    c.setFont('Helvetica-Bold',16)
    c.drawString(25,760,'SYNTHETIC ATTENDANCE - QA ONLY')
    c.setFont('Helvetica',12)
    c.drawString(25,735,'Fictional fixture. No real patient information.')
    c.drawString(25,705,f'Page {page+1} - original writing near top edge')
    for y in range(650,130,-45):
        c.line(25,y,585,y)
        c.drawString(30,y+10,'Fictional entry / signature placeholder')
    c.showPage()
c.save();os.utime(p,(1700000000,1700000000))
w.refresh_queue()
w.clients=[Client('Synthetic Alpha','Synthetic','Alpha','0007','TEST-A')]
w.client_name.addItem('Synthetic Alpha');w.client_name.setCurrentText('Synthetic Alpha');w.select_name()
w.record.setCurrentIndex(1);w.contract_choice.setCurrentIndex(1)
w.required.setCurrentText('Yes');w.amount.setText('25.00');w.paid.setText('0.00');w.single.setChecked(True)
w.position.setCurrentText('Add top margin');w.preview();w.show()
app.processEvents()
w.grab().save(str(root/'desktop.png'))
(root/'stamp-preview.pdf').write_bytes(w.preview_path.read_bytes())
w.resize(1280,800);app.processEvents();w.grab().save(str(root/'desktop-laptop.png'))
w.close()
