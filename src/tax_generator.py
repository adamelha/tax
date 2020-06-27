from copy import deepcopy
from xlrd import open_workbook
from xlrd import xldate
import csv
import datetime
import texttable as tt
from excel_helper import gen_excel_file, write_row, close_workbook
import os
import requests
import win32com.client  # pip install pypiwin32
import io
from pdf_helpers import generate_form1322_pdf, generate_form1324_pdf

# Input parameters with default values:
TAX_YEAR = 2019
LOSS_FROM_PREV_YEARS = 0
IB_ACTIVITY_STATEMENT_CSV = 'adam_ibkr_2019.csv'  # IB activity statement CSV file for the entire year (must include trades and dividends)
GET_EXCHANGE_RATES_FROM_WEB = False  # If False - use the BANK_OF_ISRAEL_DOLLAR_ILS_EXCHANGE_XLS file
EXCHANGE_RATES_FROM_WEB_START_DATE = '30-12-2018'  # All trades must be no earlier than this date
EXCHANGE_RATES_FROM_WEB_END_DATE = '31-12-2019' # All trades must be no later than this date
GENERATE_EXCEL_FILES = True  # Generate Excel files for appendixes. If False - just print the tables
GENERATED_FILES_DIR = 'generated_files'  # Dir to generate the files to
SPLIT_125_FORM = True

# Constants:
BANK_OF_ISRAEL_DOLLAR_ILS_EXCHANGE_XLS = 'ExchangeRates.xlsx'
BANK_OF_ISRAEL_DATE_COL = 0
BANK_OF_ISRAEL_RATE_COL = 1
IB_CODE_OPEN = 'O'
IB_CODE_CLOSE = 'C'
FORM_1322_FILE_NAME = 'Form1322'  # Excel file
INTERESTS_FILE_NAME = 'Interests'
FORM_1325_APPENDIX_FILE_NAME = 'Form1325_appendix'
FORM_1322_TEMPLATE_PDF = 'itc1322_18.pdf'
FORM_1322_DEDUCTED_OUTPUT_PDF = os.path.join(GENERATED_FILES_DIR, 'Form1322_deducted.pdf')
FORM_1322_NOT_DEDUCTED_1_OUTPUT_PDF = os.path.join(GENERATED_FILES_DIR, 'Form1322_not_deducted_1st_half.pdf')
FORM_1322_NOT_DEDUCTED_2_OUTPUT_PDF = os.path.join(GENERATED_FILES_DIR, 'Form1322_not_deducted_2nd_half.pdf')

FORM_1324_TEMPLATE_PDF = 'itc1324_18.pdf'
FORM_1324_OUTPUT_PDF = os.path.join(GENERATED_FILES_DIR, 'Form1324.pdf')

def get_existing_exchange_date(date, dollar_ils_rate):
    """
    If exchange date does not exist in dict, there must be vacation in Israel
    So try a day earlier - until one exists
    :param date: date to search around
    :param dollar_ils_rate: parsed exchanges dictionary
    :return: datetime object as close as possible to date (but no later than date)
             with a rate that exists in dollar_ils_rate
    """

    search_range = 5
    exchange_date = None
    for i in range(0, search_range):
        if date - datetime.timedelta(i) in dollar_ils_rate:
            exchange_date = date - datetime.timedelta(i)
            break
    if exchange_date is None:
        raise Exception('USD/ILS exchange rate not found near closing date: {}'.format(date))
    return exchange_date


def dollar_ils_rate_parse_from_excel_file(file):
    book = open_workbook(file)
    sheet = book.sheet_by_index(0)

    dic = dict()
    for row in range(0, sheet.nrows):
        rate_cell = sheet.cell(row, BANK_OF_ISRAEL_RATE_COL)
        date_cell = sheet.cell(row, BANK_OF_ISRAEL_DATE_COL)
        try:

            rate = float(rate_cell.value)
        except Exception as e:
            # If exception converting the rate column to float -
            # we haven't reached the actual data yet. Go to next row
            continue

        datetime_obj = xldate.xldate_as_datetime(date_cell.value, book.datemode)
        dic[datetime_obj] = rate

    return dic


