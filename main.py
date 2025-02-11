import os
import mysql.connector
from dotenv import load_dotenv
import yfinance as yf
import schedule
import time
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from datetime import datetime

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

STOCKS = {"ASML", "GOOG", "GOOGL", "NVDA", "AAPL", "TSLA", "PLTR", "NFLX", "JPM", "META", "AMZN", "ORCL"}
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


def db_connect():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def save_stock_to_db(stock_symbol, prev_close, current_price, percentage_change, alert_sent):
    conn = db_connect()
    cursor = conn.cursor()

    prev_close = float(prev_close)
    current_price = float(current_price)
    percentage_change = float(percentage_change)

    cursor.execute("SELECT current_price FROM stock_prices WHERE stock_symbol = %s ORDER BY timestamp DESC LIMIT 1",
                   (stock_symbol,))
    last_price = cursor.fetchone()

    if last_price and abs(float(last_price[0]) - current_price) < 0.5:
        log_message(f"[INFO] Kleine prijsverandering voor {stock_symbol}, geen update nodig.")
        return

    cursor.execute("""
        INSERT INTO stock_prices (stock_symbol, prev_close, current_price, percentage_change, alert_sent)
        VALUES (%s, %s, %s, %s, %s)
    """, (stock_symbol, prev_close, current_price, percentage_change, alert_sent))

    conn.commit()
    cursor.close()
    conn.close()


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
    log_messages.clear()
    log_message("\n[INFO] Aandelenprijzen worden opgehaald...")

    for stock in STOCKS:
        ticker = yf.Ticker(stock)
        data = ticker.history(period="2d")

        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            current_price = data["Close"].iloc[-1]
            percentage_change = ((current_price - prev_close) / prev_close) * 100

            log_message(f"[INFO] {stock}: Gisteren: ${prev_close:.2f}, Nu: ${current_price:.2f}, Verandering: {percentage_change:.2f}%")

            alert_sent = False
            if percentage_change <= THRESHOLD:
                if stock not in ALERTED_STOCKS or not ALERTED_STOCKS[stock]:
                    log_message(f"[ALERT] {stock} is meer dan {THRESHOLD}% gedaald! E-mail en Slack worden verzonden...")
                    send_email(stock, percentage_change)
                    send_slack_message()
                    ALERTED_STOCKS[stock] = True
                    alert_sent = True
                else:
                    log_message(f"[INFO] E-mail al verzonden voor {stock}.")
            else:
                if stock in ALERTED_STOCKS and ALERTED_STOCKS[stock]:
                    log_message(f"[INFO] {stock} is hersteld boven de drempel. Reset melding.")
                    ALERTED_STOCKS[stock] = False

            save_stock_to_db(stock, prev_close, current_price, percentage_change, alert_sent)
        else:
            log_message(f"[WARNING] Geen data voor {stock} gevonden.")

    send_slack_message()


def run_stock_monitor():
    log_message("\n[INFO] Stock monitor gestart...")
    send_slack_message()
    get_stock_prices()


schedule.every().hour.do(get_stock_prices)

run_stock_monitor()
while True:
    schedule.run_pending()
    time.sleep(60)
