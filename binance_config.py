# keys of main_api
BINANCE_API_KEY_MAIN = '-'
BINANCE_SECRET_KEY_MAIN = '-'

# keyf of sub1_api1
BINANCE_API_KEY1 = '-'
BINANCE_SECRET_KEY1 = '-'

# keys of sub-account2
BINANCE_API_KEY2 = '-'
BINANCE_SECRET_KEY2 = '-'

# keys of sub-account3
BINANCE_API_KEY3 = '-'
BINANCE_SECRET_KEY3 = '-'



# token of performance report bot for slack
SLACK_PERFORMANCE_REPORT_BOT_TOKEN = '-'

# token of error code bot for slack
SLACK_ERROR_CODE_BOT_TOKEN = '-'

# token of optimization report bot for slack
SLACK_OPTIMIZATION_REPORT_BOT_TOKEN = '-'

# token of trade messages bot for slack
SLACK_TRADE_MESSAGE_BOT_TOKEN = '-'


META_DATA = [
    {
        'strategy':{
            'algorithm_name':'RSI MFI Long',
            'symbol':'UNI/USDT',
            'account':'Main Account',
            'api_label':'main_api',
            'start_date':'2023-11-11 23:24 (TSI)',
            'api_key':BINANCE_API_KEY_MAIN,
            'secret_key':BINANCE_SECRET_KEY_MAIN
        }
    },

    {
        'strategy':{
            'algorithm_name':'Hammer Fibonacci',
            'symbol':'BNB/USDT',
            'account':'sub2 (sub)',
            'api_label':'sub2api',
            'start_date':'2023-11-17 19:00 (TSI)',
            'api_key':BINANCE_API_KEY2,
            'secret_key':BINANCE_SECRET_KEY2
        }
    },

    {
        'strategy':{
            'algorithm_name':'Takuri Fibonacci',
            'symbol':'DOGE/USDT',
            'account':'sub3 (sub)',
            'api_label':'sub3api',
            'start_date':'2023-11-22 13:50 (TSI)',
            'api_key':BINANCE_API_KEY3,
            'secret_key':BINANCE_SECRET_KEY3
        }
    }

]