def dollar_ils_rate_parse_from_bank_of_israel_site():
    def convert_date(date_str):
        return date_str.replace('-', '%2F')

    def fetch_corrupted_excel_file():
        url = f'https://www.boi.org.il/Boi.ashx?Command=DownloadExcel&Currency=3&' \
              f'DateStart={convert_date(EXCHANGE_RATES_FROM_WEB_START_DATE)}' \
              f'&DateEnd={convert_date(EXCHANGE_RATES_FROM_WEB_END_DATE)}&webUrl=%2Fhe%2FMarkets%2FExchangeRates'
        return requests.get(url)

    def fix_corrupted_excel_file(temp_filename, filename):
        o = win32com.client.Dispatch("Excel.Application")
        o.Visible = False

        wb = o.Workbooks.Open(temp_filename)
        wb.ActiveSheet.SaveAs(filename, 51)
        try:
            wb.Close()
        except Exception:
            print(f'Error closing Excel file: {filename}. Continuing with script anyway')

    temp_filename = os.getcwd() + '/' + '_tmp_exchanges.xls'
    filename = os.getcwd() + '/' + '_exchanges.xlsx'
    if os.path.exists(temp_filename):
        os.remove(temp_filename)
    if os.path.exists(filename):
        os.remove(filename)

    response = fetch_corrupted_excel_file()
    with open(temp_filename, 'wb') as temp:
        temp.write(response.content)

    fix_corrupted_excel_file(temp_filename, filename)
    return dollar_ils_rate_parse_from_excel_file(filename)

def dollar_ils_rate_parse():
    if not GET_EXCHANGE_RATES_FROM_WEB:
        return dollar_ils_rate_parse_from_excel_file(BANK_OF_ISRAEL_DOLLAR_ILS_EXCHANGE_XLS)
    return dollar_ils_rate_parse_from_bank_of_israel_site()

class Trade():
    def __init__(self):
        self.symbol = ''
        self.commission = 0
        self.transaction_price = 0
        self.date = None
        self.total_shares_num = 0
        self.shares_left = 0
    def __str__(self):
        return 'Trade: symbol:{}, date:{} comm:{}, price:{}'.format(self.symbol, self.date, self.commission, self.transaction_price)

class TradeOpen(Trade):
    def __init__(self, **kwargs):
        super().__init__()
        for key, value in kwargs.items():  # kwargs is a regular dictionary
            setattr(self, key, value)
    def __repr__(self):
        return self.__str__()

class TradeClose(Trade):
    def __init__(self, **kwargs):
        super().__init__()
        self.realized = 0.0
        self.shares_covered = 0
        for key, value in kwargs.items():  # kwargs is a regular dictionary
            setattr(self, key, value)

    def __str__(self):
        return '{}, realized:{}'.format(super().__str__(), self.realized)
    def __repr__(self):
        return self.__str__()

'''
The trades will be held in the following data structure:
{
    'AMZN': [
        Trade0,
        Trade1,
        ...
        Traden
    ],
    'GOOGL': [
        Trade0,
        Trade1,
        ...
        Traden
    ]
}
'''
def trades_parse():
    dic = dict()
    transaction_list = []
    with open(IB_ACTIVITY_STATEMENT_CSV) as ib_csv_file:
        id = []
        for ln in ib_csv_file:
            if ln.startswith("Trades,"):
                id.append(ln)

        s = '\n'.join(id)

        csv_reader = csv.DictReader(io.StringIO(s))

        for row in csv_reader:
            try:
                open_close = row['Code']
            except Exception as e:
                print(e)
                continue

            if open_close == IB_CODE_OPEN or IB_CODE_OPEN + ';' in open_close:
                trade = TradeOpen()
            elif open_close == IB_CODE_CLOSE:
                trade = TradeClose()
                trade.realized = float(row['Realized P/L'])
            else:
                continue

            trade.symbol = row['Symbol']
            # Commssion is represented by a negative number - store it as positive
            # because we later add it to the original price
            trade.commission = abs(float(row['Comm/Fee']))
            trade.transaction_price = float(row['T. Price'])
            # row['Date/Time'] looks like this 2019-04-22, 14:04:29
            # We discard the part after the comma so the time is 0, as with the USD/ILS exchange file
            trade.date = datetime.datetime.strptime(row['Date/Time'].split(',')[0], '%Y-%m-%d')
            # Will be negative for sell transactions
            trade.total_shares_num = int(row['Quantity'].replace(',', ''))
            trade.shares_left = trade.total_shares_num
            # If symbol not in dic - create empty list for it
            if trade.symbol not in dic:
                dic[trade.symbol] = []

            # Append the trade to the list of trades for this symbol
            dic[trade.symbol].append(trade)

    return dic

