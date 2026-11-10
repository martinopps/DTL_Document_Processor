import sys
from pathlib import Path
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
import pytest
from reportlab.pdfgen import canvas
from dtl.storage import Store
from dtl.models import Client
from dtl.pdf import Stamp

@pytest.fixture
def store(tmp_path):
    obj=Store(tmp_path/'workspace')
    yield obj
    obj.close()

@pytest.fixture
def client():
    return Client('Synthetic Alpha','Synthetic','Alpha','0007','TEST-A')

@pytest.fixture
def pdf_factory():
    def create(path,text='SYNTHETIC ATTENDANCE',pages=2,size=(612,792)):
        path.parent.mkdir(parents=True,exist_ok=True)
        c=canvas.Canvas(str(path),pagesize=size)
        for i in range(pages):
            c.drawString(25,size[1]-25,f'{text} PAGE {i+1}')
            c.line(20,size[1]-55,size[0]-20,size[1]-55)
            c.drawString(25,60,'Fictional fixture. No real client data.')
            c.showPage()
        c.save()
        os.utime(path,(1_700_000_000,1_700_000_000))
        return path
    return create

@pytest.fixture
def stamp_for():
    return lambda c,**kw:Stamp(c.name,c.number,c.contract,'Yes','25.00',None,**kw)
