from dataclasses import replace
from decimal import Decimal
from io import BytesIO
import json
import os
from pathlib import Path
import pytest
from pypdf import PdfReader
from dtl.models import UserError, money, safe_component
from dtl.storage import Store, digest
import dtl.storage as storage

@pytest.mark.parametrize('bad',['','-1','1.001','NaN','1,000','abc','+1','1e2'])
def test_currency_rejects(bad):
    with pytest.raises(UserError):money(bad)

def test_payment_unknown_distinct_zero():
    assert money('',True) is None
    assert money('$0.00',True)==Decimal('0.00')
    assert money('25')==Decimal('25.00')

@pytest.mark.parametrize('bad',['../outside','a/b','a\\b','..','\x00'])
def test_unsafe_names(bad):
    with pytest.raises(UserError):safe_component(bad)

def process(store,pdf_factory,client,stamp_for,name,text,pages=1,month=11):
    src=pdf_factory(store.folder('intake')/name,text,pages)
    original=src.read_bytes()
    dest=store.process(src,client,month,2026,stamp_for(client),confirmed=True)
    return src,dest,original


def test_append_idempotency_and_exact_undo(store,pdf_factory,client,stamp_for):
    src,dest,original=process(store,pdf_factory,client,stamp_for,'one.pdf','FIRST',pages=2)
    first_output=dest.read_bytes()
    assert not src.exists()
    archive=next(store.folder('archive').glob('*.pdf'))
    assert archive.read_bytes()==original
    src2,dest2,original2=process(store,pdf_factory,client,stamp_for,'two.pdf','SECOND',pages=3)
    assert dest==dest2 and len(PdfReader(dest).pages)==5
    assert 'FIRST' in PdfReader(dest).pages[0].extract_text()
    assert 'SECOND' in PdfReader(dest).pages[2].extract_text()
    src2.write_bytes(original2);os.utime(src2,(1,1))
    with pytest.raises(UserError,match='already'):store.process(src2,client,11,2026,stamp_for(client),True)
    store.undo()
    assert src2.read_bytes()==original2 and dest.read_bytes()==first_output
    store.undo()
    assert src.read_bytes()==original and not dest.exists()


def test_collisions_and_contract_routing(store,pdf_factory,client,stamp_for):
    _,a,_=process(store,pdf_factory,client,stamp_for,'one.pdf','ONE')
    other=replace(client,name='Other Alpha',first='Other',number='0008')
    _,b,_=process(store,pdf_factory,other,stamp_for,'two.pdf','TWO')
    assert a!=b and len(PdfReader(a).pages)==len(PdfReader(b).pages)==1
    other=replace(other,contract='TEST-B')
    _,c,_=process(store,pdf_factory,other,stamp_for,'three.pdf','THREE')
    assert c.parent.name=='TEST-B' and a.parent.name=='TEST-A'


def test_unmanaged_output_is_preserved(store,pdf_factory,client,stamp_for):
    folder=store.folder('output')/'TEST-A';folder.mkdir()
    unmanaged=pdf_factory(folder/'Alpha_DTL_November_2026.pdf','UNMANAGED',1)
    before=unmanaged.read_bytes()
    _,dest,_=process(store,pdf_factory,client,stamp_for,'one.pdf','NEW')
    assert dest!=unmanaged and unmanaged.read_bytes()==before


def test_master_order_contract_period_and_regeneration(store,pdf_factory,client,stamp_for):
    z=replace(client,name='Zed Zulu',first='Zed',last='Zulu',number='90')
    b=replace(client,name='Bert Alpha',first='Bert',number='20')
    a=replace(client,name='Amy Alpha',first='Amy',number='10')
    for i,c in enumerate([z,b,a,replace(a,contract='TEST-B'),replace(z,contract='TEST-C')]):
        process(store,pdf_factory,c,stamp_for,f'{i}.pdf',f'FIXTURE-{i}',month=10 if i==4 else 11)
    summary=store.masters(11,2026)
    assert sorted((c,n) for c,n,_ in summary)==[('TEST-A',3),('TEST-B',1)]
    masters=list(store.folder('master').glob('*/*.pdf'));assert len(masters)==2
    master=next(p for p in masters if p.parent.name=='TEST-A')
    text=[p.extract_text() for p in PdfReader(master).pages]
    assert ['Amy Alpha' in text[0],'Bert Alpha' in text[1],'Zed Zulu' in text[2]]==[True]*3
    assert not any('FIXTURE-4' in t for t in text)
    process(store,pdf_factory,a,stamp_for,'extra.pdf','EXTRA')
    assert store.is_stale(11,2026) and master.with_suffix('.STALE.txt').exists()
    store.masters(11,2026)
    assert len(PdfReader(master).pages)==4 and not master.with_suffix('.STALE.txt').exists()
    store.undo();assert store.is_stale(11,2026)
    store.masters(11,2026);assert len(PdfReader(master).pages)==3