class Dividend():
    def __init__(self):
        self.symbol = ''
        self.date = None
        self.value_usd = 0
        self.tax_deducted_usd = 0

'''
The dividends will be held in the following stucture:
[
    Dividend1,
    Dividend2,
    ...
    Dividendn,
]
'''
def dividends_parse():
    dividend_list = []
    dividend_helper_dict = {}
    with open(IB_ACTIVITY_STATEMENT_CSV) as ib_csv_file:
        id = []
        for ln in ib_csv_file:
            if ln.startswith("Dividends,"):
                id.append(ln)

        s = '\n'.join(id)

        csv_reader = csv.DictReader(io.StringIO(s))

        for row in csv_reader:
            # If end of dividends
            if row['Currency'] == 'Total':
                break

            dividend = Dividend()
            dividend.symbol = row['Description'].split('(')[0]
            # row['Date/Time'] looks like this 2019-04-22
            dividend.date = datetime.datetime.strptime(row['Date'], '%Y-%m-%d')
            dividend.value_usd = float(row['Amount'])
            dividend_list.append(dividend)
            dividend_helper_dict[f'{dividend.symbol}-{dividend.date}'] = dividend

    # Get tax deducted
    with open(IB_ACTIVITY_STATEMENT_CSV) as ib_csv_file:
        id = []
        for ln in ib_csv_file:
            if ln.startswith("Withholding Tax,"):
                id.append(ln)

        s = '\n'.join(id)

        csv_reader = csv.DictReader(io.StringIO(s))

        for row in csv_reader:
            # If end of dividends
            if row['Currency'] == 'Total':
                break
            symbol = row['Description'].split('(')[0]
            date = f'{row["Date"]} 00:00:00'
            dividend_helper_dict[f'{symbol}-{date}'].tax_deducted_usd = 0 - float(row['Amount'])

    return dividend_list


class Interest:
    def __init__(self, date, value_usd):
        self.exchanges_dict = None
        self.date = date
        self.value_usd = value_usd

    @property
    def value_ils(self):
        if self.exchanges_dict is None:
            raise Exception('Interest object not populated')
        return self.value_usd * self.exchanges_dict[get_existing_exchange_date(self.date, self.exchanges_dict)]

    def __str__(self):
        return 'date\tvalue_usd\tvalue_ils\tusd_ils_rate\n' \
               '<{}\t{}\t{}\t{}>'.format(self.date, self.value_usd, self.value_ils,
                                         self.exchanges_dict[get_existing_exchange_date(self.date, self.exchanges_dict)])

    def __repr__(self):
        return self.__str__()

    def to_list(self):
        return [self.date, self.value_usd, self.value_ils,
                self.exchanges_dict[get_existing_exchange_date(self.date, self.exchanges_dict)]]

    def populate(self, usd_ils_rate_dict):
        self.exchanges_dict = usd_ils_rate_dict

    
'''
The interests will be held in the following stucture:
[
    Interest1,
    Interest2,
    ...
    Interestn,
]
'''
def interest_parse():
    interest_list = []
    with open(IB_ACTIVITY_STATEMENT_CSV) as ib_csv_file:
        id = []
        for ln in ib_csv_file:
            if ln.startswith("Interest,"):
                id.append(ln)

        s = '\n'.join(id)

        csv_reader = csv.DictReader(io.StringIO(s))

        for row in csv_reader:
            # If end of interests
            if row['Currency'] == 'Total':
                break

            # interest.symbol = row['Description'].split('(')[0]
            # row['Date/Time'] looks like this 2019-04-22
            date = datetime.datetime.strptime(row['Date'], '%Y-%m-%d')
            value_usd = float(row['Amount'])
            interest_list.append(Interest(date, value_usd))

    return interest_list

