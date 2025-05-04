from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, time, timedelta
import pytz
import requests
import os
import sys
from flask import Flask, render_template_string, abort

# CONFIG
SERVICE_ACCOUNT_FILE = 'service_account.json'
CALENDAR_ID = 'ef36429c4a9bdee0b32f09b65483c67e5ab7f472423d19c9ece75a139e0de79c@group.calendar.google.com'
TIMEZONE = 'Europe/Zurich'
WORK_START = "09:00"
WORK_END = "17:00"
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = os.getenv('TELEGRAM_USER_ID')
TRIGGER_SECRET = os.getenv('TRIGGER_SECRET')
CALENDLY_URL = 'https://calendly.com/ch-sports-rehab/30min'

app = Flask(__name__)

def generate_text_summary():
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    message = "🗕 Available 1-Hour Free Slots This Week:\n\n"
    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        message += f"{day.strftime('%A, %d %b')}\n"
        message += f"  09:00 - 10:00 ✅ → Book: {CALENDLY_URL}\n"
        message += "\n"
    return message

@app.route('/')
def index():
    return "Web output placeholder"

@app.route('/trigger/<secret>')
def trigger(secret):
    if secret != TRIGGER_SECRET:
        abort(403)
    msg = generate_text_summary()
    requests.post(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage', data={
        'chat_id': TELEGRAM_USER_ID,
        'text': msg
    })
    return 'Telegram update sent.'

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
