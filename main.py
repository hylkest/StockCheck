import os
from dotenv import load_dotenv

import yfinance as yf
import schedule
import time
import smtplib
from email.mime.text import MIMEText

load_dotenv()

STOCKS = {
    "ASML": None,
    "GOOG": None,
    "GOOGL": None,
    "NVDA": None
}
THRESHOLD = -5
EMAIL_SENDER = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

ALERTED_STOCKS = {}


def get_stock_prices():
    print("\n[INFO] Aandelenprijzen worden opgehaald...")
    for stock in STOCKS.keys():
        ticker = yf.Ticker(stock)
        data = ticker.history(period="2d")
        if len(data) >= 2:
            prev_close = data["Close"].iloc[-2]
            current_price = data["Close"].iloc[-1]
            STOCKS[stock] = (prev_close, current_price)
            print(f"[INFO] {stock}: Gisteren: ${prev_close:.2f}, Nu: ${current_price:.2f}")


def check_stocks():
    get_stock_prices()
    print("\n[INFO] Veranderingen in prijs berekenen...")

    for stock, (prev_close, current_price) in STOCKS.items():
        percentage_change = ((current_price - prev_close) / prev_close) * 100
        print(f"[INFO] {stock}: {percentage_change:.2f}% verandering")

        if percentage_change <= THRESHOLD:
            if stock not in ALERTED_STOCKS or not ALERTED_STOCKS[stock]:
                print(f"[ALERT] {stock} is meer dan {THRESHOLD}% gedaald! E-mail wordt verzonden...")
                send_email(stock, percentage_change)
                ALERTED_STOCKS[stock] = True
            if stock in ALERTED_STOCKS or ALERTED_STOCKS[stock]:
                print(f"[INFO] Already send email for {stock}")
        else:
            if stock in ALERTED_STOCKS and ALERTED_STOCKS[stock]:
                print(f"[INFO] {stock} is hersteld boven de drempel. Reset melding.")
                ALERTED_STOCKS[stock] = False


def send_email(stock, percentage_change):
    subject = f"ALERT: {stock} is met {percentage_change:.2f}% gedaald!"
    body = f"De prijs van {stock} is met {percentage_change:.2f}% gedaald."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.strato.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"[INFO] Email send for stock: {stock}")
    except Exception as e:
        print(f"[ERROR] Error sending mail: {e}")


def send_startup_email():
    subject = "Stock Monitor started"
    body = "Stock monitor started successfully"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.strato.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("[INFO] Send startup mail.")
    except Exception as e:
        print(f"[ERROR] Error sending startup mail: {e}")


print("[INFO] Stock monitor draait...")
print(os.getenv("EMAIL"))
send_startup_email()
check_stocks()

schedule.every().hour.do(check_stocks)

while True:
    schedule.run_pending()
    time.sleep(60)