class Form1325Entry():
    def __init__(self):
        self.symbol = ''
        self.sale_value_usd = 0.0
        self.purchase_date = None
        self.orig_price_ils = 0.0 # ILS price day of purchase
        self.usd_sale_to_purchase_rate = 0.0 # (usd/ils day of open) / (usd/ils day of open)
        self.adjusted_price = 0.0
        self.sale_date = None
        self.sale_value = 0.0  # In ILS, of the day of sale (TMURA)
        self.profit_loss = 0.0

    def __str__(self):
        return 'symbol\tsale_value_usd\tpurchase_date\torig_price_ils\tusd_sale_to_purchase_rate\tadjusted_price\tsale_date\tsale_value\tprofit_loss\n' \
               '<{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}>'.format(self.symbol, self.sale_value_usd, self.purchase_date, self.orig_price_ils, self.usd_sale_to_purchase_rate, self.adjusted_price, self.sale_date, self.sale_value, self.profit_loss)
    def __repr__(self):
        return self.__str__()
    def to_list(self):
        return [self.symbol, self.sale_value_usd, self.purchase_date, self.orig_price_ils, self.usd_sale_to_purchase_rate, self.adjusted_price, self.sale_date, self.sale_value, self.profit_loss]

    @staticmethod
    def to_header_list():
        return ['symbol', 'sale_value_usd', 'purchase_date', 'orig_price_ils', 'usd_sale_to_purchase_rate', 'adjusted_price', 'sale_date', 'sale_value', 'profit_loss']


class Form1325:
    def __init__(self):
        self.entry_list = []

    def add_totals(self):
        self.total_profits = sum([entry.profit_loss for entry in self.entry_list if entry.profit_loss >= 0])
        self.total_losses = sum([entry.profit_loss for entry in self.entry_list if entry.profit_loss < 0])
        self.total_sales = sum([entry.sale_value for entry in self.entry_list])

def _tax_to_pay(nominal_profit_loss, inflational_profit_loss):
    taxable = 0
    real_profit_lost = nominal_profit_loss - inflational_profit_loss
    # # Different signs
    # if inflational_profit_loss * nominal_profit_loss < 0:
    #     taxable = nominal_profit_loss
    # else:  # Same sign
    #     taxable = nominal_profit_loss - inflational_profit_loss
    #
    #     # If inflation causes a sign change - leave the profit at 0
    #     if nominal_profit_loss * taxable < 0:
    #         taxable = 0
    #
    # # If loss - disregard inflation
    # if taxable < 0:
    #     taxable = nominal_profit_loss

    def is_nominal_profit():
        return nominal_profit_loss >= 0
    def is_nominal_loss():
        return not is_nominal_profit()
    def is_inflational_profit():
        return inflational_profit_loss >= 0
    def is_inflational_loss():
        return not is_inflational_profit()
    def is_real_profit():
        return real_profit_lost >= 0
    def is_real_loss():
        return not is_real_profit()

    # These are the different cases:
    if is_nominal_profit() and is_inflational_profit() and is_real_profit():
        taxable = real_profit_lost
    elif is_nominal_profit() and is_inflational_loss() and is_real_profit():
        taxable = nominal_profit_loss
    elif is_nominal_loss() and is_inflational_loss() and is_real_profit():
        taxable = 0
    elif is_nominal_loss() and is_inflational_loss() and is_real_loss():
        taxable = real_profit_lost # This is according to example Meir
        #taxable = nominal_profit_loss # maybe this is the correct one? (according to form)
    elif is_nominal_loss() and is_inflational_profit() and is_real_loss():
        taxable = nominal_profit_loss
    elif is_nominal_profit() and is_inflational_profit() and is_real_loss():
        taxable = 0
    else:
        raise Exception("Encountered case that wasn't handled. Please fix bug")

    return taxable


