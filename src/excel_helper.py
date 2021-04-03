import xlsxwriter
import datetime
import os

def translate(text):
    if type(text) != str:
        return text

    dictionary = {
        'symbol' : 'זיהוי של ניר הערך',
        'sale_value_usd' : 'ערך נקוב במכירה',
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
        'Total sales' : 'סכום מכירות'
    }

    try:
        translated_str = dictionary[text]
    except KeyError:
        translated_str = text

    return translated_str


def write_row(worksheet, row_number, values_list):
    for col_num in range(0, len(values_list)):
        val = values_list[col_num]
        # Try to translate
        val = translate(val)
        if type(val) == datetime.datetime:
            val = val.__str__().split(' 00:00:00')[0]
        worksheet.write(row_number, col_num, val)
    return  row_number + 1

# Return (worksheet/None, next_row)
def gen_excel_file(file_name, header_list, values_matrix, close_workbook=True):
    from .tax_generator import GENERATED_FILES_DIR
    next_row = 0
    complete_filename = os.path.join(GENERATED_FILES_DIR, file_name + '.xlsx')

    # Create an new Excel file and add a worksheet.
    workbook = xlsxwriter.Workbook(complete_filename)
    try:
        worksheet = workbook.add_worksheet()
        headers_and_data = [header_list] + values_matrix
        for row_number in range(0, len(headers_and_data)):
            next_row = write_row(worksheet, row_number, headers_and_data[row_number])

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