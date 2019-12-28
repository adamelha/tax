from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfFileWriter, PdfFileReader


pdfmetrics.registerFont(TTFont('Hebrew', 'Arial.ttf'))

user_data = {
    'name': 'אדם אלחכם',
    'id-number': 201390085
}

class PdfText:
    def __init__(self, text, x, y, space_between_chars=False):
        '''For coordinante system where origin is top left and x and y are in inches.'''
        self.x = x * inch
        self.y = y * inch
        if type(text) is str:
            self.text = text[::-1]
            self.direction = 'RTL'
        elif type(text) is int:
            self.text = str(text)
            self.direction = 'LTR'
        if space_between_chars:
            self.text = ' '.join(self.text)
        self.convert_top_left_origin_to_bottom_left_origin()
    def convert_top_left_origin_to_bottom_left_origin(self):
        self.y = 11.69 * inch - self.y

class XMark(PdfText):
    def __init__(self, x, y):
        super().__init__('x', x, y)

form_1322_data = [PdfText(user_data['name'], 7.25, 1.82),
                  PdfText(user_data['id-number'], 1.61, 1.83, space_between_chars=True),
                  XMark(0.95, 1.77), # mehira letzad kashur - no
                  XMark(7.34, 2.23), # My ownership - yes
                  XMark(6.71, 2.67),
                  ]

foriegn_assets_1322 = XMark(2.45, 2.24)
non_foriegn_assets_1322 = XMark(2.03, 2.24)
tax_deducted_by_broker_1322 = [XMark(5.82, 2.48)]
tax_not_deducted_1_1322 = [ XMark(3.61, 2.48), XMark(3.42, 2.62)]
tax_not_deducted_2_1322 = [ XMark(3.61, 2.48), XMark(3.42, 2.79)]


def iterate_and_draw(pdftext_list, canvas):
    for rec in pdftext_list:
        if rec.direction == 'RTL':
            canvas.drawRightString(rec.x, rec.y, rec.text)
        else:
            canvas.drawString(rec.x, rec.y, rec.text)



def generate_form1322_pdf(form1322_appendix_list, input_file, output_file, tax_deduction='by_broker', is_foreign_asset=False):
    '''tax_deduction must be in ('by_broker', 'not_deducted_1', 'not_deducted_2')'''
    if tax_deduction not in ('by_broker', 'not_deducted_1', 'not_deducted_2'):
        raise Exception("tax_deduction arg must be one of ('by_broker', 'not_deducted_1', 'not_deducted_2')")

    pdf_text_list = [PdfText('אדם אלחכם', 7.25, 1.82)]
    packet = io.BytesIO()
    # create a new PDF with Reportlab
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont('Hebrew', 14)


    if is_foreign_asset:
        form_1322_list = form_1322_data + [foriegn_assets_1322]
    else:
        form_1322_list = form_1322_data + [non_foriegn_assets_1322]

    if tax_deduction == 'by_broker':
        form_1322_list += tax_deducted_by_broker_1322
    elif tax_deduction == 'not_deducted_1':
        form_1322_list += tax_not_deducted_1_1322
    else:
        form_1322_list += tax_not_deducted_2_1322

    iterate_and_draw(form_1322_list, can)



    can.save()
    # move to the beginning of the StringIO buffer
    packet.seek(0)
    new_pdf = PdfFileReader(packet)
    # read your existing PDF
    existing_pdf = PdfFileReader(open(input_file, "rb"))
    output = PdfFileWriter()
    # add the "watermark" (which is the new pdf) on the existing page
    page = existing_pdf.getPage(0)
    page.mergePage(new_pdf.getPage(0))
    output.addPage(page)
    # finally, write "output" to a real file
    outputStream = open(output_file, "wb")
    output.write(outputStream)
    outputStream.close()