def form1325_obj_create(trade_dic, dollar_ils_rate):
    '''
    Create Tofes 1325 nispah hey (5)
    Summery of selling of stock which were not taxed
    :param trade_dic: retrieved dictionary from trades_parse()
    :param dollar_ils_rate: retrieved list of usd/ils for each date. from dollar_ils_rate_parse()
    :return: list of Entry1325 objects
    '''
    # list of all lists of tuples of symbol. Each list of tuples corresponds to
    # one form1325 entry
    opening_shares_lists_for_all_symbols = []
    for symbol, trade_list in trade_dic.items():
        # Go to last transaction that is a closing position
        reversed_trade_list = reversed(trade_list)
        for closing_trade in trade_list:
            # opening_shares_list is list of tuples (TradeClose, TradeOpen, num_of_shares)
            # summing num_of_shares of all these tuples will equal to closing_trade.
            # In all tuples in the list, TradeClose will be the same
            opening_shares_list = []
            # The number of shares in opening_shares_list[-1] that were not used
            # to cover the closing.
            # residue_shares = 0
            if type(closing_trade) is TradeClose:
                # Found closing position, remember it, then iterate from start
                # of ordered list, to find enough opening shares
                # Those will be the shares closing the
                for opening_trade in trade_list:
                    if type(opening_trade) is TradeOpen:
                        # If no shares left in opening trade - skip to next trade
                        if opening_trade.shares_left == 0:
                            continue
                        covered = 0
                        # If opening trade shares cover all closing trade shares
                        if opening_trade.shares_left + closing_trade.shares_left >= 0:
                            covered += abs(closing_trade.shares_left)
                            opening_trade.shares_left += closing_trade.shares_left
                            closing_trade.shares_left = 0
                        # If all opening shares cover some closing shared
                        elif opening_trade.shares_left > 0 and opening_trade.shares_left + closing_trade.shares_left < 0:
                            covered += abs(opening_trade.shares_left)
                            closing_trade.shares_left += opening_trade.shares_left
                            opening_trade.shares_left = 0

                        opening_shares_list.append((closing_trade, opening_trade, covered))

                        # If nothing left to cover - exit loop and find earlier closing trade
                        if closing_trade.shares_left == 0:
                            break
            # At this point we have a list of tuples of opening trades covering closing_trade
            # Append it to the list of lists of the symbol
            if len(opening_shares_list) > 0:
                opening_shares_lists_for_all_symbols.append(opening_shares_list[:])

    entries = []
    # Now opening_shares_lists_for_all_symbols is populated
    for list_of_tuples_for_symbol in opening_shares_lists_for_all_symbols:
        print (list_of_tuples_for_symbol)
        # If len(list_of_tuples_for_symbol) > 1: this means one sale covers
        # multiple buys, and sale is split to 2 entries, one for each buy
        for tup in list_of_tuples_for_symbol:
            form_entry = Form1325Entry()
            # tup[0] is the TradeClose object
            # tup[1] is TradeOpen object
            # tup[2] is the number of shares TradeClose closed
            exchange_dates = [None, None]

            # If exchange date does not exist in dict, there must be vacation in Israel
            # So try a day earlier - until one exists
            for j in range(0,2):
                exchange_dates[j] = get_existing_exchange_date(tup[j].date, dollar_ils_rate)

            sell_date = exchange_dates[0]
            buy_date = exchange_dates[1]
            form_entry.symbol = tup[0].symbol
            form_entry.sale_value_usd = tup[0].transaction_price * tup[2]
            form_entry.purchase_date = tup[1].date
            form_entry.orig_price_ils = tup[1].transaction_price * tup[2] * dollar_ils_rate[buy_date]
            print(f'orig_price_ils = {form_entry.orig_price_ils}')
            form_entry.orig_price_ils += (tup[0].commission * dollar_ils_rate[sell_date] + tup[1].commission * dollar_ils_rate[buy_date])
            print(f'orig_price_ils = {form_entry.orig_price_ils}')
            # zero out the commissions so that we do not use them for other entries envolving this trade.
            # For instance buy 1, buy 1, sell 2: we split the sell trade to 2 entries, so we make sure
            # we only add the commission to the price once
            tup[0].commission = 0
            tup[1].commission = 0

            form_entry.sale_value = (tup[0].transaction_price * tup[2]) * dollar_ils_rate[sell_date]
            rate = dollar_ils_rate[sell_date] / dollar_ils_rate[buy_date]

            # https://fintranslator.com/israel-tax-schedules-passive-income-foreign-broker/
            # writes to do this: if madad has gone down in profit we, disregard it
            # and if madad has gone up in profit we, disregard it

            # Define the 'realized' as the difference between purchase (ILS that day) and orig price (ILS that day)
            tup[0].realized = form_entry.sale_value - form_entry.orig_price_ils
            # if tup[0].realized <= 0 and rate > 1:
            #     form_entry.usd_sale_to_purchase_rate = rate
            # elif tup[0].realized <= 0 and rate <= 1:
            #     form_entry.usd_sale_to_purchase_rate = 1
            # elif tup[0].realized > 0 and rate > 1:
            #     form_entry.usd_sale_to_purchase_rate = rate
            # elif tup[0].realized > 0 and rate <= 1:
            #     form_entry.usd_sale_to_purchase_rate = 1
            form_entry.sale_date = sell_date
            realized = tup[0].realized # hon nominali
            inflation = form_entry.orig_price_ils * (rate - 1)
            form_entry.profit_loss = _tax_to_pay(realized, inflation)


            # form_entry.profit_loss = form_entry.sale_value - form_entry.adjusted_price =>
            form_entry.adjusted_price = form_entry.sale_value - form_entry.profit_loss
            form_entry.usd_sale_to_purchase_rate = form_entry.adjusted_price / form_entry.orig_price_ils




            #form_entry.adjusted_price = form_entry.usd_sale_to_purchase_rate * form_entry.orig_price_ils
            #form_entry.sale_date = sell_date
            #print(f'{tup[0].transaction_price} * {tup[2]}) * {dollar_ils_rate[buy_date]}')

            #form_entry.profit_loss = form_entry.sale_value - form_entry.adjusted_price
            entries.append(form_entry)
    form = Form1325()
    form.entry_list = entries
    form.add_totals()
    return form


