from src.tax_generator import form1325_list_create, print_form1325_list
from src.tax_generator import TradeOpen, TradeClose
from datetime import date
import texttable as tt
import pytest

ALLOWED_ERROR_MARGIN = 0.01

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
            TradeClose(symbol='TEST', transaction_price=(144.26), date=close_date, total_shares_num=-1, shares_left=-1),
        ]
    }

    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)

    print_form1325_list(form1325_list)
    assert False

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
            TradeClose(symbol='TEST', transaction_price=392.86, date=close_date, total_shares_num=-1, shares_left=-1),
        ]
    }

    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)

    print_form1325_list(form1325_list)
    assert False

ladar_testdata = [
    (5, 7, 100, 150, 1, -1,
     {
         'profit_loss' : 350
     }),
    (5, 3, 100, 200, 1, -1,
     {
         'profit_loss' : 100
     }),
    (5, 11, 100, 50, 1, -1,
     {
         'profit_loss' : 0
     }),
    (5, 7, 100, 50, 1, -1,
     {
         'profit_loss' : -150
     }),
    (5, 3, 100, 50, 1, -1,
     {
         'profit_loss' : -150
     }),
    (5, 3, 100, 150, 1, -1,
     {
         'profit_loss' : 0
     })
]

def check_entries_math(form1325_list):
    '''
    Sanity check that the fields of the table add up as instructed in the form
    :param form1325_list:
    :return void
    '''
    for entry in form1325_list:
        assert entry.orig_price_ils * entry.usd_sale_to_purchase_rate == pytest.approx(entry.adjusted_price, ALLOWED_ERROR_MARGIN)
        if entry.profit_loss >= 0:
            assert entry.sale_value - entry.adjusted_price == pytest.approx(entry.profit_loss, ALLOWED_ERROR_MARGIN)
        else:
            # Not sure why this is the case why is the calculation different??
            assert entry.orig_price_ils - entry.sale_value == pytest.approx(-entry.profit_loss, ALLOWED_ERROR_MARGIN)


@pytest.mark.parametrize("open_rate, close_rate, open_price_usd, close_price_usd, shares_num_open, shares_num_close, expected", ladar_testdata)
def test_laradar_example(open_rate, close_rate, open_price_usd, close_price_usd, shares_num_open, shares_num_close, expected):
    '''
    Check the algorithm agains the example from here: http://laradar.com/?p=304#
    '''
    dollar_ils_rate = {}
    open_date = date(2020, 1, 1)
    close_date = date(2020, 1, 2)

    dollar_ils_rate[open_date] = open_rate
    dollar_ils_rate[close_date] = close_rate

    # print(dollar_ils_rate)
    print('bla!')

    trade_dic = {
        'TEST' : [
            TradeOpen(symbol='TEST', transaction_price=open_price_usd, date=open_date, total_shares_num=shares_num_open, shares_left=shares_num_open),
            TradeClose(symbol='TEST', transaction_price=close_price_usd, date=close_date, total_shares_num=shares_num_close, shares_left=shares_num_close),
        ]
    }

    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)
    print_form1325_list(form1325_list)
    assert expected['profit_loss'] == pytest.approx(form1325_list[0].profit_loss, ALLOWED_ERROR_MARGIN)
    check_entries_math(form1325_list)
    #assert False
