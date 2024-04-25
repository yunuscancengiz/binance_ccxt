import ccxt
import pandas as pd
import os
from pprint import pprint
import time
from datetime import datetime as dt
from _logger import Logger
from binance_config import BINANCE_API_KEY2, BINANCE_SECRET_KEY2
import slack_bot
import traceback
import threading

class BinanceCCXT:
    def __init__(self, symbol:str, amount:float, timeframe:str, filename:str, BINANCE_API_KEY:str, BINANCE_SECRET_KEY:str) -> None:
        self.logger = Logger(filename=filename)
        self.BINANCE_API_KEY = BINANCE_API_KEY
        self.BINANCE_SECRET_KEY = BINANCE_SECRET_KEY
        while True:
            try:
                self.binance = ccxt.binance({'enableRateLimit':True, 'apiKey':self.BINANCE_API_KEY, 'secret':self.BINANCE_SECRET_KEY, 'options':{'defaultType':'future'}})
                break
            except Exception as e:
                print(e)
                self.logger.logging(date=time.time(), action='ERROR(24)', order_type=None, price=None, amount=None)
                time.sleep(1)

        self.symbol = symbol
        self.amount = amount
        self.timeframe = timeframe
        self.filename = filename

        self.limit_fee = 0.0002
        self.market_fee = 0.0005

        self.bid_price = None
        self.ask_price = None

        # open orders txt path
        self.open_orders_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "binance_ccxt", "logs", "open_orders")

        self.conditional_orders_lock = threading.Lock()
        self.conditional_orders = []    # {'sl_order_id'':'sl id', 'tp_order_id':'tp id', 'status':'open or in_line'}
        self.initialize_open_orders_dict()  # if there are any orders left open before the program is run, they will be added to the conditional orders list

        # leverage
        self.leverage = 1
        try:
            self.binance.set_leverage(leverage=self.leverage, symbol=self.symbol)
        except Exception as e:
            print(e)
            self.logger.logging(date=time.time(), action='ERROR(49)', order_type=None, price=None, amount=None)


    def check_balance(self, price, order_type, amount):
        '''
        Summary: checks the available balance in the wallet through the exchange. 
        :return bool value according to balance's availability
        '''
        is_balance_available = None
        while True:
            try:
                balance = self.binance.fetch_balance()['USDT']['free']
                break
            except Exception as e:
                print(e)
                self.logger.logging(date=time.time(), action='ERROR(66)', order_type=None, price=None, amount=None)
                time.sleep(1)

        if order_type == 'limit':
            if float(balance) > (price * amount + (self.limit_fee * price * amount)):
                is_balance_available = True
            elif float(balance) < (price * amount + (self.limit_fee * price * amount)):
                is_balance_available = False
                print('Insufficient balance!')
        elif order_type == 'market':
            if float(balance) > (price * amount + (price * self.market_fee * amount)):
                is_balance_available = True
            elif float(balance) < (price * amount + (price * self.market_fee * amount)):
                is_balance_available = False
                print('Insufficient balance!')
        return is_balance_available
    

    def liquidation_price_for_long(self, price, leverage=None):
        '''
        Summary: Calculates liquidation price for long position according to position size, price, leverage etc.
        Formula: 
            Liquidation Price (Long) = (Entry Price - (Entry Price / Leverage)) + 150
        :return liquidation price
        '''
        if leverage == None:
            leverage = self.leverage
        liq_price = (price - (price / leverage)) + (price / 200)
        return liq_price


    def liquidation_price_for_short(self, price, leverage=None):
        '''
        Summary: Calculates estimated liquidation price for short position according to position size, price, leverage etc.
        Formula: 
            Liquidation Price (Short) = (Entry Price + (Entry Price / Leverage)) - 150
        :return liquidation price
        '''
        if leverage == None:
            leverage = self.leverage
        liq_price = (price + (price / leverage)) - (price / 200)
        return liq_price
    

    def get_binance_OHLCV(self, limit:int=None, since:int=None, timeframe:str=None):
        ''' 
        Summary: gets the last open, high, low, close and volume data from binance and convert the data to dataframe
        :limit (int): limit for number of tick
        :since (int): unix timestamp of the start date
        :return OHLCV data (DataFrame)
        '''
        if timeframe == None:
            timeframe = self.timeframe

        while True:
            try:
                ohlcv = self.binance.fetch_ohlcv(symbol=self.symbol, timeframe=timeframe, limit=limit, since=since)
                binance_df_ohlcv = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                break
            except Exception as e:
                print(e)
                self.logger.logging(date=time.time(), action='ERROR(117)', order_type=None, price=None, amount=None)
                time.sleep(1)
        return binance_df_ohlcv
    

    def get_close_price(self):
        '''
        Summary: gets close price from ticker
        :return close price
        '''
        while True:
            try:
                ticker = self.binance.fetch_ticker(symbol=self.symbol)
                break
            except Exception as e:
                print(e)
                self.logger.logging(date=time.time(), action='ERROR(145)', order_type=None, price=None, amount=None)
                time.sleep(1)

        close = float(ticker['info']['lastPrice'])
        high = float(ticker['info']['highPrice'])
        low = float(ticker['info']['lowPrice'])
        return close, high, low
    

    def calculate_SL_long(self, SL, price=None) -> str:
        ''' 
        Summary: calculates the stop loss price for long positions according to the stop loss percentage given by the SL parameter
        :param SL (float): percentage of stop loss
        :return stop loss price for long
        '''
        if price == None:
            price = self.fetch_entry_price()
        long_sl_price = price - (price * (SL / 100))
        """if round(price, 4) == round(long_sl_price, 4):
            while round(price, 4) <= round(long_sl_price, 4):
                long_sl_price -= 0.00001"""
        return str(long_sl_price)


    def calculate_SL_short(self, SL, price=None) -> str:
        '''
        Summary: calculates the stop loss price for short positions according to the stop loss percentage given by the SL parameter
        :param SL (float): percentage of stop loss
        :return stop loss price for short
        '''
        if price == None:
            price = self.fetch_entry_price()
        short_sl_price = price + (price * (SL / 100))
        """if round(price, 4) == round(short_sl_price, 4):
            while round(price, 4) >= round(short_sl_price, 4):
                short_sl_price += 0.00001"""
        return str(short_sl_price)
    

    def calculate_TP_long(self, TP, price) -> str:
        '''
        Summary: calculates the take profit price for long positions according to the take profit percentage given by the TP parameter
        :param TP (float): percentage of take profit
        :return take profit price for long
        '''
        if price == None:
            price = self.fetch_entry_price()
        long_tp_price = price + (price * (TP / 100))
        """if round(price, 4) == round(long_tp_price, 4):
            while round(price, 4) >= round(long_tp_price, 4):
                long_tp_price += 0.00001"""
        return str(long_tp_price)
    

    def calculate_TP_short(self, TP, price):
        '''
        Summary: calculates the take profit price for short positions according to the take profit percentage given by the TP parameter
        :param TP (float): percentage of take profit
        :return take profit price for short
        '''
        if price == None:
            price = self.fetch_entry_price()
        short_tp_price = price - (price * (TP / 100))
        """if round(price, 4) == round(short_tp_price, 4):
            while round(price, 4) <= round(short_tp_price, 4):
                short_tp_price -= 0.00001"""
        return str(short_tp_price)
    

    def fetch_entry_price(self):
        '''
        :returns last order's average entry price
        '''
        while True:
            try:
                entry_price = float(self.binance.fetch_orders(symbol=self.symbol)[-1]['average'])
                break
            except Exception as e:
                print(e)
                self.logger.logging(date=time.time(), action='ERROR(226)', order_type=None, price=None, amount=None)
                time.sleep(1)
        return entry_price
    

    def cancel_all_orders(self) -> None:
        '''
        Summary: cancels all open orders
        '''
        try:
            self.binance.cancel_all_orders(symbol=self.symbol)
            self.logger.logging(date=time.time(), action='CANCEL ORDER', order_type=None, price=None, amount=None)
        except Exception as e:
            print(e)
            print('Error received when canceling orders!')
            self.logger.logging(date=time.time(), action='ERROR(227)', order_type=None, price=None, amount=None)

    
    def check_market_price(self):
        '''
        Summary: checks the symbol's market price continiously. If market price crosses the stop order price then sends an order to close one of the positions. Finally removes the order from self.conditional_orders list.
        '''
        last_candle = self.get_binance_OHLCV(limit=1, timeframe='1m')
        last_candle = last_candle.to_dict(orient='records')
        high_price = float(last_candle[0]['high'])
        low_price = float(last_candle[0]['low'])

        print(f'high: {high_price}\t-\tlow: {low_price}')

        row_indexes = []
        cond_orders_df = pd.DataFrame(self.conditional_orders)
        for index, row in cond_orders_df.iterrows():
            if row['side'] == 'sell':
                # stop order for long position
                if row['tp_price'] is not None:
                    if float(high_price) >= float(row['tp_price']):
                        # high price crossed the tp price
                        print('take profit for long position triggered')
                        self.binance.create_market_sell_order(symbol=self.symbol, amount=self.amount)
                        self.logger.logging(date=time.time(), action='TP FOR LONG', order_type='market', price=row['tp_price'], amount=self.amount)
                        row_indexes.append(index)
                        try:
                            self.send_trade_info_to_slackbot(action='TP FOR LONG', entry_price=row['tp_price'], position_size=self.amount)
                        except Exception as e:
                            print(e)
                            self.logger.logging(date=time.time(), action='ERROR - EXIT(267)', order_type=None, price=None, amount=None)
                        break
                
                if row['sl_price'] is not None:
                    if float(low_price) <= float(row['sl_price']):
                        # low price crossed the sl price
                        print('stop loss for long position triggered')
                        self.binance.create_market_sell_order(symbol=self.symbol, amount=self.amount)
                        self.logger.logging(date=time.time(), action='SL FOR LONG', order_type='market', price=row['sl_price'], amount=self.amount)
                        row_indexes.append(index)
                        try:
                            self.send_trade_info_to_slackbot(action='SL FOR LONG', entry_price=row['sl_price'], position_size=self.amount)
                        except Exception as e:
                            print(e)
                            self.logger.logging(date=time.time(), action='ERROR - EXIT(277)', order_type=None, price=None, amount=None)
                        break

            elif row['side'] == 'buy':
                # stop order for short position
                if row['tp_price'] is not None:
                    if float(low_price) <= float(row['tp_price']):
                        # low price crossed the tp price
                        print('take profit for short position triggered')
                        self.binance.create_market_buy_order(symbol=self.symbol, amount=self.amount)
                        self.logger.logging(date=time.time(), action='TP FOR SHORT', order_type='market', price=row['tp_price'], amount=self.amount)
                        row_indexes.append(index)
                        try:
                            self.send_trade_info_to_slackbot(action='TP FOR SHORT', entry_price=row['tp_price'], position_size=self.amount)
                        except Exception as e:
                            print(e)
                            self.logger.logging(date=time.time(), action='ERROR - EXIT(289)', order_type=None, price=None, amount=None)
                        break

                if row['sl_price'] is not None:
                    if float(high_price) >= float(row['sl_price']):
                        # high price crossed the sl price
                        print('stop loss for short position triggered')
                        self.binance.create_market_buy_order(symbol=self.symbol, amount=self.amount)
                        self.logger.logging(date=time.time(), action='SL FOR SHORT', order_type='market', price=row['sl_price'], amount=self.amount)
                        row_indexes.append(index)
                        try:
                            self.send_trade_info_to_slackbot(action='SL FOR SHORT', entry_price=row['sl_price'], position_size=self.amount)
                        except Exception as e:
                            print(e)
                            self.logger.logging(date=time.time(), action='ERROR - EXIT(299)', order_type=None, price=None, amount=None)
                        break

        for i in row_indexes:
            cond_orders_df.loc[i, :] = None
        cond_orders_df.dropna(how='all', axis=0, inplace=True)
        self.conditional_orders = cond_orders_df.to_dict(orient='records')
        print(f'Conditional orders list:\n{self.conditional_orders}\n')


    def market_buy_order(self, action:str='OPEN LONG', SL=None, TP=None, pos_amount=None):
        '''
        Summary: 
        :param action (str):
        :param SL (float):
        :param pos_amount (float):
        '''
        if pos_amount == None:
            # use self.amount as amount when opening a position
            amount = self.amount
        else:
            # use pos_amount as amount when closing the open positions. pos_amount is the position size of the open positions
            amount = pos_amount

        close, high, low = self.get_close_price()
        is_balance_available = self.check_balance(price=close, order_type='market', amount=amount)
        if action == 'CLOSE SHORT':
            is_balance_available = True

        if is_balance_available:
            try:
                self.binance.create_market_buy_order(symbol=self.symbol, amount=amount)
                time.sleep(2)
                entry_price = self.fetch_entry_price()
                self.logger.logging(date=time.time(), action=action, order_type='market', price=entry_price, amount=amount)
                print('Market buy order sent successfully!')
                time.sleep(1)
            except Exception as e:
                error_message = f'{str(e)}\n{str(traceback.format_exc())}'
                print(error_message)
                self.logger.logging(date=time.time(), action='ERROR - EXIT(327)', order_type=None, price=None, amount=None)
                self.exit(error_message=error_message)

            if SL is not None:
                long_sl_price = self.calculate_SL_long(SL=SL, price=entry_price)
                sl_price = long_sl_price
            else:
                sl_price = None

            if TP is not None:
                long_tp_price = self.calculate_TP_long(TP=TP, price=entry_price)
                tp_price = long_tp_price
            else:
                tp_price = None

            if SL is not None or TP is not None:
                order_dict = {
                    'sl_price':sl_price,
                    'tp_price':tp_price,
                    'side':'sell'
                }
                self.add_conditional_order(order_dict=order_dict)

            try:
                total_position_size = self.binance.fetch_positions(symbols=[self.symbol])[0]['contracts']
                self.send_trade_info_to_slackbot(action=action, entry_price=entry_price, sl_price=sl_price, tp_price=tp_price, position_size=amount, total_position_size=total_position_size)
            except Exception as e:
                print(e)
                self.logger.logging(date=time.time(), action='ERROR - EXIT(379)', order_type=None, price=None, amount=None)


    def market_sell_order(self, action:str='OPEN SHORT', SL=None, TP=None, pos_amount=None):
        if pos_amount == None:
            # use self.amount as amount when opening a position
            amount = self.amount
        else:
            # use pos_amount as amount when closing the open positions. pos_amount is the position size of the open positions
            amount = pos_amount

        close, high, low = self.get_close_price()
        is_balance_available = self.check_balance(price=close, order_type='market', amount=amount)
        if action == 'CLOSE LONG':
            is_balance_available = True

        if is_balance_available:
            try:
                self.binance.create_market_sell_order(symbol=self.symbol, amount=amount)
                time.sleep(2)
                entry_price = self.fetch_entry_price()
                self.logger.logging(date=time.time(), action=action, order_type='market', price=entry_price, amount=amount)
                print('Market sell order sent successfully!')
                time.sleep(1)
            except Exception as e:
                error_message = f'{str(e)}\n{str(traceback.format_exc())}'
                print(error_message)
                self.logger.logging(date=time.time(), action='ERROR - EXIT(407)', order_type=None, price=None, amount=None)
                self.exit(error_message=error_message)

            if SL is not None:
                short_sl_price = self.calculate_SL_short(SL=SL, price=entry_price)
                sl_price = short_sl_price
            else:
                sl_price = None

            if TP is not None:
                short_tp_price = self.calculate_TP_short(TP=TP, price=entry_price)
                tp_price = short_tp_price
            else:
                tp_price = None

            if SL is not None or TP is not None:
                order_dict = {
                    'sl_price':sl_price,
                    'tp_price':tp_price,
                    'side':'buy'
                }
                self.add_conditional_order(order_dict=order_dict)

            try:
                total_position_size = self.binance.fetch_positions(symbols=[self.symbol])[0]['contracts']
                self.send_trade_info_to_slackbot(action=action, entry_price=entry_price, sl_price=sl_price, tp_price=tp_price, position_size=amount, total_position_size=total_position_size)
            except Exception as e:
                print(e)
                self.logger.logging(date=time.time(), action='ERROR - EXIT(434)', order_type=None, price=None, amount=None)

    def close_long_positions_with_market_order(self):
        '''
        Summary: calculates the position size of the open long positions according to the leverage and size info of the open long positions then closes them all
        '''
        open_pos_side = self.binance.fetch_positions(symbols=[self.symbol])[0]['side']
        if open_pos_side == 'long':
            open_pos_leverage = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['leverage'])
            open_pos_size = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['positionAmt'])
            open_pos_amount = abs(open_pos_leverage * open_pos_size)
            self.market_sell_order(action='CLOSE LONG', pos_amount=open_pos_amount)
            print('All long positions are closed!')

            # stop loss & take profit orders removed from conditional_orders list
            with self.conditional_orders_lock:
                self.conditional_orders = []


    def close_short_positions_with_market_order(self):
        '''
        Summary: calculates the position size of the open short positions according to the leverage and size info of the open short positions then closes them all
        '''
        open_pos_side = self.binance.fetch_positions(symbols=[self.symbol])[0]['side']
        if open_pos_side == 'short':
            open_pos_leverage = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['leverage'])
            open_pos_size = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['positionAmt'])
            open_pos_amount = abs(open_pos_leverage * open_pos_size)
            self.market_buy_order(action='CLOSE SHORT', pos_amount=open_pos_amount)
            print('All short positions are closed!')

            # stop loss & take profit orders removed from conditional_orders list
            with self.conditional_orders_lock:
                self.conditional_orders = []


    def close_all_open_positions_with_market_order(self):
        '''
        Summary: calculates the position size of the open positions according to the leverage, size and side info of open positions then closes them all
        '''
        open_pos_side = self.binance.fetch_positions(symbols=[self.symbol])[0]['side']
        open_pos_leverage = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['leverage'])
        open_pos_size = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['positionAmt'])
        open_pos_amount = abs(open_pos_leverage * open_pos_size)
        try:
            self.binance.set_leverage(leverage=1, symbol=self.symbol)
        except:
            pass
        try:
            if open_pos_side == 'long':
                self.market_sell_order(action='CLOSE LONG', pos_amount=open_pos_amount)
            elif open_pos_side == 'short':
                self.market_buy_order(action='CLOSE SHORT', pos_amount=open_pos_amount)
            print('All open positions closed!')

            # cancel stop loss & take profit orders for closed positions
            open_orders = self.binance.fetch_open_orders(symbol=self.symbol)
            for order in open_orders:
                if order['stopPrice'] is not None:
                    self.binance.cancel_order(id=order['id'], symbol=self.symbol)
            print('All stop loss & take profit orders canceled!')
        except Exception as e:
            print(e)
            self.logger.logging(date=time.time(), action='ERROR(448)', order_type=None, price=None, amount=None)
            print('Error received when closing open positions')


    def limit_buy_order_until_open(self, action='OPEN LONG', SL=None, pos_amount=None):
        ''' 
        Summary: creates limit buy order, if order was not opened for 20 seconds and cancels the order and send new order with new price.
        :param SL (float): percentage of short stop loss, default None
        '''
        if pos_amount == None:
            # use self.amount as amount when opening position
            amount = self.amount
        else:
            # use pos_amount as amount when closing the open positions. pos_amount is the position size of the open positions
            amount = pos_amount
        in_position = False
        while not in_position:
            self.bid_price = float(self.binance.fetch_order_book(symbol=self.symbol, limit=10)['bids'][0][0])
            is_balance_available = self.check_balance(price=self.bid_price, order_type='limit', amount=amount)
            if action == 'OPEN LONG':
                if is_balance_available == False:
                    break
            elif action == 'CLOSE SHORT':
                is_balance_available == True
            
            if is_balance_available:
                try:
                    self.binance.create_limit_buy_order(symbol=self.symbol, amount=amount, price=self.bid_price)
                    self.logger.logging(date=time.time(), action=action, order_type="limit", price=self.bid_price, amount=amount)
                    print('Limit buy order sent successfully!')
                    time.sleep(20)
                    open_orders = self.binance.fetch_open_orders(symbol=self.symbol)
                    open_order_counter = 0
                    for order in open_orders:
                        if order["stopPrice"] == None:
                            open_order_counter += 1

                    if open_order_counter == 0:
                        if SL is not None:
                            long_sl_price = self.calculate_SL_long(SL)
                            params = {'stopLossPrice':long_sl_price}
                            self.binance.create_market_sell_order(symbol=self.symbol, amount=amount, params=params)
                            self.logger.logging(date=time.time(), action='SL FOR LONG', order_type='market', price=long_sl_price, amount=amount)
                            print('Market sell order for stop loss sent successfully!')
                            in_position = True
                        else:
                            in_position = True
                    else:
                        for order in open_orders:
                            if order['stopPrice'] == None:
                                self.binance.cancel_order(id=order['id'], symbol=self.symbol)
                                self.logger.logging(date=time.time(), action='CANCEL ORDER', order_type=None, price=None, amount=amount)
                                print('The limit buy order was canceled because the position was not opened, it will be resent.')
                except Exception as e:
                    error_message = f'{str(e)}\n{str(traceback.format_exc())}'
                    print(error_message)
                    self.exit(error_message=error_message)
            else:
                print('Insufficient balance!')
                break


    def limit_sell_order_until_open(self, action='OPEN SHORT', SL=None, pos_amount=None):
        ''' 
        Summary: creates limit sell order, if order was not opened for 20 seconds and cancels the order and send new order with new price.
        :param SL (float): percentage of short stop loss, default None
        '''
        if pos_amount == None:
            # use self.amount as amount when open position
            amount = self.amount
        else:
            # use pos_amount as amount when closing the open positions. pos_amount is the position size of the open positions
            amount = pos_amount
        in_position = False
        while not in_position:
            self.ask_price = float(self.binance.fetch_order_book(symbol=self.symbol, limit=10)['asks'][0][0])
            is_balance_available = self.check_balance(price=self.ask_price, order_type='limit', amount=amount)
            if action == 'OPEN SHORT':
                if is_balance_available == False:
                    break
            elif action == 'CLOSE LONG':
                is_balance_available = True

            if is_balance_available:
                try:
                    self.binance.create_limit_sell_order(symbol=self.symbol, amount=amount, price=self.ask_price)
                    self.logger.logging(date=time.time(), action=action, order_type='limit', price=self.ask_price, amount=amount)
                    print('Limit sell order sent successfully!')
                    time.sleep(20)
                    open_orders = self.binance.fetch_open_orders(symbol=self.symbol)
                    open_order_counter = 0
                    for order in open_orders:
                        if order['stopPrice'] == None:
                            open_order_counter += 1

                    if open_order_counter == 0:
                        if SL is not None:
                            short_sl_price = self.calculate_SL_short(SL)
                            params = {'stopLossPrice':short_sl_price}
                            self.binance.create_market_buy_order(symbol=self.symbol, amount=amount, params=params)
                            self.logger.logging(date=time.time(), action='SL FOR SHORT', order_type='market', price=short_sl_price, amount=amount)
                            print('Market buy order for stop loss sent successfully!')
                            in_position = True
                        else:
                            in_position =True
                    else:
                        for order in open_orders:
                            if order['stopPrice'] == None:
                                self.binance.cancel_order(id=order['id'], symbol=self.symbol)
                                self.logger.logging(date=time.time(), action='CANCEL ORDER', order_type=None, price=None, amount=amount)
                                print('The limit sell order canceled because the position was not opened, it will be resent.')
                except Exception as e:
                    error_message = f'{str(e)}\n{str(traceback.format_exc())}'
                    print(error_message)
                    self.exit(error_message=error_message)

    
    def close_long_positions_with_limit_order(self):
        '''
        Summary: calculates the position size of the open long positions according to the leverage and size info of the open long positions then closes them all
        '''
        open_pos_side = self.binance.fetch_positions(symbols=[self.symbol])[0]['side']
        if open_pos_side == 'long':
            open_pos_leverage = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['leverage'])
            open_pos_size = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['positionAmt'])
            open_pos_amount = abs(open_pos_leverage * open_pos_size)
            self.limit_sell_order_until_open(action='CLOSE LONG', pos_amount=open_pos_amount)
            print('All long positions are closed!')

            # cancel stop loss orders for closed positions
            open_orders = self.binance.fetch_open_orders(symbol=self.symbol)
            for order in open_orders:
                if order['stopPrice'] is not None:
                    self.binance.cancel_order(id=order['id'], symbol=self.symbol)
            print('All stop loss orders canceled!')


    def close_short_positions_with_limit_order(self):
        '''
        Summary: calculates the position size of the open short positions according to the leverage and size info of the open short positions then closes them all
        '''
        open_pos_side = self.binance.fetch_positions(symbols=[self.symbol])[0]['side']
        if open_pos_side == 'short':
            open_pos_leverage = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['leverage'])
            open_pos_size = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['positionAmt'])
            open_pos_amount = abs(open_pos_leverage * open_pos_size)
            self.limit_buy_order_until_open(action='CLOSE SHORT', pos_amount=open_pos_amount)
            print('All short positions are closed!')

            # cancel stop loss orders for closed positions
            open_orders = self.binance.fetch_open_orders(symbol=self.symbol)
            for order in open_orders:
                if order['stopPrice'] is not None:
                    self.binance.cancel_order(id=order['id'], symbol=self.symbol)
            print('All stop loss orders canceled!')


    def close_all_open_positions_with_limit_order(self):
        ''' 
        Summary: calculates the position size of the open positions according to the leverage, size and side info of open positions then closes them all
        '''
        open_pos_side = self.binance.fetch_positions(symbols=[self.symbol])[0]['side']
        open_pos_leverage = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['leverage'])
        open_pos_size = float(self.binance.fetch_positions(symbols=[self.symbol])[0]['info']['positionAmt'])
        open_pos_amount = abs(open_pos_leverage * open_pos_size)
        try:
            self.binance.set_leverage(leverage=1, symbol=self.leverage_symbol)
        except:
            pass
        try:
            if open_pos_side == 'long':
                self.limit_sell_order_until_open(action='CLOSE LONG', pos_amount=open_pos_amount)
            elif open_pos_side == 'short':
                self.limit_buy_order_until_open(action='CLOSE SHORT', pos_amount=open_pos_amount)
            print('All open positions closed!')

            # cancel stop loss orders for closed positions
            open_orders = self.binance.fetch_open_orders(symbol=self.symbol)
            for order in open_orders:
                if order['stopPrice'] is not None:
                    self.binance.cancel_order(id=order['id'], symbol=self.symbol)
            print('All stop loss orders canceled!')
        except Exception as e:
            print(e)
            print('Error received when closing open positions')


    def dataset_creater(self, max_length:int) -> pd.DataFrame:
        '''
        Summary: Iterates get_binance_OHLCV function until create max_length sized dataset.
        :param max_length (int): length of dataset
        :return created pandas DataFrame  
        '''
        df_ohlcv = self.get_binance_OHLCV(limit=1)
        current_timestamp = int(list(df_ohlcv['timestamp'])[0])
        unix_difference_for_1m = 60000

        if self.timeframe.endswith('m'):
            minute = int(self.timeframe.split('m')[0])          # to find out how many minutes the frequency is

        elif self.timeframe.endswith('h'):
            minute = int(self.timeframe.split('h')[0]) * 60     # to find out how many minutes the frequency is

        since = current_timestamp - (minute * unix_difference_for_1m * max_length)
        df_ohlcv = self.get_binance_OHLCV(since=since)
        last_timestamp = df_ohlcv['timestamp'][len(df_ohlcv) - 1]

        while last_timestamp < current_timestamp:
            df2 = self.get_binance_OHLCV(since=last_timestamp)
            df2 = df2.iloc[1:, :]
            df_ohlcv = pd.concat([df_ohlcv, df2], axis=0, ignore_index=True)
            if len(df2) > 1:
                last_timestamp = df2['timestamp'][len(df2) - 1]
            else:
                break

            if current_timestamp in list(df2['timestamp']):
                break

        if len(df_ohlcv) > max_length:
            df_ohlcv = df_ohlcv.iloc[(len(df_ohlcv) - max_length):, :]   

        last_candle = self.get_binance_OHLCV(limit=1)



        # @TODO: veri çekilene kadar geçen süreçte yeni eklenen mumlar varsa onları da tespit et ve veri setine ekle



        if list(last_candle['timestamp'])[0] != df_ohlcv['timestamp'].iloc[- 1]:
            df_ohlcv = pd.concat([df_ohlcv, last_candle], axis=0, ignore_index=True)
        else:
            pass

        df_ohlcv = df_ohlcv.astype({'timestamp':str})

        return df_ohlcv


    def send_trade_info_to_slackbot(self, action=None, entry_price=None, sl_price=None, tp_price=None, position_size=None, total_position_size=None):
        strategy_name = self.filename.split(' - ')[0]
        try:
            if action == 'OPEN SHORT':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] opened short position!\n\nAction: {action}\nEntry Price: {entry_price} USDT\nStop Loss Price: {sl_price} USDT\nTake Profit Price: {tp_price} USDT\nPosition Size: {self.amount} {self.symbol.split("/")[0]}\nTotal Position Size: {total_position_size} {self.symbol.split("/")[0]}\nNumber of Positions: {float(total_position_size) / self.amount}\n----------------------------------------------------------\n\n'

            elif action == 'OPEN LONG':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] opened long position!\n\nAction: {action}\nEntry Price: {entry_price} USDT\nStop Loss Price: {sl_price} USDT\nTake Profit Price: {tp_price} USDT\nPosition Size: {self.amount} {self.symbol.split("/")[0]}\nTotal Position Size: {total_position_size} {self.symbol.split("/")[0]}\nNumber of Positions: {float(total_position_size) / self.amount}\n----------------------------------------------------------\n\n'

            elif action == 'CLOSE SHORT':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] closed short position(s)!\n\nAction: {action}\nClose Price: {entry_price} USDT\nClosed Position Size: {position_size} {self.symbol.split("/")[0]}\n----------------------------------------------------------\n\n'

            elif action == 'CLOSE LONG':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] closed long position(s)!\n\nAction: {action}\nClose Price: {entry_price} USDT\nClosed Position Size: {position_size} {self.symbol.split("/")[0]}\n----------------------------------------------------------\n\n'

            elif action == 'SL FOR LONG':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] closed long position with stop loss!\n\nAction: {action}\nClose Price: {entry_price} USDT\nClosed Position Size: {position_size} {self.symbol.split("/")[0]}\n----------------------------------------------------------\n\n'

            elif action == 'TP FOR LONG':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] closed long position with take profit!\n\nAction: {action}\nClose Price: {entry_price} USDT\nClosed Position Size: {position_size} {self.symbol.split("/")[0]}\n----------------------------------------------------------\n\n'

            elif action == 'SL FOR SHORT':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] closed short position with stop loss!\n\nAction: {action}\nClose Price: {entry_price} USDT\nClosed Position Size: {position_size} {self.symbol.split("/")[0]}\n----------------------------------------------------------\n\n'

            elif action == 'TP FOR SHORT':
                trade_info = f'\n----------------------------------------------------------\n{strategy_name}[{self.symbol}] closed short position with take profit!\n\nAction: {action}\nClose Price: {entry_price} USDT\nClosed Position Size: {position_size} {self.symbol.split("/")[0]}\n----------------------------------------------------------\n\n'
        
        except Exception as e:
            print(e)
            self.logger.logging(date=time.time(), action='ERROR - EXIT(768)', order_type=None, price=None, amount=None)
        
        try:
            slack_bot.send_trade_info(message=trade_info)
        except Exception as e:
            print(e)
            self.logger.logging(date=time.time(), action='ERROR - EXIT(774)', order_type=None, price=None, amount=None)

    

    def initialize_open_orders_dict(self):
        '''
        Summary: checks the logs/open_orders path, if there is a file that starts with strategies name, takes the file as open orders list.
        '''
        strategy_name = self.filename.split(' - ')[0]
        open_order_files = os.listdir(self.open_orders_path)
        for order_file in open_order_files:
            if order_file.startswith(strategy_name):
                # take open orders' ids from strategies open order logs
                with open(f'{self.open_orders_path}/{order_file}', 'r', encoding='utf-8') as f:
                    for line in f:
                        order_dict = {
                            'sl_price':str(line.split(' & ')[0]).split('sl_price:')[1].strip('\n'),
                            'tp_price':str(line.split(' & ')[1]).split('tp_price:')[1].strip('\n'),
                            'side':str(line.split(' & ')[2]).split('side:')[1].strip('\n')
                        }
                        self.add_conditional_order(order_dict=order_dict)


    def write_open_orders_to_file(self):
        '''
        Summary: create a open_orders log file for the strategy and print open orders' ids to the file
        '''
        print(self.conditional_orders)
        strategy_name = self.filename.split(' - ')[0]
        with open(f'{self.open_orders_path}/{strategy_name}.txt', 'w', encoding='utf-8') as f:
            for id_dict in self.conditional_orders:
                f.write(f'sl_price:{id_dict["sl_price"]} & tp_price:{id_dict["tp_price"]} & side:{id_dict["side"]}')
                f.write('\n')
        print(f'Open orders saved to: {self.open_orders_path}/{strategy_name}.txt file. ')
        return f'{self.open_orders_path}/{strategy_name}.txt'
    

    def number_of_open_positions(self):
        try:
            positions = self.binance.fetch_positions(symbols=[self.symbol])
            number_of_positions = float(positions[0]['info']['positionAmt']) / self.amount
        except IndexError:
            number_of_positions = 0
        except Exception as e:
            print(e)
            self.logger.logging(date=time.time(), action='ERROR(785)', order_type=None, price=None, amount=None)
        return abs(number_of_positions)
    

    def start_order_monitoring(self):
        self.monitoring_thread = threading.Thread(target=self.monitor_orders, daemon=True)
        self.stop_monitoring = False
        self.monitoring_thread.start()


    def monitor_orders(self):
        try:
            while not self.stop_monitoring:
                print("Monitoring orders...")
                with self.conditional_orders_lock:
                    self.check_market_price()
                time.sleep(15)  # Adjust sleep time as needed
        except KeyboardInterrupt:
            error_message = str(traceback.format_exc())
            print("KeyboardInterrupt detected, stopping order monitoring...")
            self.exit(error_message=error_message)
        except Exception as e:
            print(f"An error occurred in order monitoring: {e}")
            traceback.print_exc()
        finally:
            self.cleanup_order_monitoring()


    def stop_order_monitoring(self):
        self.stop_monitoring = True
        if self.monitoring_thread:
            self.monitoring_thread.join()


    def cleanup_order_monitoring(self):
        # Perform any necessary cleanup
        print("Cleaning up order monitoring resources...")
        # Add any additional cleanup logic here


    def add_conditional_order(self, order_dict:dict):
        with self.conditional_orders_lock:
            self.conditional_orders.append(order_dict)
            print(f"Order dict: {order_dict} added to conditional orders.")
      

    def exit(self, error_message:str=None):
        '''
        Summary: When the program receives an error and stops running: 
            * writes open orders to a file
            * sends error message to the slack channel 
            * gives option to the user to cancel open orders and close open positions
        '''

        if error_message == None:
            error_message = 'An error occured in order monitoring'

        self.stop_order_monitoring()

        open_orders_file = self.write_open_orders_to_file()
        slack_bot.send_error_message(error_message=error_message)

        choice1 = input('Do you want to cancel the orders? (y/n): ')
        if choice1.lower() == 'y':
            self.cancel_all_orders()
            os.remove(open_orders_file)     # if open orders are closed, delete the file

        choice2 = input('Do you want to close the positions? (y/n): ')
        if choice2.lower() == 'y':
            self.close_all_open_positions_with_market_order()