class Form1322AppendixEntry():
    def __init__(self, dividend):
        self.symbol = dividend.symbol
        self.date = dividend.date
        self.value_usd = dividend.value_usd
        self.rate = 0
        self.value_ils = 0
        self.tax_deducted_usd = dividend.tax_deducted_usd
        self.tax_deducted_ils = 0

    def populate(self, dollar_ils_rate):
        self.rate = dollar_ils_rate[get_existing_exchange_date(self.date, dollar_ils_rate)]
        self.value_ils = self.value_usd * self.rate
        self.tax_deducted_ils = self.tax_deducted_usd * dollar_ils_rate[
            get_existing_exchange_date(self.date, dollar_ils_rate)]

    @staticmethod
    def to_header_list():
        return ['symbol', 'date', 'dividend_value_usd', 'rate', 'dividend_value_ils', 'tax_deducted_ils']
    def to_list(self):
        return [self.symbol, self.date, self.value_usd, self.rate, self.value_ils, self.tax_deducted_ils]

def form1322_appendix_list_create(dividends_list, dollar_ils_rate):
    lst = []
    for div in dividends_list:
        entry = Form1322AppendixEntry(div)
        entry.populate(dollar_ils_rate)
        lst.append(entry)
    return lst

def sum_profit_loss(form1325_list):
    return sum([entry.profit_loss for entry in form1325_list])

def print_broker_form1099_retrieval_instructions():
    print('\nBroker tax form 1099:')
    print('In your Interactive Brokers account go to Reports > Tax > Tax Forms')

def print_form1325_list(form1325):
    if form1325.entry_list:
        tab = tt.Texttable()
        header_list = Form1325Entry.to_header_list()
        tab.header(header_list)
        values_list = []
        print('\nForm 1325 appendix 3 (nispah gimmel):')
        for entry in form1325.entry_list:
            #for row in zip(entry.to_list()):
            tab.add_row(entry.to_list())
            s = tab.draw()
            values_list += [entry.to_list()]
        print(s)
        print(f'Total profits: {form1325.total_profits}\tTotal losses: {form1325.total_losses}')
        print(f'Total sales {form1325.total_sales}')
        if GENERATE_EXCEL_FILES:
            workbook, worksheet, next_row = gen_excel_file(FORM_1325_APPENDIX_FILE_NAME, header_list, values_list, close_workbook=False)
            # Skip row
            next_row += 1
            next_row = write_row(worksheet, next_row, ['Total profits', form1325.total_profits])
            next_row = write_row(worksheet, next_row, ['Total losses', form1325.total_losses])
            next_row = write_row(worksheet, next_row, ['Total sales', form1325.total_sales])
            close_workbook(workbook)
    else:
        print(f'Warning: No sales in stock found. If sales were actually made - make sure the corrct .csv file was\n'
              f'provided (In this case {IB_ACTIVITY_STATEMENT_CSV} was provided as the input file). If the file is\n'
              f'correct and up to date - check for a software bug (in the CSV parser).')



