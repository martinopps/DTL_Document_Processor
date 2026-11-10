"""Additional synthetic-only durability and PDF image-preservation checks."""
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import pytest
from pypdf import PdfReader
from dtl.storage import Store, digest
from dtl.models import UserError
from dtl.pdf import stamped_bytes
import dtl.storage as storage


def test_restart_rolls_back_interrupted_append(tmp_path,pdf_factory,client,stamp_for,monkeypatch):
    root=tmp_path/'workspace'
    store=Store(root)
    try:
        one=pdf_factory(store.folder('intake')/'one.pdf','RESTART FIRST',1)
        dest=store.process(one,client,11,2026,stamp_for(client),True)
        before=dest.read_bytes()
        two=pdf_factory(store.folder('intake')/'two.pdf','RESTART SECOND',2)
        original=two.read_bytes()
        monkeypatch.setattr(store,'mark_stale',lambda *_:(_ for _ in ()).throw(OSError('fictional failure')))
        monkeypatch.setattr(store,'rollback_pending',lambda *_:(_ for _ in ()).throw(RuntimeError('fictional termination')))
        with pytest.raises(RuntimeError):store.process(two,client,11,2026,stamp_for(client),True)
        assert dest.read_bytes()!=before
    finally:
        store.close()
    recovered=Store(root)
    try:
        assert dest.read_bytes()==before and two.read_bytes()==original
        assert recovered.db.execute("SELECT count(*) FROM actions WHERE status='done'").fetchone()[0]==1
        assert not recovered.db.execute("SELECT 1 FROM actions WHERE status='pending'").fetchone()
    finally:
        recovered.close()


def test_archive_failure_preserves_intake(store,pdf_factory,client,stamp_for,monkeypatch):
    source=pdf_factory(store.folder('intake')/'source.pdf','ARCHIVE FAILURE',2)
    before=source.read_bytes()
    real=storage.atomic_write
    archive=store.folder('archive')
    def fail(path,data):
        if Path(path).parent==archive:
            raise OSError('synthetic storage full')
        return real(path,data)
    monkeypatch.setattr(storage,'atomic_write',fail)
    with pytest.raises(OSError):store.process(source,client,11,2026,stamp_for(client),True)
    assert source.read_bytes()==before and not list(store.folder('output').glob('*/*.pdf'))
    assert not store.db.execute('SELECT 1 FROM groups').fetchone()
    assert not store.db.execute("SELECT 1 FROM actions WHERE status='pending'").fetchone()


def test_contract_sanitization_collisions_separate_masters(store,pdf_factory,client,stamp_for):
    clients=[replace(client,contract='TEST:A'),replace(client,contract='TEST?A')]
    dests=[]
    for i,c in enumerate(clients):
        source=pdf_factory(store.folder('intake')/f'{i}.pdf',f'SANITIZE-{i}',1)
        dests.append(store.process(source,c,11,2026,stamp_for(c),True))
    assert dests[0].parent!=dests[1].parent
    store.masters(11,2026)
    masters=list(store.folder('master').glob('*/*.pdf'))
    assert len(masters)==2 and masters[0].parent!=masters[1].parent
    for master in masters:
        text=PdfReader(master).pages[0].extract_text()
        assert ('CONTRACT #: TEST:A' in text) != ('CONTRACT #: TEST?A' in text)


def test_unmanaged_master_is_never_overwritten(store,pdf_factory,client,stamp_for):
    source=pdf_factory(store.folder('intake')/'one.pdf','MASTER OWNER',1)
    store.process(source,client,11,2026,stamp_for(client),True)
    store.masters(11,2026)
    master=next(store.folder('master').glob('*/*.pdf'))
    before=master.read_bytes()
    master.with_suffix('.owner').unlink()
    with pytest.raises(UserError):store.masters(11,2026)
    assert master.read_bytes()==before and store.is_stale(11,2026)


def test_scanned_pixels_survive_first_page_stamp(tmp_path,client,stamp_for):
    from PIL import Image,ImageDraw
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    image=Image.new('RGB',(400,600),'white')
    draw=ImageDraw.Draw(image)
    draw.text((12,12),'FICTIONAL SCAN',fill='black')
    for y in range(50,550,40):draw.line((10,y,390,y),fill='blue',width=2)
    path=tmp_path/'fictional-scan.pdf'
    c=canvas.Canvas(str(path),pagesize=(612,792))
    for _ in range(2):
        c.drawImage(ImageReader(image),0,0,612,792);c.showPage()
    c.save()
    original=PdfReader(path)
    out=PdfReader(BytesIO(stamped_bytes(path,stamp_for(client))))
    def pixels(page):
        objects=page['/Resources']['/XObject'].get_object()
        return [(obj.get_object()['/Width'],obj.get_object()['/Height'],digest(obj.get_object().get_data()))
                for obj in objects.values() if obj.get_object().get('/Subtype')=='/Image']
    assert pixels(out.pages[0])==pixels(original.pages[0])
    assert pixels(out.pages[1])==pixels(original.pages[1])
    assert len(out.pages)==2
