from src.tax_generator import form1325_list_create, print_form1325_list
from src.tax_generator import TradeOpen, TradeClose
from src.tax_generator import _tax_to_pay
from datetime import date, timedelta
from itertools import count

import texttable as tt
import pytest

ALLOWED_ERROR_MARGIN = 0.001

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
            # In loss - we do not care inflation - only nominal (or do we? nobody knows...)
            #assert entry.orig_price_ils - entry.sale_value == pytest.approx(-entry.profit_loss, ALLOWED_ERROR_MARGIN)
            pass


def check_expected_profit_loss(expected, actual):
    assert expected == pytest.approx(actual, ALLOWED_ERROR_MARGIN)

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

#
def test_loss_positive_rate_change():
    '''
    from example here: https://fintranslator.com/israel-tax-schedules-passive-income-foreign-broker/
    '''
    dollar_ils_rate = {}
    open_date = date(2020, 1, 1)
    close_date = date(2020, 1, 2)

    dollar_ils_rate[open_date] = 3.558
    dollar_ils_rate[close_date] = 3.568

    expected_profit_loss = -25.81
    trade_dic = {
        'TEST' : [
            TradeOpen(symbol='TEST', transaction_price=151.92, date=open_date, total_shares_num=1, shares_left=1),
            TradeClose(symbol='TEST', transaction_price=(144.26), date=close_date, total_shares_num=-1, shares_left=-1),
        ]
    }

    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)
    print_form1325_list(form1325_list)

    check_expected_profit_loss(expected_profit_loss, form1325_list[0].profit_loss)
    check_entries_math(form1325_list)
    #assert False

def test_profit_positive_rate_change():
    '''
    from example here: https://fintranslator.com/israel-tax-schedules-passive-income-foreign-broker/
    '''
    dollar_ils_rate = {}
    open_date = date(2020, 1, 1)
    close_date = date(2020, 1, 2)

    dollar_ils_rate[open_date] = 3.818
    dollar_ils_rate[close_date] = 3.512

    expected_profit_loss = 33.99

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
    check_expected_profit_loss(expected_profit_loss, form1325_list[0].profit_loss)
    check_entries_math(form1325_list)
    #assert False

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
         # In the actual data we are given -150 as the real loss
         # However, since this is a loss, we do not need the real,
         # but the nominal, so changed it to -350 which is the nominal
         # loss
         # 'profit_loss' : -350
        'profit_loss' : -150
     }),
    (5, 3, 100, 150, 1, -1,
     {
         'profit_loss' : 0
     })
]
ladar_testdata_test_case_names = [
    'nominal profit, inflation profit',
    'nominal profit, inflation loss',
    'nominal profit zeroed by inflation profit',
    'nominal loss, inflation profit',
    'nominal loss, inflation loss',
    'nominal loss zeroed by inflation loss'

]

@pytest.mark.parametrize("open_rate, close_rate, open_price_usd, close_price_usd, shares_num_open, shares_num_close, expected", ladar_testdata, ids=ladar_testdata_test_case_names)
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
    check_expected_profit_loss(expected['profit_loss'], form1325_list[0].profit_loss)
    check_entries_math(form1325_list)
    #assert False


class TradeTest:
    _ids = count(0)
    def __init__(self, trade, rate):
        self.trade = trade
        self.rate = rate
        self.trade.date = date(2020, 1, 1) + timedelta(days=next(self._ids))