def print_form1322_appendix_list(dividends):
    values_list = []
    header_list = Form1322AppendixEntry.to_header_list()
    tab = tt.Texttable()
    tab.header(header_list)
    print('\nForm 1322 appendix:')
    for div in dividends.dividend_list:
        # for row in zip(entry.to_list()):
        tab.add_row(div.to_list())
        s = tab.draw()
        values_list += [div.to_list()]
    print(s)
    total_usd = dividends.get_total_usd()
    total_ils = dividends.get_total_ils()
    total_ils_deducted = dividends.get_total_ils_deducted()
    print(f'total_usd: {total_usd}\ttotal_ils: {total_ils}\ttotal_ils_deducted: {total_ils_deducted}')

    if GENERATE_EXCEL_FILES:
        workbook, worksheet, next_row = gen_excel_file(FORM_1322_FILE_NAME, header_list, values_list, close_workbook=False)
        #rows = ('total_usd: {total_usd}\ttotal_ils: {total_ils}\ttotal_ils_deducted: {total_ils_deducted}')
        next_row = write_row(worksheet, next_row, ['Total', '', total_usd, '', total_ils, total_ils_deducted])
        close_workbook(workbook)

def print_interests_appendix(interests):
    values_list = []
    header_list = Interests.to_header_list()
    tab = tt.Texttable()
    tab.header(header_list)
    print('\nInterests appendix:')
    for interest in interests.interest_list:
        # for row in zip(entry.to_list()):
        tab.add_row(interest.to_list())
        s = tab.draw()
        values_list += [interest.to_list()]
    print(s)
    total_usd = interests.get_total_usd()
    total_ils = interests.get_total_ils()
    print(f'total_usd: {total_usd}\ttotal_ils: {total_ils}')

    if GENERATE_EXCEL_FILES:
        workbook, worksheet, next_row = gen_excel_file(INTERESTS_FILE_NAME, header_list, values_list, close_workbook=False)
        #rows = ('total_usd: {total_usd}\ttotal_ils: {total_ils}\ttotal_ils_deducted: {total_ils_deducted}')
        next_row = write_row(worksheet, next_row, ['Total', total_usd, total_ils])
        close_workbook(workbook)

def create_gen_dir():
    if GENERATE_EXCEL_FILES:
        if not os.path.exists(GENERATED_FILES_DIR):
            os.makedirs(GENERATED_FILES_DIR)


def create_form1325_from_date_range(original_form1325, start_date, end_date):
    f = Form1325()
    f.entry_list = [rec for rec in original_form1325.entry_list if rec.sale_date >= start_date and rec.sale_date < end_date]
    f.add_totals()
    return f


class Dividends:
    def __init__(self, dividends_list, dollar_ils_rate):
        self.dividend_list = []
        for div in dividends_list:
            entry = Form1322AppendixEntry(div)
            entry.populate(dollar_ils_rate)
            self.dividend_list.append(entry)

    def get_total_usd(self):
        return sum([div.value_usd for div in self.dividend_list])
    def get_total_ils(self):
        return sum([div.value_ils for div in self.dividend_list])
    def get_total_ils_deducted(self):
        return sum([div.tax_deducted_ils for div in self.dividend_list])

class Interests:
    def __init__(self, interest_list, usd_ils_rate_dict):
        for i in interest_list:
            i.populate(usd_ils_rate_dict)
        self.interest_list = interest_list

    def get_total_usd(self):
        return sum([i.value_usd for i in self.interest_list])
    def get_total_ils(self):
        return sum([i.value_ils for i in self.interest_list])

    @staticmethod
    def to_header_list():
        return ['date', 'value_usd', 'value_ils', 'usd_ils_rate']


def create_interests_excel():
    pass


