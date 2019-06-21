from xlrd import open_workbook
from xlrd import xldate
import csv
import io
import datetime
import texttable as tt

IB_ACTIVITY_STATEMENT_CSV = 'test.csv'
BANK_OF_ISRAEL_DOLLAR_ILS_EXCHANGE_XLS = 'ExchangeRates.xlsx'
BANK_OF_ISRAEL_DATE_COL = 0
BANK_OF_ISRAEL_RATE_COL = 1
IB_CODE_OPEN = 'O'
IB_CODE_CLOSE = 'C'

def dollar_ils_rate_parse():
    book = open_workbook(BANK_OF_ISRAEL_DOLLAR_ILS_EXCHANGE_XLS)
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

class Trade():
    def __init__(self):
        self.symbol = ''
        self.commision = 0
        self.transaction_price = 0
        self.date = None
        self.total_shares_num = 0
        self.shares_left = 0
    def __str__(self):
        return 'Trade: symbol:{}, date:{} comm:{}, price:{}'.format(self.symbol, self.date, self.commision, self.transaction_price)
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

            if open_close == IB_CODE_OPEN:
                trade = TradeOpen()
            elif open_close == IB_CODE_CLOSE:
                trade = TradeClose()
                trade.realized = float(row['Realized P/L'])
            else:
                continue

            trade.symbol = row['Symbol']
            trade.commision = float(row['Comm/Fee'])
            trade.transaction_price = float(row['T. Price'])
            # row['Date/Time'] looks like this 2019-04-22, 14:04:29
            # We discard the part after the comma so the time is 0, as with the USD/ILS exchange file
            trade.date = datetime.datetime.strptime(row['Date/Time'].split(',')[0], '%Y-%m-%d')
            # Will be negative for sell transactions
            trade.total_shares_num = int(row['Quantity'])
            trade.shares_left = trade.total_shares_num
            # If symbol not in dic - create empty list for it
            if trade.symbol not in dic:
                dic[trade.symbol] = []

            # Append the trade to the list of trades for this symbol
            dic[trade.symbol].append(trade)

    return dic

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
               '{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format(self.symbol, self.sale_value_usd, self.purchase_date, self.orig_price_ils, self.usd_sale_to_purchase_rate, self.adjusted_price, self.sale_date, self.sale_value, self.profit_loss)
    def __repr__(self):
        return self.__str__()
    def to_list(self):
        return [self.symbol, self.sale_value_usd, self.purchase_date, self.orig_price_ils, self.usd_sale_to_purchase_rate, self.adjusted_price, self.sale_date, self.sale_value, self.profit_loss]

    @staticmethod
    def to_header_list():
        return ['symbol', 'sale_value_usd', 'purchase_date', 'orig_price_ils', 'usd_sale_to_purchase_rate', 'adjusted_price', 'sale_date', 'sale_value', 'profit_loss']


def form1325_list_create(trade_dic, dollar_ils_rate):
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
        for closing_trade in reversed_trade_list:
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
        # If only one opening trade needed to cover closing trade - easy
        if len(list_of_tuples_for_symbol) == 1:
            tup = list_of_tuples_for_symbol[0]
            form_entry = Form1325Entry()
            # tup[0] is the TradeClose object
            # tup[1] is TradeOpen object
            # tup[2] is the number of shares TradeClose closed
            exchange_dates = [None, None]

            # If exchange date does not exist in dict, there must be vacation in Israel
            # So try a day earlier - until one exists
            for j in range(0,2):
                search_range = 5
                for i in range(0,search_range):
                    if tup[j].date - datetime.timedelta(i) in dollar_ils_rate:
                        exchange_dates[j] = tup[j].date - datetime.timedelta(i)
                        break
                if exchange_dates[j] is None:
                    raise Exception('USD/ILS exchange rate not found near closing date. Trade: {}'.format(tup[j]))

            sell_date = exchange_dates[0]
            buy_date = exchange_dates[1]
            form_entry.symbol = tup[0].symbol
            form_entry.sale_value_usd = tup[0].transaction_price * tup[2]
            print(tup[0].transaction_price)
            form_entry.purchase_date = tup[1].date
            form_entry.orig_price_ils = tup[1].transaction_price * tup[2] * dollar_ils_rate[buy_date]
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

            # Different signs
            if inflation * realized < 0:
                form_entry.profit_loss = realized
            else: # Same sign
                form_entry.profit_loss = realized - inflation

                # If inflation causes a sign change - leave the profit at 0
                if realized * form_entry.profit_loss < 0:
                    form_entry.profit_loss = 0

            # If loss - disregard inflation
            if form_entry.profit_loss < 0:
                form_entry.profit_loss = realized

            # form_entry.profit_loss = form_entry.sale_value - form_entry.adjusted_price =>
            form_entry.adjusted_price = form_entry.sale_value - form_entry.profit_loss
            form_entry.usd_sale_to_purchase_rate = form_entry.adjusted_price / form_entry.orig_price_ils




            #form_entry.adjusted_price = form_entry.usd_sale_to_purchase_rate * form_entry.orig_price_ils
            #form_entry.sale_date = sell_date
            #print(f'{tup[0].transaction_price} * {tup[2]}) * {dollar_ils_rate[buy_date]}')

            #form_entry.profit_loss = form_entry.sale_value - form_entry.adjusted_price
            entries.append(form_entry)
        else:
            raise Exception('Closing trade for {} covers more than one opening trade. This is not yet supported.'.format(list_of_tuples_for_symbol[0][0].symbol))
    return entries

def sum_profit_loss(form1325_list):
    return sum([entry.profit_loss for entry in form1325_list])

def print_form1325_list(form1325_list):
    tab = tt.Texttable()
    tab.header(Form1325Entry.to_header_list())

    for entry in form1325_list:
        #for row in zip(entry.to_list()):
        tab.add_row(entry.to_list())
        s = tab.draw()
    print(s)


def main():
    dollar_ils_rate = dollar_ils_rate_parse()
    trade_dic = trades_parse()
    print(trade_dic)
    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)
    print_form1325_list(form1325_list)

if __name__ == "__main__":


    main()