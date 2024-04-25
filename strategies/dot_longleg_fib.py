import os
import sys

# set the path as main directory's path for imports
main_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
__path__ = [main_path]
sys.path += __path__

# imports
from binance_ccxt import BinanceCCXT
import time
from binance_config import BINANCE_API_KEY9, BINANCE_SECRET_KEY9 
from datetime import datetime
import talib
import numpy as np
import pandas as pd
import traceback

class LonglegFibonacci:
    def __init__(self, open_prices:list, high_prices:list, low_prices:list, close_prices:list) -> None:
        self.open_prices = open_prices
        self.high_prices = high_prices
        self.low_prices = low_prices
        self.close_prices = close_prices
        
        self.R = None
        self.longline = None

    def calculate_longleg(self):
        self.longleg = talib.CDLLONGLEGGEDDOJI(np.array(self.open_prices), np.array(self.high_prices), np.array(self.low_prices), np.array(self.close_prices))
        return self.longleg[-1]
    
    def calculate_fibonacci_downtrend(self):
        max_price = max(self.high_prices)
        min_price = min(self.low_prices)
        swing_high = max_price - min_price
        
        self.R = {
            0: min_price + (swing_high * 0),
            0.236: min_price + (swing_high * 0.236),
            0.382: min_price + (swing_high * 0.382),
            0.500: min_price + (swing_high * 0.500),
            0.618: min_price + (swing_high * 0.618),
            0.764: min_price + (swing_high * 0.764),
            1: min_price + (swing_high * 1)
        }
        return self.R
    

if __name__ == '__main__':
    last_minute = None
    minutes = [x for x in range(0, 60) if x % 15 == 1]

    now = time.time()
    filename = 'DOT_longleg_fib - ' + str(datetime.fromtimestamp(now)).replace(":", "_").split(".")[0] + '.txt'
    sub9 = BinanceCCXT(symbol='DOT/USDT', amount=2, timeframe='15m', filename=filename, BINANCE_API_KEY=BINANCE_API_KEY9, BINANCE_SECRET_KEY=BINANCE_SECRET_KEY9)

    df_ohlcv = sub9.dataset_creater(max_length=1700)

    sub9.start_order_monitoring()

    while True:
        try:
            minute = datetime.now().minute
            if minute in minutes and minute != last_minute:
                last_minute = minute

                # drop first row and append last candle to the dataframe to keep df's length 680
                df_ohlcv = df_ohlcv.iloc[1:, :]
                last_candle = sub9.get_binance_OHLCV(limit=1)
                df_ohlcv = pd.concat([df_ohlcv, last_candle], axis=0, ignore_index=True)


                open_prices = list(df_ohlcv['open'])
                high_prices = list(df_ohlcv['high'])
                low_prices = list(df_ohlcv['low'])
                close_prices = list(df_ohlcv['close'])

                longleg_fib = LonglegFibonacci(open_prices=open_prices, high_prices=high_prices, low_prices=low_prices, close_prices=close_prices)

                longleg = longleg_fib.calculate_longleg()
                R = longleg_fib.calculate_fibonacci_downtrend()

                print(datetime.now())
                print(f'\nLongline: {longleg}\nR: {R}\n')

                if longleg == 100 and R[0.618] > close_prices[-1] > R[0.618] - (R[0.618] * 1) / 100:
                    sub9.market_sell_order(SL=32, TP=20)

                elif R[0.500] < close_prices[-1] < R[0.500] + (R[0.500] * 1) / 100:
                    sub9.close_short_positions_with_market_order()

                print('\n---------------------------------------------------------------\n')

        except Exception as e:
            print(e)

        except KeyboardInterrupt:
            error_message = str(traceback.format_exc())
            sub9.exit(error_message=error_message)
            break