def main():
    create_gen_dir()
    dollar_ils_rate = dollar_ils_rate_parse()
    trade_dic = trades_parse()
    dividends_list = dividends_parse()
    interest_list = interest_parse()
    interests = Interests(interest_list, dollar_ils_rate)

    #print(trade_dic)
    form1325 = form1325_obj_create(trade_dic, dollar_ils_rate)
    dividends = Dividends(dividends_list, dollar_ils_rate)
    print_interests_appendix(interests)
    print_form1325_list(form1325)
    print_form1322_appendix_list(dividends)
    print_broker_form1099_retrieval_instructions()

    if GENERATE_EXCEL_FILES:
        print(f"\nCheck the '{GENERATED_FILES_DIR}' directory for the generated Excel files")

    # not_deducted_1_1322_list = [rec for rec in form1322_appendix_list
    #                             if (rec.tax_deducted_ils == 0 and
    #                                 rec.date < datetime.datetime(TAX_YEAR, 7, 1))]
    # not_deducted_2_1322_list = [rec for rec in form1322_appendix_list
    #                             if (rec.tax_deducted_ils == 0 and
    #                                 rec.date >= datetime.datetime(TAX_YEAR, 7, 1))]
    # deducted_by_broker_1322_list = [rec for rec in form1322_appendix_list if rec.tax_deducted_ils != 0]

    if SPLIT_125_FORM:
        form1325_1st_half = create_form1325_from_date_range(form1325, datetime.datetime(TAX_YEAR, 1, 1),
                                                            datetime.datetime(TAX_YEAR, 7, 1))
        form1325_2nd_half = create_form1325_from_date_range(form1325, datetime.datetime(TAX_YEAR, 7, 1),
                                                            datetime.datetime(TAX_YEAR + 1, 1, 1))

        loss_remaining_from_prev = LOSS_FROM_PREV_YEARS
        loss_remaining_from_stock = form1325.total_losses * -1  # Make positive
        # loss_remaining = generate_form1322_pdf(deducted_by_broker_1322_list, FORM_1322_TEMPLATE_PDF, FORM_1322_DEDUCTED_OUTPUT_PDF,
        #                       tax_deduction='by_broker', loss_remaining=loss_remaining)
        loss_remaining_from_prev, loss_remaining_from_stock, _ = generate_form1322_pdf(form1325_1st_half, FORM_1322_TEMPLATE_PDF, FORM_1322_NOT_DEDUCTED_1_OUTPUT_PDF,
                              tax_deduction='not_deducted_1', credits_from_prev=loss_remaining_from_prev, credits_from_stock=loss_remaining_from_stock)
        loss_remaining_from_prev, loss_remaining_from_stock, dividends_and_interest_profits_including_deduction = generate_form1322_pdf(form1325_2nd_half, FORM_1322_TEMPLATE_PDF, FORM_1322_NOT_DEDUCTED_2_OUTPUT_PDF,
                              tax_deduction='not_deducted_2', credits_from_prev=loss_remaining_from_prev, credits_from_stock=loss_remaining_from_stock, dividends=dividends, interests=interests)
    else:
        loss_remaining_from_prev = LOSS_FROM_PREV_YEARS
        loss_remaining_from_stock = form1325.total_losses * -1  # Make positive
        loss_remaining_from_prev, loss_remaining_from_stock, dividends_and_interest_profits_including_deduction = generate_form1322_pdf(form1325,
                                                                                       FORM_1322_TEMPLATE_PDF,
                                                                                       FORM_1322_DEDUCTED_OUTPUT_PDF,
                                                                                       tax_deduction='not_deducted_2',
                                                                                       credits_from_prev=loss_remaining_from_prev,
                                                                                       credits_from_stock=loss_remaining_from_stock,
                                                                                       dividends=dividends, interests=interests)

    generate_form1324_pdf(FORM_1324_TEMPLATE_PDF, FORM_1324_OUTPUT_PDF, form1325, dividends, dividends_and_interest_profits_including_deduction)

    print(f'Total loss from previous year remaining for the next tax year: {loss_remaining_from_prev }')
    print(f'Total loss from stock remaining for the next tax year: {loss_remaining_from_stock}')

if __name__ == "__main__":


    main()