def test_write_failure_rolls_back_append(store,pdf_factory,client,stamp_for,monkeypatch):
    _,dest,_=process(store,pdf_factory,client,stamp_for,'one.pdf','FIRST')
    before=dest.read_bytes()
    src=pdf_factory(store.folder('intake')/'two.pdf','SECOND',1)
    original=src.read_bytes()
    real=storage.atomic_write
    calls=[]
    def fail_once(path,data):
        if Path(path)==dest and not calls:
            calls.append(1)
            raise OSError('synthetic disk full')
        return real(path,data)
    monkeypatch.setattr(storage,'atomic_write',fail_once)
    with pytest.raises(OSError):store.process(src,client,11,2026,stamp_for(client),True)
    assert dest.read_bytes()==before and src.read_bytes()==original
    assert store.db.execute("SELECT count(*) FROM actions WHERE status='done'").fetchone()[0]==1


def test_crash_pending_recovery(store,pdf_factory,client,stamp_for,monkeypatch):
    _,dest,_=process(store,pdf_factory,client,stamp_for,'one.pdf','FIRST')
    before=dest.read_bytes()
    src=pdf_factory(store.folder('intake')/'two.pdf','SECOND',1)
    real=store.rollback_pending
    def interrupted(*_):raise RuntimeError('simulate immediate termination before rollback')
    monkeypatch.setattr(store,'rollback_pending',interrupted)
    monkeypatch.setattr(store,'mark_stale',lambda *_: (_ for _ in ()).throw(OSError('synthetic interruption')))
    with pytest.raises(RuntimeError):store.process(src,client,11,2026,stamp_for(client),True)
    assert dest.read_bytes()!=before
    monkeypatch.setattr(store,'rollback_pending',real)
    store.recover()
    assert dest.read_bytes()==before and src.exists()


def test_crash_undo_recovery(store,pdf_factory,client,stamp_for,monkeypatch):
    _,dest,_=process(store,pdf_factory,client,stamp_for,'one.pdf','FIRST')
    before=dest.read_bytes()
    src,_,orig=process(store,pdf_factory,client,stamp_for,'two.pdf','SECOND')
    real=store.finish_undo
    monkeypatch.setattr(store,'finish_undo',lambda *_: (_ for _ in ()).throw(OSError('synthetic interruption')))
    with pytest.raises(OSError):store.undo()
    monkeypatch.setattr(store,'finish_undo',real)
    store.recover()
    assert src.read_bytes()==orig and dest.read_bytes()==before


def test_copying_flagging_and_permissions(store,pdf_factory):
    src=pdf_factory(store.folder('intake')/'bad.pdf','TEST',1)
    os.utime(src,None)
    with pytest.raises(UserError,match='copying'):store.stable_source(src)
    src.write_bytes(b'broken pdf');os.utime(src,(1,1))
    store.flag(src)
    assert store.status(digest(src.read_bytes()))=='Flagged' and src.exists()
    store.unflag(src)
    assert store.status(digest(src.read_bytes()))=='Queued'
    if os.name != 'nt':
        for p in [store.path('Config'),store.path('Config/audit.sqlite')]:
            assert p.stat().st_mode & 0o077==0


def test_sandbox_and_lock(store,tmp_path):
    with pytest.raises(UserError):store.path('../escape')
    with pytest.raises(UserError):Store(store.root)


def test_symlink_escape(store,tmp_path):
    link=store.root/'escape'
    try:
        link.symlink_to(tmp_path.parent,target_is_directory=True)
    except OSError:
        if os.name == 'nt':
            pytest.skip('Windows symlink creation requires Developer Mode or privilege')
        raise
    with pytest.raises(UserError):store.path('escape/file.pdf')


def test_missing_confirmations(store,pdf_factory,client,stamp_for):
    src=pdf_factory(store.folder('intake')/'one.pdf','ONE',1)
    with pytest.raises(UserError):store.process(src,client,11,2026,stamp_for(client))
    with pytest.raises(UserError):store.process(src,client,11,2026,replace(stamp_for(client),required=''),True)
    assert src.exists()


def test_external_modification_blocks_undo_append(store,pdf_factory,client,stamp_for):
    _,dest,_=process(store,pdf_factory,client,stamp_for,'one.pdf','FIRST')
    dest.write_bytes(b'externally changed')
    with pytest.raises(UserError):store.undo()
    src=pdf_factory(store.folder('intake')/'two.pdf','SECOND',1)
    with pytest.raises(UserError):store.process(src,client,11,2026,stamp_for(client),True)
    assert src.exists() and dest.read_bytes()==b'externally changed'