test_params_generic = [
    {
        'test_name' : 'Simple: buy1,trade1,buy1,trade1',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=151.92, date=None, total_shares_num=1, shares_left=1), 3.558),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(144.26), date=None, total_shares_num=-1, shares_left=-1),3.568),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=151.92, date=None, total_shares_num=1, shares_left=1), 3.558),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(144.26), date=None, total_shares_num=-1, shares_left=-1), 3.568)
        ],
        'expected_profit_loss' : [-25.81, -25.81]
    },
    {
        'test_name' : 'Simple: buy1, trade1... complete laradar_example',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, date=None, total_shares_num=1, shares_left=1), 5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(150), date=None, total_shares_num=-1, shares_left=-1),7),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, date=None, total_shares_num=1, shares_left=1), 5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(200), date=None, total_shares_num=-1, shares_left=-1),3),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, date=None, total_shares_num=1, shares_left=1), 5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(50), date=None, total_shares_num=-1, shares_left=-1),11),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, date=None, total_shares_num=1, shares_left=1), 5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(50), date=None, total_shares_num=-1, shares_left=-1),7),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, date=None, total_shares_num=1, shares_left=1), 5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(50), date=None, total_shares_num=-1, shares_left=-1),3),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, date=None, total_shares_num=1, shares_left=1), 5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(150), date=None, total_shares_num=-1, shares_left=-1),3)
        ],
        'expected_profit_loss' : [350, 100, 0, -150, -150, 0]
    },
    {
        'test_name' : 'buy3, sell 1, sell 1',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=151.92, date=None, total_shares_num=3, shares_left=3), 3.558),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(144.26), date=None, total_shares_num=-1, shares_left=-1),3.568),
            TradeTest(TradeClose(symbol='TEST', transaction_price=(144.26), date=None, total_shares_num=-1, shares_left=-1), 3.568)
        ],
        'expected_profit_loss' : [-25.81, -25.81]
    },
    {
        # ADAM: my calculation, hopefully is correct
        'test_name' : 'Sell from 2 different opens at once',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=5, shares_left=5), 5),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=120, total_shares_num=10, shares_left=10), 7),
            TradeTest(TradeClose(symbol='TEST', transaction_price=130, total_shares_num=-15, shares_left=-15), 8)
        ],
        'expected_profit_loss' : [1200, 800]
    },
    {
        # ADAM: my calculation, hopefully is correct
        'test_name' : 'Sell from different opens at once - more complicated',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=5, shares_left=5), 5),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=120, total_shares_num=10, shares_left=10), 7),
            TradeTest(TradeClose(symbol='TEST', transaction_price=130, total_shares_num=-12, shares_left=-12), 8),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=10, shares_left=10), 8),
            TradeTest(TradeClose(symbol='TEST', transaction_price=70, total_shares_num=-12, shares_left=-12), 9)
        ],
        'expected_profit_loss' : [1200, 560, -630, -1530]
    },
    {
        # ADAM: my calculation, hopefully is correct
        'test_name' : '2 * (Sell from different opens at once - more complicated)',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=5, shares_left=5), 5),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=120, total_shares_num=10, shares_left=10), 7),
            TradeTest(TradeClose(symbol='TEST', transaction_price=130, total_shares_num=-12, shares_left=-12), 8),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=10, shares_left=10), 8),
            TradeTest(TradeClose(symbol='TEST', transaction_price=70, total_shares_num=-12, shares_left=-12), 9),
            TradeTest(TradeOpen(symbol='TEST1', transaction_price=100, total_shares_num=5, shares_left=5), 5),
            TradeTest(TradeOpen(symbol='TEST1', transaction_price=120, total_shares_num=10, shares_left=10), 7),
            TradeTest(TradeClose(symbol='TEST1', transaction_price=130, total_shares_num=-12, shares_left=-12), 8),
            TradeTest(TradeOpen(symbol='TEST1', transaction_price=100, total_shares_num=10, shares_left=10), 8),
            TradeTest(TradeClose(symbol='TEST1', transaction_price=70, total_shares_num=-12, shares_left=-12), 9)
        ],
        'expected_profit_loss' : [1200, 560, -630, -1530] * 2
    },
    {
        # ADAM: my calculation, hopefully is correct
        'test_name' : 'Commissions simple test',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=1, shares_left=1, commission=20), 10),
            TradeTest(TradeClose(symbol='TEST', transaction_price=200, total_shares_num=-1, shares_left=-1, commission=20), 10)
        ],
        'expected_profit_loss' : [600]
    },
    {
        # ADAM: my calculation, hopefully is correct
        'test_name' : 'Commissions test with close split',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=1, shares_left=1, commission=20), 10),
            TradeTest(TradeOpen(symbol='TEST', transaction_price=100, total_shares_num=1, shares_left=1, commission=20), 10),
            TradeTest(TradeClose(symbol='TEST', transaction_price=200, total_shares_num=-2, shares_left=-2, commission=20), 10)
        ],
        'expected_profit_loss' : [600, 800]
    },
    {
        'test_name' : 'Meir: example A',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=80, total_shares_num=1, shares_left=1, commission=0), 3.5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=100, total_shares_num=-1, shares_left=-1, commission=0), 4)
        ],
        'expected_profit_loss' : [80]
    },
    {
        'test_name' : 'Meir: example B',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=80, total_shares_num=1, shares_left=1, commission=0), 4),
            TradeTest(TradeClose(symbol='TEST', transaction_price=100, total_shares_num=-1, shares_left=-1, commission=0), 3.5)
        ],
        'expected_profit_loss' : [30]
    },
    {
        'test_name' : 'Meir: example C',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=80, total_shares_num=1, shares_left=1, commission=0), 4),
            TradeTest(TradeClose(symbol='TEST', transaction_price=100, total_shares_num=-1, shares_left=-1, commission=0), 3)
        ],
        'expected_profit_loss' : [0]
    },
    {
        'test_name' : 'Meir: example D',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=120, total_shares_num=1, shares_left=1, commission=0), 4),
            TradeTest(TradeClose(symbol='TEST', transaction_price=100, total_shares_num=-1, shares_left=-1, commission=0), 3.5)
        ],
        'expected_profit_loss' : [-70]
    },
    {
        'test_name' : 'Meir: example E',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=120, total_shares_num=1, shares_left=1, commission=0), 3.5),
            TradeTest(TradeClose(symbol='TEST', transaction_price=100, total_shares_num=-1, shares_left=-1, commission=0), 4)
        ],
        'expected_profit_loss' : [-20]
    },
    {
        'test_name' : 'Meir: example F',
        'test_trade_list' : [
            TradeTest(TradeOpen(symbol='TEST', transaction_price=120, total_shares_num=1, shares_left=1, commission=0), 3),
            TradeTest(TradeClose(symbol='TEST', transaction_price=100, total_shares_num=-1, shares_left=-1, commission=0), 4)
        ],
        'expected_profit_loss' : [0]
    },
]

