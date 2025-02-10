import os
from dotenv import load_dotenv
import yfinance as yf
import schedule
import time
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

load_dotenv()

STOCKS = {"ASML": None, "GOOG": None, "GOOGL": None, "NVDA": None, "AAPL": None, "TSLA": None, "PLTR": None,
          "NFLX": None, "JPM": None, "META": None, "AMZN": None, "ORCL": None}
THRESHOLD = -4
EMAIL_SENDER = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
ALERTED_STOCKS = {}
log_messages = []


def log_message(message):
    print(message)
    log_messages.append(message)


def send_slack_message():
    if not SLACK_WEBHOOK_URL:
        log_message("[WARNING] Geen Slack Webhook URL ingesteld!")
        return

    slack_message = "\n".join(log_messages)
    payload = {"text": slack_message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            log_message("[INFO] Slack-bericht succesvol verzonden.")
        else:
            log_message(f"[ERROR] Slack-fout: {response.status_code} - {response.text}")
    except Exception as e:
        log_message(f"[ERROR] Fout bij verzenden Slack-bericht: {e}")


def get_stock_prices():
    log_message("\n[INFO] Aandelenprijzen worden opgehaald...")
    for stock in STOCKS.keys():
        ticker = yf.Ticker(stock)
        data = ticker.history(period="2d")
        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            current_price = data["Close"].iloc[-1]
            STOCKS[stock] = (prev_close, current_price)
            log_message(f"[INFO] {stock}: Gisteren: ${prev_close:.2f}, Nu: ${current_price:.2f}")
        else:
            log_message(f"[WARNING] Geen data voor {stock} gevonden.")


def check_stocks():
    log_messages.clear()
    current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    log_message(f"\n[INFO] Calculating changes... - {current_time}")
    get_stock_prices()

    for stock, (prev_close, current_price) in STOCKS.items():
        percentage_change = ((current_price - prev_close) / prev_close) * 100
        log_message(f"[INFO] {stock}: {percentage_change:.2f}% change")

        if percentage_change <= THRESHOLD:
            if stock not in ALERTED_STOCKS or not ALERTED_STOCKS[stock]:
                log_message(f"[ALERT] {stock} is meer dan {THRESHOLD}% gedaald! E-mail en Slack worden verzonden...")
                send_email(stock, percentage_change)
                ALERTED_STOCKS[stock] = True
            else:
                log_message(f"[INFO] E-mail al verzonden voor {stock}.")
        else:
            if stock in ALERTED_STOCKS and ALERTED_STOCKS[stock]:
                log_message(f"[INFO] {stock} is hersteld boven de drempel. Reset melding.")
                ALERTED_STOCKS[stock] = False
    send_slack_message()


def send_email(stock, percentage_change):
    subject = f"ALERT: {stock} is met {percentage_change:.2f}% gedaald!"
    body = f"Waarschuwing! {stock} is gedaald met {percentage_change:.2f}%!"

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.strato.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        log_message(f"[INFO] E-mail verzonden voor {stock} ({percentage_change:.2f}%)")
    except Exception as e:
        log_message(f"[ERROR] Fout bij verzenden e-mail voor {stock}: {e}")


def send_startup_message():
    log_message("[INFO] Stock monitor gestart...")
    send_slack_message()


send_startup_message()
check_stocks()
schedule.every().hour.do(check_stocks)

while True:
    schedule.run_pending()
    time.sleep(60)
