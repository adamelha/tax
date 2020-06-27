import json
import os

from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfFileWriter, PdfFileReader


pdfmetrics.registerFont(TTFont('Hebrew', 'Arial.ttf'))

f = os.path.join(os.path.dirname(os.path.realpath(__file__)),'config.json')
with open(f, encoding='utf-8') as json_data:
    user_data_dict = json.load(json_data)
    print(user_data_dict)

user_data = {k: user_data_dict[k]['value'] for k in user_data_dict.keys() }
user_data['name'] = user_data['first-name'] + ' ' + user_data['last-name']

class PdfText:
    def __init__(self, text, x, y, space_between_chars=False, direction=None, empty_string_if_zero=False, reverse_text=True):
        '''For coordinante system where origin is top left and x and y are in inches.'''
        self.x = x * inch
        self.y = y * inch
        if type(text) is str:
            self.text = text
            if direction:
                self.direction = direction
            else:
                self.direction = 'RTL'
            if self.direction == 'RTL':
                if reverse_text:
                    self.text = text[::-1]
        elif type(text) is int:
            self.direction = 'LTR'
            if empty_string_if_zero and text == 0:
                self.text = ''
            else:
                self.text = str(text)
        elif type(text) is float:
            self.direction = 'LTR'
            if empty_string_if_zero and text < 0.1:
                self.text = ''
            else:
                if text < 0.1:
                    self.text = '0'
                else:
                    self.text = str(round(text))
        if space_between_chars:
            self.text = ' '.join(self.text)
        self.convert_top_left_origin_to_bottom_left_origin()
    def convert_top_left_origin_to_bottom_left_origin(self):
        self.y = 11.69 * inch - self.y

class XMark(PdfText):
    def __init__(self, x, y):
        super().__init__('x', x, y)

