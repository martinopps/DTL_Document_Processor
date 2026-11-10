from io import BytesIO
import pytest
from pypdf import PdfReader,PdfWriter
from dtl.pdf import stamped_bytes, read_pdf
from dtl.models import UserError

@pytest.mark.parametrize('placement',['Top margin','Upper left','Upper right'])
@pytest.mark.parametrize('size',[(612,792),(842,595)])
def test_first_page_stamp_and_preservation(tmp_path,pdf_factory,client,stamp_for,placement,size):
    p=pdf_factory(tmp_path/'synthetic.pdf',size=size,pages=3)
    before=p.read_bytes()
    out=stamped_bytes(p,stamp_for(client,placement=placement))
    r=PdfReader(BytesIO(out)); original=PdfReader(BytesIO(before))
    assert len(r.pages)==3 and p.read_bytes()==before
    assert 'CLIENT #: 0007' in r.pages[0].extract_text()
    assert 'COPAY PAID: UNKNOWN' in r.pages[0].extract_text()
    assert 'SYNTHETIC ATTENDANCE PAGE 1' in r.pages[0].extract_text()
    for i in [1,2]:
        assert r.pages[i].extract_text()==original.pages[i].extract_text()
        assert r.pages[i].get_contents().get_data()==original.pages[i].get_contents().get_data()
    expected_height=size[1]+100 if placement=='Top margin' else size[1]
    assert float(r.pages[0].mediabox.height)==expected_height

@pytest.mark.parametrize('rotation',[90,180,270])
def test_rotation(tmp_path,pdf_factory,client,stamp_for,rotation):
    p=pdf_factory(tmp_path/'raw.pdf',pages=1)
    w=PdfWriter();w.add_page(PdfReader(p).pages[0]);w.pages[0].rotate(rotation)
    out=BytesIO();w.write(out)
    r=PdfReader(BytesIO(stamped_bytes(BytesIO(out.getvalue()),stamp_for(client))))
    assert r.pages[0].rotation==0 and 'CLIENT:' in r.pages[0].extract_text()


def test_encrypted_and_corrupt(tmp_path,pdf_factory):
    with pytest.raises(UserError):read_pdf(BytesIO(b'not a pdf'))
    p=pdf_factory(tmp_path/'raw.pdf',pages=1)
    w=PdfWriter();w.add_page(PdfReader(p).pages[0]);w.encrypt('secret');out=BytesIO();w.write(out)
    with pytest.raises(UserError):read_pdf(BytesIO(out.getvalue()))


def test_unsupported_name_glyph_is_not_silently_replaced(tmp_path,pdf_factory,client,stamp_for):
    from dataclasses import replace
    p=pdf_factory(tmp_path/'synthetic.pdf',pages=1)
    unsupported=replace(client,name='Synthetic \U0001f9ec')
    with pytest.raises(UserError,match='font cannot render'):
        stamped_bytes(p,stamp_for(unsupported))
