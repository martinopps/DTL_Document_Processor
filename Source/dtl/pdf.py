from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .models import UserError


def font_name():
    if 'DTLSans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('DTLSans',str(Path(__file__).parent/'assets/DejaVuSans.ttf')))
    return 'DTLSans'

@dataclass(frozen=True)
class Stamp:
    name: str
    number: str
    contract: str
    required: str
    amount: str
    paid: str | None
    placement: str = 'Top margin'
    font_size: int = 10

    def lines(self):
        return [f'CLIENT: {self.name}', f'CLIENT #: {self.number}',f'CONTRACT #: {self.contract}',
                f'COPAY REQUIRED: {self.required.upper()}',f'COPAY AMOUNT: ${self.amount}',
                f'COPAY PAID: {"UNKNOWN / NOT CHECKED" if self.paid is None else "$"+self.paid}']


def read_pdf(source):
    try:
        reader = PdfReader(source,strict=False)
        if reader.is_encrypted:
            raise UserError('This PDF is password protected. Use an approved unprotected copy.')
        if not reader.pages:
            raise UserError('This PDF has no pages.')
        return reader
    except UserError:
        raise
    except Exception:
        raise UserError('The PDF cannot be opened. It may still be copying, damaged, or locked. Wait and refresh, or flag it.') from None


def stamped_bytes(source,stamp):
    reader = read_pdf(source)
    writer = PdfWriter()
    working = PdfWriter()
    working.add_page(reader.pages[0])
    page = working.pages[0]
    page.transfer_rotation_to_content()
    left,bottom = float(page.cropbox.left),float(page.cropbox.bottom)
    w,h = float(page.cropbox.width),float(page.cropbox.height)
    if left or bottom:
        page.add_transformation(Transformation().translate(-left,-bottom))
    page.mediabox = RectangleObject([0,0,w,h])
    page.cropbox = RectangleObject([0,0,w,h])
    font = font_name()
    fs = max(7,min(14,int(stamp.font_size)))
    lines = stamp.lines()
    glyphs = pdfmetrics.getFont(font).face.charToGlyph
    if any(ord(ch) not in glyphs for line in lines for ch in line):
        raise UserError('The stamp font cannot render part of this name or identifier. Flag the document and ask your administrator for a suitable approved font.')
    while max(pdfmetrics.stringWidth(s,font,fs) for s in lines)>w-36 and fs>6:
        fs -= .5
    if max(pdfmetrics.stringWidth(s,font,fs) for s in lines)>w-36:
        raise UserError('The stamp text is too wide for this page. Use an approved larger-page copy or flag it.')
    sh = 22+6*fs*1.3
    if h<sh+24 or w<100:
        raise UserError('This page is too small for the stamp. Flag it for manual review.')
    out_h = h+sh if stamp.placement=='Top margin' else h
    out_page = writer.add_blank_page(width=w,height=out_h)
    out_page.merge_page(page)
    buffer = BytesIO()
    c = canvas.Canvas(buffer,pagesize=(w,out_h))
    box_w = min(w-24,max(pdfmetrics.stringWidth(s,font,fs) for s in lines)+16)
    x = w-box_w-12 if stamp.placement=='Upper right' else 12
    y = out_h-10
    c.setFillColorRGB(1,1,1)
    c.rect(x-4,y-sh+8,box_w+4,sh-4,fill=1,stroke=0)
    c.setFillColorRGB(.05,.12,.2)
    c.setFont(font,fs)
    for line in lines:
        c.drawString(x,y-fs,line)
        y-=fs*1.3
    c.save()
    out_page.merge_page(PdfReader(BytesIO(buffer.getvalue())).pages[0])
    for p in reader.pages[1:]:
        writer.add_page(p)
    output=BytesIO()
    writer.write(output)
    return output.getvalue()


def merge_bytes(sources):
    writer=PdfWriter()
    for src in sources:
        reader=read_pdf(BytesIO(src) if isinstance(src,bytes) else src)
        for p in reader.pages:
            writer.add_page(p)
    output=BytesIO()
    writer.write(output)
    return output.getvalue()


def verify(data,pages):
    if len(read_pdf(BytesIO(data)).pages)!=pages:
        raise UserError('Output verification failed. The original has been preserved.')
