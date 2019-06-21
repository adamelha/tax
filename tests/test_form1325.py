from src.tax_generator import form1325_list_create, print_form1325_list
from src.tax_generator import TradeOpen, TradeClose
from datetime import date
import texttable as tt
tab = tt.Texttable()

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

def test_loss_positive_rate_change():
    dollar_ils_rate = {}
    open_date = date(2020, 1, 1)
    close_date = date(2020, 1, 2)

    dollar_ils_rate[open_date] = 3.558
    dollar_ils_rate[close_date] = 3.568

    # print(dollar_ils_rate)
    print('bla!')

    trade_dic = {
        'TEST' : [
            TradeOpen(symbol='TEST', transaction_price=151.92, date=open_date, total_shares_num=1, shares_left=1),
            TradeClose(symbol='TEST', transaction_price=(144.26), date=close_date, total_shares_num=-1, shares_left=-1, realized=-1),
        ]
    }

    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)

    print_form1325_list(form1325_list)
    assert True

def test_profit_positive_rate_change():
    dollar_ils_rate = {}
    open_date = date(2020, 1, 1)
    close_date = date(2020, 1, 2)

    dollar_ils_rate[open_date] = 3.818
    dollar_ils_rate[close_date] = 3.512

    # print(dollar_ils_rate)
    print('bla!')

    trade_dic = {
        'TEST' : [
            TradeOpen(symbol='TEST', transaction_price=352.47, date=open_date, total_shares_num=1, shares_left=1),
            TradeClose(symbol='TEST', transaction_price=392.86, date=close_date, total_shares_num=-1, shares_left=-1, realized=1),
        ]
    }

    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)

    print_form1325_list(form1325_list)
    assert True
