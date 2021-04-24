import xlsxwriter
import datetime
import os

from .user_data_helper import user_data


def translate(text):
    if type(text) != str:
        return text

    dictionary = {
        'symbol' : 'זיהוי של ניר הערך',
        'sale_value_usd' : 'ערך נקוב במכירה ($)',
        'purchase_date' : 'תאריך הרכישה',
        'orig_price_ils' : 'מחיר מקורי',
        'usd_sale_to_purchase_rate' : '1 + שיעור עליית המדד',
        'adjusted_price' : 'מחיר מתואם',
        'sale_date' : 'תאריך המכירה',
        'sale_value' : 'תמורה',
        'profit_loss' : 'רווח\הפסד למס',
        'date' : 'תאריך',
        'dividend_value_usd' : 'דיבידנד ב-$',
        'dividend_value_ils' : 'דיבידנד בש"ח',
        'rate' : 'יחס המרה',
        'tax_deducted_ils' : 'מס שנוכה במקור בש"ח',
        'Total profits' : 'סה"כ רווח הון',
        'Total losses' : 'סה"כ הפסד הון',
        'Total sales' : 'סכום מכירות',
        'value_usd': 'ערך בדולר',
        'value_ils': 'ערך בש"ח',
        'usd_ils_rate': 'יחס המרה דולר לש"ח',

    }

    try:
        translated_str = dictionary[text]
    except KeyError:
        translated_str = text

    return translated_str


def write_row(worksheet, row_number, values_list, workbook, bold=False, underline=False, font_size=None, align=None,
              highlighted_cols=None):
    if highlighted_cols is None:
        highlighted_cols = []
    worksheet_extra_args = []
    format_dict = {}
    if bold:
        format_dict['bold'] = True
    if underline:
        format_dict['underline'] = True
    if font_size:
        format_dict['font_size'] = font_size
    if align:
        format_dict['align'] = align

    for col_num in range(0, len(values_list)):
        val = values_list[col_num]
        # Try to translate
        val = translate(val)
        if type(val) == datetime.datetime:
            val = val.__str__().split(' 00:00:00')[0]
        if col_num in highlighted_cols:
            format_dict['bg_color'] = 'yellow'

        if format_dict:
            worksheet_extra_args = [workbook.add_format(format_dict)]

        worksheet.write(row_number, col_num, val, *worksheet_extra_args)

        if 'bg_color' in format_dict:
            del format_dict['bg_color']
        worksheet_extra_args = []
    return  row_number + 1

# Return (worksheet/None, next_row)
def gen_excel_file(file_name, header_list, values_matrix, description, close_workbook=True):
    from .tax_generator import GENERATED_FILES_DIR
    def get_personal_info_str():
        name = user_data['name'][::-1]
        name_heb = 'שם'[::-1]
        id_number = user_data['id-number'][::-1]
        id_heb = 'ת"ז'[::-1]
        tax_file_number = id_number
        tax_file_number_heb = 'מספר תיק'[::-1]
        phone_number = user_data['phone-number'][::-1]
        phone_heb = 'טלפון'[::-1]

        s = f'{phone_number} :{phone_heb} ,{tax_file_number} :{tax_file_number_heb} ,{id_number} :{id_heb} ,{name} :{name_heb}'

        return s[::-1]

    complete_filename = os.path.join(GENERATED_FILES_DIR, file_name + '.xlsx')

    # Create an new Excel file and add a worksheet.
    workbook = xlsxwriter.Workbook(complete_filename)
    try:
        worksheet = workbook.add_worksheet()

        # Write personal info at top of worksheet
        merge_format = workbook.add_format({
            'bold': 1,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })

        worksheet.merge_range('A1:I2', get_personal_info_str(), merge_format)

        # Write file description
        merge_format = workbook.add_format({
            'bold': 1,
            'underline': 1,
            'font_size': 22,
            'align': 'center',
            'valign': 'vcenter'
        })

        worksheet.merge_range('C3:E4', description, merge_format)

        # Write header
        header_row_number = 5
        next_row = write_row(worksheet, header_row_number, header_list, workbook, bold=True, underline=True)

        # Write data
        values_row_number = 6
        for row_number in range(values_row_number, len(values_matrix) + values_row_number):
            next_row = write_row(worksheet, row_number, values_matrix[row_number - values_row_number], workbook)

        if close_workbook:
            workbook.close()
            workbook = None

        return workbook, worksheet, next_row
    except Exception as e:
        workbook.close()
        print('Error in Excel file generation')
        raise e

def close_workbook(workbook):
    workbook.close()