import pandas as pd
import ccxt
import time
import json
from pprint import pprint
from datetime import datetime
from binance_config import META_DATA

class BinancePerformanceReport:
    def __init__(self) -> None:
        self.META_DATA_LIST = []
        for meta in META_DATA:
            meta_dict = {
                'Algorithm Name':meta['strategy']['algorithm_name'],
                'Symbol':meta['strategy']['symbol'],
                'Account':meta['strategy']['account'],
                'Api Label':meta['strategy']['api_label'],
                'Start Date':meta['strategy']['start_date'],
                'api_key':meta['strategy']['api_key'],
                'secret_key':meta['strategy']['secret_key']
            }
            self.META_DATA_LIST.append(meta_dict)

        self.API_KEY = None
        self.SECRET_KEY = None

        self.symbol = None
        self.strategy_name = None

        self.list_for_excel = []
        self.timestamp_difference_for_24h = 86400000
        self.today = str(datetime.now()).split(' ')[0] + ' 00:00:00'
        #self.today_timestamp = (int(datetime.timestamp(datetime.strptime(self.today, '%Y-%m-%d %H:%M:%S'))) + 10800) * 1000
        self.today_timestamp = int(datetime.timestamp(datetime.strptime(self.today, '%Y-%m-%d %H:%M:%S'))) * 1000
        self.unix_7d_ago = self.today_timestamp - (self.timestamp_difference_for_24h * 6)
        self.unix_30d_ago = self.today_timestamp - (self.timestamp_difference_for_24h * 29)
        self.unix_list = [self.today_timestamp, self.unix_7d_ago, self.unix_30d_ago]


    def exchange_connection(self, API_KEY:str, SECRET_KEY:str):
        while True:
            try:
                binance = ccxt.binance({'enableRateLimit':True, 'apiKey':API_KEY, 'secret':SECRET_KEY, 'options':{'defaultType':'future'}})
                break
            except Exception as e:
                print(e)
                time.sleep(1)
        return binance


    def calculate_metrics(self, positions:list, unix, time_label=None):
        if unix == self.today_timestamp:
            time_label = 'today'
        elif unix == self.unix_7d_ago:
            time_label = '7d'
        elif unix == self.unix_30d_ago:
            time_label = '30d'
        else:
            time_label = 'None'

        total_pnl = 0
        total_fee = 0
        total_win = 0
        total_loss = 0
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        portfolio_profit = 0
        portfolio_loss = 0
        for pos in positions:
            realized_pnl = float(pos['info']['realizedPnl'])
            fee = float(pos['fee']['cost'])
            if realized_pnl > 0:
                total_win += realized_pnl
                total_trades += 1
                winning_trades += 1
                try:
                    portfolio_profit += (realized_pnl / (float(pos['info']['price'])))
                except ZeroDivisionError:
                    pass
            elif realized_pnl < 0:
                total_loss += realized_pnl
                total_trades += 1
                losing_trades += 1
                try:
                    portfolio_loss += (abs(realized_pnl) / (float(pos['info']['price'])))
                except ZeroDivisionError:
                    pass

            total_pnl += realized_pnl
            total_fee += fee    

        try:
            win_rate = round(winning_trades / (losing_trades + winning_trades), 3)
        except ZeroDivisionError:
            win_rate = 0.0

        try:
            portfolio_profit_factor = round((portfolio_profit / portfolio_loss), 3)
        except ZeroDivisionError:
            portfolio_profit_factor = 0.0
        

        try:
            profit_factor = round(total_win / abs(total_loss), 3)
        except ZeroDivisionError:
            profit_factor = 0.0

        try:
            average_pnl = total_pnl / total_trades
        except ZeroDivisionError:
            average_pnl = 0.0

        try:
            profit_loss_ratio = round((total_win / winning_trades) / (abs(total_loss) / losing_trades), 3)
        except ZeroDivisionError:
            profit_loss_ratio = 0.0

        try:
            total_pnl = round(total_pnl, 3)
        except:
            pass
        try:
            average_pnl = round(average_pnl, 3)
        except:
            pass
        try:
            total_win = round(total_win, 3)
        except:
            pass
        try:
            total_loss = round(total_loss, 3)
        except:
            pass
        try:
            total_fee = (round(total_fee, 3) * (-1))
        except:
            pass

        try:
            portfolio_profit = round(portfolio_profit, 3)
        except:
            pass

        try:
            portfolio_loss = round(portfolio_loss, 3)
        except:
            pass

        start_date = datetime.utcfromtimestamp(int(unix / 1000)).strftime('%Y-%m-%d %H:%M:%S')
        number_of_orders = len(positions)

        metrics_info = {
            'Strategy Name':self.strategy_name,
            'Symbol':self.symbol,
            'Time Label':time_label,
            "Report's Start Time": start_date,
            'Profit Factor':profit_factor,
            'Win Rate':win_rate,
            'Total Pnl':total_pnl,
            'Portfolio Profit Factor':portfolio_profit_factor,
            'Total Win':total_win,
            'Total Loss':total_loss,
            'Portfolio Profit':portfolio_profit,
            'Portfolio Loss':portfolio_loss,
            'Number of Orders':number_of_orders,
            'Total Trades':total_trades,
            'Winning Trades':winning_trades,
            'Losing Trades':losing_trades,
            'Average Pnl':average_pnl,
            'Profit Loss Ratio':profit_loss_ratio,
            'Total Fee':total_fee
        }
        self.list_for_excel.append(metrics_info)

        return metrics_info


    def fetch_positions(self, since=None):
        binance = self.exchange_connection(API_KEY=self.API_KEY, SECRET_KEY=self.SECRET_KEY) 
        positions = binance.fetch_my_trades(symbol=self.symbol, since=since)

        if since == self.unix_30d_ago:
            last_unix = 0
            try:
                last_unix = positions[-1]['timestamp']
            except:
                last_unix += (since + (self.timestamp_difference_for_24h * 1))

            while last_unix <= self.today_timestamp:
                positions2 = binance.fetch_my_trades(symbol=self.symbol, since=last_unix)
                try:
                    if len(positions2) == 1:
                        break
                    else:
                        positions2.pop(0)
                        last_unix = positions2[-1]['timestamp']
                except:
                    last_unix += (self.timestamp_difference_for_24h * 1)

                positions = positions + positions2

        return positions


    def main(self, timestamp:int=None):
        results_list = []
        for meta_dict in self.META_DATA_LIST:
            self.API_KEY = meta_dict['api_key']
            self.SECRET_KEY = meta_dict['secret_key']
            self.symbol = meta_dict['Symbol']
            self.strategy_name = meta_dict['Algorithm Name']
            del meta_dict['api_key']
            del meta_dict['secret_key']

            for unix in self.unix_list:
                if unix == self.today_timestamp:
                    time_label = 'today'
                elif unix == self.unix_7d_ago:
                    time_label = '7d'
                elif unix == self.unix_30d_ago:
                    time_label = '30d'
                else:
                    time_label = 'None'

                positions = self.fetch_positions(since=unix)
                metrics_dict = self.calculate_metrics(positions=positions, unix=unix, time_label=time_label)

                meta_str = self.get_report_string(rdict=meta_dict, header='Algo Meta Data')
                metrics_str = self.get_report_string(rdict=metrics_dict, header=f'Trading Metrics ({time_label})')

                results_str = meta_str + metrics_str
                results_list.append(results_str)

                print(results_str)

        return results_list
    

    def report_for_slack(self, timelabel:str):
        results_list = []
        for meta_dict in self.META_DATA_LIST:
            instant_date = str(datetime.now()).split('.')[0]
            unix_24h_ago = ((int(datetime.timestamp(datetime.strptime(instant_date, '%Y-%m-%d %H:%M:%S'))) + 10800) * 1000) - self.timestamp_difference_for_24h

            self.API_KEY = meta_dict['api_key']
            self.SECRET_KEY = meta_dict['secret_key']
            self.symbol = meta_dict['Symbol']
            del meta_dict['api_key']
            del meta_dict['secret_key']

            if timelabel == '24h':
                since = unix_24h_ago
            elif timelabel == '7d':
                since = self.unix_7d_ago

            positions = self.fetch_positions(since=since)
            metrics_dict = self.calculate_metrics(positions=positions, unix=since)

            meta_str = self.get_report_string(rdict=meta_dict, header='Algo Meta Data')
            metrics_str = self.get_report_string(rdict=metrics_dict, header=f'Trading Metrics ({timelabel})')

            results_str = meta_str + metrics_str
            results_list.append(results_str)

        return results_list
    

    def get_report_string(self, rdict:dict, header:str) -> str:
        # Our report string 
        rstring = ""
        keys = list(rdict.keys())
        values = list(rdict.values())
        max_len_key = max([len(key) for key in keys])
        LPADDING = 5 + max_len_key
        RPADDING = 25
        # Center the header with padded "-" on the left and right
        rstring += "-"*((LPADDING+RPADDING+2)//2 - len(header)//2) + header + "-"*((LPADDING+RPADDING+2)//2 - len(header)//2) + "\n"

        # Metrics
        for i in range(len(keys)):
            rstring += f"{keys[i].ljust(LPADDING)}: {str(values[i]).rjust(RPADDING)}\n"

        rstring += "-"*(LPADDING+RPADDING+2) + "\n"

        return rstring


    def convert_excel(self):
        df = pd.DataFrame(self.list_for_excel)
        df.to_excel(f'{self.today.split(" ")[0]}.xlsx', index=False)


# @TODO:SİLİNECEK

    def last_7days_metrics(self):
        results_list = []
        for meta_dict in self.META_DATA_LIST:
            self.API_KEY = meta_dict['api_key']
            self.SECRET_KEY = meta_dict['secret_key']
            self.symbol = meta_dict['Symbol']
            self.strategy_name = meta_dict['Algorithm Name']
            del meta_dict['api_key']
            del meta_dict['secret_key']

            positions = self.fetch_positions(since=self.unix_7d_ago)

            """with open(f'{counter}_{strategy_name}.json', 'w') as f:
                json.dump(positions, f)"""

            metrics_dict = self.calculate_metrics(positions=positions, unix=self.unix_7d_ago)

            meta_str = self.get_report_string(rdict=meta_dict, header='Algo Meta Data')
            metrics_str = self.get_report_string(rdict=metrics_dict, header='Trading Metrics (7d)')

            results_str = meta_str + metrics_str
            results_list.append(results_str)
            print(results_str)

            

if __name__ == '__main__':
    report = BinancePerformanceReport()
    #report.main()
    #report.convert_excel()
    #report.last_7days_metrics()