test_params_generic_test_names = [params['test_name'] for params in test_params_generic ]

@pytest.mark.parametrize('test_trade_list_dic', test_params_generic, ids=test_params_generic_test_names)
def test_multiple_buy_sell(test_trade_list_dic):
    '''
    Buy a stock, sell all the shares, then buy the same stock again,
    and sell all the shares
    '''
    dollar_ils_rate = {}


    trade_dic = {}
    for test_trade in test_trade_list_dic['test_trade_list']:
        dollar_ils_rate[test_trade.trade.date] = test_trade.rate
        if test_trade.trade.symbol in trade_dic:
            trade_dic[test_trade.trade.symbol].append(test_trade.trade)
        else:
            trade_dic[test_trade.trade.symbol] = [test_trade.trade]
    print(trade_dic)

    form1325_list = form1325_list_create(trade_dic, dollar_ils_rate)
    print_form1325_list(form1325_list)

    assert len(form1325_list) == len(test_trade_list_dic['expected_profit_loss'])

    idx = 0
    for entry in form1325_list:
        check_expected_profit_loss(test_trade_list_dic['expected_profit_loss'][idx], entry.profit_loss)
        idx += 1

    check_entries_math(form1325_list)


bad_nominal_inflational_expected_triples = [
    (-20, -120, 0),
    (-20, 80, -20),
    (-180, -100, -80),
    (-180, -80, -100),
    (20, 120, 0),
    (80, -20, 80),
    (180, 100, 100),
    (180, 100, 80)
]
bla = [(-180, -100, -80)]

# nominal_inflational_expected_triples = [
# @pytest.mark.parametrize('nominal, inflational, expected_taxable', bla)
# def test_calculate_taxable_from_nominal_and_inflational(nominal, inflational, expected_taxable):
#     '''
#     From example in Excel file
#     '''
#     taxable = _tax_to_pay(nominal_profit_loss=nominal, inflational_profit_loss=inflational)
#     assert taxable == expected_taxable
