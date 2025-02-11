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
import numpy as np
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

    cursor.execute("""
        INSERT INTO stock_prices (stock_symbol, prev_close, current_price, percentage_change, alert_sent)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        stock_symbol,
        float(prev_close),
        float(current_price),
        float(percentage_change),
        alert_sent
    ))

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
        print(f"[INFO] E-mail verzonden voor {stock} ({percentage_change:.2f}%)")
    except Exception as e:
        print(f"[ERROR] Fout bij verzenden e-mail voor {stock}: {e}")


def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("[WARNING] Geen Slack Webhook URL ingesteld!")
        return

    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            print("[INFO] Slack-bericht succesvol verzonden.")
        else:
            print(f"[ERROR] Slack-fout: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] Fout bij verzenden Slack-bericht: {e}")


def get_stock_prices():
    print("\n[INFO] Aandelenprijzen worden opgehaald...")
    for stock in STOCKS:
        ticker = yf.Ticker(stock)
        data = ticker.history(period="2d")

        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            current_price = data["Close"].iloc[-1]
            percentage_change = ((current_price - prev_close) / prev_close) * 100

            print(f"[INFO] {stock}: Gisteren: ${prev_close:.2f}, Nu: ${current_price:.2f}, Verandering: {percentage_change:.2f}%")

            alert_sent = False
            if percentage_change <= THRESHOLD:
                print(f"[ALERT] {stock} is meer dan {THRESHOLD}% gedaald! E-mail en Slack worden verzonden...")
                send_email(stock, percentage_change)
                send_slack_message(f"[ALERT] {stock} is {percentage_change:.2f}% gedaald!")
                alert_sent = True

            save_stock_to_db(stock, prev_close, current_price, percentage_change, alert_sent)

        else:
            print(f"[WARNING] Geen data voor {stock} gevonden.")


def run_stock_monitor():
    print("\n[INFO] Stock monitor gestart...")
    send_slack_message("[INFO] Stock monitor gestart...")
    get_stock_prices()


schedule.every().hour.do(get_stock_prices)

run_stock_monitor()
while True:
    schedule.run_pending()
    time.sleep(60)
