import random
from datetime import datetime
import time
import pandas as pd
import os

class Logger:
    def __init__(self, filename) -> None:
        self.filename = filename
        self.txt_path =  os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "binance_ccxt", "logs", "txt")
        self.excel_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "binance_ccxt", "logs", "excel")
        self.strategies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "binance_ccxt", "strategies")

    def logging(self, date, action, order_type, price, amount):
        os.chdir(self.txt_path)
        try:
            date = datetime.fromtimestamp(int(date))
        except:
            pass
        log = f"{date}\t-\t{action}\t-\t{order_type}\t-\t{price}\t-\t{amount}"
        if action == "OPEN LONG":
            print(f"\033[1;32;38m{log}\033[0m")
        elif action == "CLOSE LONG":
            print(f"\033[1;32;38m{log}\033[0m")
        elif action == "OPEN SHORT":
            print(f"\033[1;31;38m{log}\033[0m")
        elif action == "CLOSE SHORT":
            print(f"\033[1;31;38m{log}\033[0m")
        elif action == "CANCEL ORDER":
            print(f"\033[1;35;38m{log}\033[0m")
        elif action == "SL FOR LONG":
            print(f"\033[1;33;38m{log}\033[0m")
        elif action == "SL FOR SHORT":
            print(f"\033[1;33;38m{log}\033[0m")

        with open(self.filename, "a", encoding="utf-8") as log_file:
            log_file.write(f"{log}\n")

    def convert_logs_to_excel(self, filename):
        os.chdir(self.txt_path)
        list_for_excel = []
        with open (filename, "r", encoding="utf-8") as file:
            lines = file.readlines()
            for line in lines:
                elements = line.split("\t-\t")
                date = elements[0]
                action = elements[1]
                type = elements[2]
                price = elements[3]
                amount = elements[4].rstrip("\n")

                log = {
                    "date":date,
                    "action":action,
                    "type":type,
                    "price":price,
                    "amount":amount
                }
                list_for_excel.append(log)
        os.chdir(self.excel_path)
        excel_file = filename.split(".")[0] + ".xlsx"
        df = pd.DataFrame(list_for_excel)
        df.to_excel(excel_file, index=False)