# Form 1322 marks
form_1322_data = [PdfText(user_data['name'], 7.25, 1.82),
                  PdfText(user_data['id-number'], 1.61, 1.83, space_between_chars=True, reverse_text=False),
                  XMark(0.95, 1.77), # mehira letzad kashur - no
                  XMark(0.95, 2.23), # mehira metzad kashur - no
                  XMark(7.34, 2.23), # My ownership - yes
                  XMark(6.71, 2.67),
                  PdfText(user_data['name'], 4.64, 10),
                  PdfText(user_data['date'], 6.25, 10, direction='LTR'),
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

def try_to_deduct(deduct_from, detuct_credits):
    if detuct_credits == 0:
        return deduct_from, 0, 0
    if detuct_credits <= deduct_from:
        remaining = deduct_from - detuct_credits
        detuct_credits_left = 0
    else:
        remaining = 0
        detuct_credits_left = detuct_credits - deduct_from

    credits_used = detuct_credits - detuct_credits_left
    return remaining, detuct_credits_left, credits_used

# Return what is left from losses - to be inserted as loss_from_previous in next call
# Return <credits_left_from_prev, credits_left_from_stock)
def generate_form1322_pdf(form_1325, input_file, output_file, tax_deduction='by_broker', is_foreign_asset=False,
                          credits_from_prev=0, credits_from_stock=0, form1322_appendix_list=None, dividends=None,
                          interests=None):
    '''tax_deduction must be in ('by_broker', 'not_deducted_1', 'not_deducted_2')'''
    if tax_deduction not in ('by_broker', 'not_deducted_1', 'not_deducted_2'):
        raise Exception("tax_deduction arg must be one of ('by_broker', 'not_deducted_1', 'not_deducted_2')")

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

    # Profit from stocks without losses
    form_1322_list += [PdfText(form_1325.total_profits, 2.9, 5)]

    # Loss from previous
    remaining_profit, deduct_credits_left_from_prev, credits_used_from_prv = try_to_deduct(form_1325.total_profits, credits_from_prev)
    form_1322_list += [PdfText(credits_used_from_prv, 2.9, 5.74, empty_string_if_zero=True)]

    # Loss from stock
    remaining_profit, detuct_credits_left_from_stock, credits_used_from_stock = try_to_deduct(remaining_profit, credits_from_stock)
    form_1322_list += [PdfText(credits_used_from_stock, 2.9, 5.37, empty_string_if_zero=True)]

    # Amount taxable
    amount_taxable = form_1325.total_profits - credits_used_from_prv - credits_used_from_stock
    form_1322_list += [PdfText(amount_taxable, 2.9, 6.83)]

    # Total sales
    form_1322_list += [PdfText(form_1325.total_sales, 4.4, 7.2)]
    dividends_and_interest_profits_including_deduction = None
    if tax_deduction == 'not_deducted_2':
        if not dividends:
            print('No dividends??? Please make sure that you did not receive any dividends!!!')
        if not interests:
            print('No interest??? Please make sure that you did not receive any interest on cash!!!')
        total_cash_interest = interests.get_total_ils()
        total_dividends = dividends.get_total_ils()
        total_dividends_and_cash_interest = total_cash_interest + total_dividends
        form_1322_list += [PdfText(total_dividends_and_cash_interest, 1.54, 8)]

        # Note: I cannot deduct dividend profits with deduct_credits_left_from_prev -
        # only with stock losses from this year.

        remaining_profit, detuct_credits_left_from_stock, credits_used_from_stock = try_to_deduct(total_dividends_and_cash_interest,
                                                                                                  detuct_credits_left_from_stock)
        form_1322_list += [PdfText(credits_used_from_stock, 1.54, 8.46)]
        form_1322_list += [PdfText(detuct_credits_left_from_stock, 4.31, 9.56)]

        dividends_and_interest_profits_including_deduction = total_dividends_and_cash_interest - credits_used_from_stock
        form_1322_list += [PdfText(dividends_and_interest_profits_including_deduction, 1.54, 9.21)]

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
    output_stream = open(output_file, "wb")
    output.write(output_stream)
    output_stream.close()

    return deduct_credits_left_from_prev, detuct_credits_left_from_stock, dividends_and_interest_profits_including_deduction

form_1324_data = [PdfText(user_data['first-name'], 7.6, 2.77),
                  PdfText(user_data['last-name'], 5.85, 2.77),
                  PdfText(user_data['id-number'], 2.7, 2.77, space_between_chars=True, reverse_text=False),
                  ]


def generate_form1324_pdf(template_pdf, output_pdf, form1325, dividends, dividends_profits_including_deduction):


    # Page 1
    form_1324_page1_list = form_1324_data + [PdfText(dividends_profits_including_deduction, 1.89, 8.02)]
    form_1324_page1_list += [PdfText(dividends.get_total_ils_deducted(), 0.44, 8.02)]
    form_1324_page1_list += [PdfText(form1325.total_sales, 1.89, 10.37)]

    # Page 2
    form_1324_page2_list = [PdfText(dividends_profits_including_deduction, 1.95, 5.36)]
    form_1324_page2_list += [XMark(3.93, 8.45)]
    form_1324_page2_list += [PdfText(user_data['date'], 6.41, 9.48, direction='LTR')]


    packet = [None] * 2
    output = PdfFileWriter()
    for page_num, form_page_list in enumerate([form_1324_page1_list, form_1324_page2_list]):

        packet[page_num] = io.BytesIO()
        # create a new PDF with Reportlab
        can = canvas.Canvas(packet[page_num], pagesize=letter)
        can.setFont('Hebrew', 14)

        iterate_and_draw(form_page_list, can)

        can.save()
        # move to the beginning of the StringIO buffer
        packet[page_num].seek(0)
        new_pdf = PdfFileReader(packet[page_num])
        # read your existing PDF
        existing_pdf = PdfFileReader(open(template_pdf, "rb"))

        # add the "watermark" (which is the new pdf) on the existing page
        page = existing_pdf.getPage(page_num)
        page.mergePage(new_pdf.getPage(0))
        output.addPage(page)
    # finally, write "output" to a real file
    output_stream = open(output_pdf, "wb")
    output.write(output_stream)
    output_stream.close()