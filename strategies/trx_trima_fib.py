import os
import sys

# set the path as main directory's path for imports
main_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
__path__ = [main_path]
sys.path += __path__

# imports
from binance_ccxt import BinanceCCXT
import time
from binance_config import BINANCE_API_KEY6, BINANCE_SECRET_KEY6
from datetime import datetime
import talib
import numpy as np
import pandas as pd
import traceback

class TrimaFibonacci:
    def __init__(self, open_prices:list, high_prices:list, low_prices:list, close_prices:list) -> None:
        self.dataset_length = 336
        self.open_prices = open_prices
        self.high_prices = high_prices
        self.low_prices = low_prices
        self.close_prices = close_prices

        self.R = None
        self.trima = None

    def calculate_trima(self):
        self.trima = talib.TRIMA(np.array(self.close_prices), timeperiod=60)
        return self.trima[-1]
    
    def calculate_fibonacci_uptrend(self):
        max_price = max(self.high_prices)
        min_price = min(self.low_prices)
        swing_high = max_price - min_price
        
        self.R = {
            0: max_price - (swing_high * 0),
            0.236: max_price - (swing_high * 0.236),
            0.382: max_price - (swing_high * 0.382),
            0.500: max_price - (swing_high * 0.500),
            0.618: max_price - (swing_high * 0.618),
            0.764: max_price - (swing_high * 0.764),
            1: max_price - (swing_high * 1)
        }
        return self.R
    
if __name__ == '__main__':
    minutes = [1]
    
    now = time.time()
    filename = 'TRX_trima_fib - ' + str(datetime.fromtimestamp(now)).replace(":", "_").split(".")[0] + '.txt'
    sub7 = BinanceCCXT(symbol='TRX/USDT', amount=100, timeframe='1h', filename=filename, BINANCE_API_KEY=BINANCE_API_KEY6, BINANCE_SECRET_KEY=BINANCE_SECRET_KEY6)

    sub7.start_order_monitoring()

    while True:
        try:
            minute = datetime.now().minute
            if minute in minutes:
                df_ohlcv = sub7.get_binance_OHLCV(limit=336)
                open_prices = list(df_ohlcv['open'])
                high_prices = list(df_ohlcv['high'])
                low_prices = list(df_ohlcv['low'])
                close_prices = list(df_ohlcv['close'])

                trima_fib = TrimaFibonacci(open_prices=open_prices, high_prices=high_prices, low_prices=low_prices, close_prices=close_prices)
                trima = trima_fib.calculate_trima()
                R = trima_fib.calculate_fibonacci_uptrend()

                print(datetime.now())
                print(f'\nTrima:{trima}\nR: {R}\n')

                if R[0.764] < close_prices[-1] < R[0.764] + (R[0.764] * 1) / 100:
                    if trima < close_prices[-1]:
                        sub7.market_buy_order(SL=30, TP=8)

                elif R[0.618] > close_prices[-1] > R[0.618] - (R[0.618] * 1) / 100 :
                    sub7.close_long_positions_with_market_order()

                time.sleep(65)

                print('\n--------------------------------------------------\n')



        except Exception as e:
            print(e)

        except KeyboardInterrupt:
            error_message = str(traceback.format_exc())
            sub7.exit(error_message=error_message)
            break