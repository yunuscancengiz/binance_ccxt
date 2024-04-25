import os
import sys

# set the path as main directory's path for imports
main_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
__path__ = [main_path]
sys.path += __path__

# imports
from binance_ccxt import BinanceCCXT
import time
from binance_config import BINANCE_API_KEY7, BINANCE_SECRET_KEY7
from datetime import datetime
import talib
import numpy as np
import pandas as pd
import traceback

class DojistarFibonacci:
    def __init__(self, open_prices:list, high_prices:list, low_prices:list, close_prices:list) -> None:
        self.dataset_length = 336
        self.open_prices = open_prices
        self.high_prices = high_prices
        self.low_prices = low_prices
        self.close_prices = close_prices

        self.R = None
        self.dojistar = None

    def calculate_dojistar(self):
        self.dojistar = talib.CDLDOJISTAR(np.array(self.open_prices), np.array(self.high_prices), np.array(self.low_prices), np.array(self.close_prices))
        return self.dojistar[-1]

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
    last_minute = None
    minutes = [x for x in range(1, 60) if x % 5 == 1]

    now = time.time()
    filename = 'XMR_dojistar_fib - ' + str(datetime.fromtimestamp(now)).replace(":", "_").split(".")[0] + '.txt'
    sub7 = BinanceCCXT(symbol='XMR/USDT', amount=0.1, timeframe='5m', filename=filename, BINANCE_API_KEY=BINANCE_API_KEY7, BINANCE_SECRET_KEY=BINANCE_SECRET_KEY7)

    df_ohlcv = sub7.dataset_creater(max_length=4080)

    sub7.start_order_monitoring()

    while True:
        try:
            minute = datetime.now().minute
            if minute in minutes and minute != last_minute:
                last_minute = minute

                # drop first row and append last candle to the dataframe to keep df's length 5200
                df_ohlcv = df_ohlcv.iloc[1:, :]
                last_candle = sub7.get_binance_OHLCV(limit=1)
                df_ohlcv = pd.concat([df_ohlcv, last_candle], axis=0, ignore_index=True)


                open_prices = list(df_ohlcv['open'])
                high_prices = list(df_ohlcv['high'])
                low_prices = list(df_ohlcv['low'])
                close_prices = list(df_ohlcv['close'])

                dojistar_fib = DojistarFibonacci(open_prices=open_prices, high_prices=high_prices, low_prices=low_prices, close_prices=close_prices)
                dojistar = dojistar_fib.calculate_dojistar()
                R = dojistar_fib.calculate_fibonacci_uptrend()

                print(datetime.now())
                print(f'\nDojistar:{dojistar}\nR: {R}\n')

                if dojistar == 100 and  R[0.500] - (R[0.500] * 1) / 100 > close_prices[-1]:
                    sub7.market_buy_order(SL=14)

                elif close_prices[-1] > R[0.500] - (R[0.500] * 1) / 100:
                    sub7.close_long_positions_with_market_order()

                print('\n---------------------------------------\n')


        except Exception as e:
            print(e)

        except KeyboardInterrupt:
            error_message = str(traceback.format_exc())
            sub7.exit(error_message=error_message)
            break