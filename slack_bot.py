import slack
from binance_config import SLACK_PERFORMANCE_REPORT_BOT_TOKEN, SLACK_ERROR_CODE_BOT_TOKEN, SLACK_TRADE_MESSAGE_BOT_TOKEN
from performance_report import BinancePerformanceReport
from datetime import datetime
from flask import Flask, request, Response

def send_trade_info(message:str):
    print(message)
    trade_client = slack.WebClient(token=SLACK_TRADE_MESSAGE_BOT_TOKEN)
    trade_client.chat_postMessage(channel='#trades', text=message)



def send_error_message(error_message:str):
    print(error_message)
    error_client = slack.WebClient(token=SLACK_ERROR_CODE_BOT_TOKEN)
    error_client.chat_postMessage(channel='#error_messages', text=error_message)


if __name__ == '__main__':
    # saat başı son 24 saatin raporunu atan kod
    last_hour = None
    hour_list = [0, 16]
    #hour_list = [x for x in range(0, 24)]
    while True:
        hour = datetime.now().hour
        if hour in hour_list and hour != last_hour:
            last_hour = hour

            report = BinancePerformanceReport()

            if hour == 0:
                result_list = report.report_for_slack(timelabel='7d')

                for result in result_list:
                    client = slack.WebClient(token=SLACK_PERFORMANCE_REPORT_BOT_TOKEN)
                    client.chat_postMessage(channel='#performance_report', text=result)
                    print(result)

            else:
                result_list = report.report_for_slack(timelabel='24h')

                for result in result_list:
                    client = slack.WebClient(token=SLACK_PERFORMANCE_REPORT_BOT_TOKEN)
                    client.chat_postMessage(channel='#performance_report', text=result)
                    print(result)