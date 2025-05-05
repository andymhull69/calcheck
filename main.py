from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, time, timedelta
import pytz
import requests
import os
import sys
from flask import Flask, render_template_string, abort

# === CONFIG ===
SERVICE_ACCOUNT_FILE = 'service_account.json'
CALENDAR_ID = 'ef36429c4a9bdee0b32f09b65483c67e5ab7f472423d19c9ece75a139e0de79c@group.calendar.google.com'
TIMEZONE = 'Europe/London'
WORK_START = "09:00"
WORK_END = "17:00"
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = os.getenv('TELEGRAM_USER_ID')
TRIGGER_SECRET = os.getenv('TRIGGER_SECRET')
CALENDLY_URL = 'https://calendly.com/ch-sports-rehab/session'

# === SETUP ===
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/calendar.readonly']
)
service = build('calendar', 'v3', credentials=creds)

# === FLASK SETUP ===
app = Flask(__name__)

# === FUNCTIONS ===
def get_slots_with_status(calendar_id, date, work_start, work_end):
    if not ((date.weekday() == 2 and time(15, 0) <= time.fromisoformat(work_start) <= time(20, 0)) or
            (date.weekday() == 4 and time(8, 0) <= time.fromisoformat(work_start) <= time(19, 0)) or
            (date.weekday() == 5 and time(8, 0) <= time.fromisoformat(work_start) <= time(12, 0))):
        return []
    tz = pytz.timezone(TIMEZONE)
    start_dt = tz.localize(datetime.combine(date, time.fromisoformat(work_start)))
    end_dt = tz.localize(datetime.combine(date, time.fromisoformat(work_end)))

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    all_slots = []
    cursor = start_dt
    while cursor + timedelta(minutes=15) <= end_dt:
        slot_end = cursor + timedelta(minutes=15)
        status = "Free"

        slot_link = CALENDLY_URL if status == "Free" else f"https://calendar.google.com/calendar/u/0/r/day/{cursor.year}/{cursor.month:02}/{cursor.day:02}?pli=1#main_7|{cursor.strftime('%H')}"

        for event in events:
            event_start = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            event_end = datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')))

            if cursor < event_end and slot_end > event_start:
                attendees = event.get('attendees', [])
                client_contact = None
                for attendee in attendees:
                    if attendee.get('email') != CALENDAR_ID:
                        email = attendee.get('email')
                        display_name = attendee.get('displayName') or email
                        client_contact = f"<a href='mailto:{email}'>{display_name}</a>"
                        break
                description = event.get('description', '')
                prep_text = ""
                if "Please share anything that will help prepare me for your appointment.:" in description:
                    parts = description.split("Please share anything that will help prepare me for your appointment.:")
                    if len(parts) > 1:
                        prep_text = parts[1].strip().splitlines()[0].lstrip(':').strip()
                status = f"{client_contact}<br><details><summary>More details</summary><small>{prep_text}</small></details>" if client_contact else "Booked"
                slot_link = f"https://calendar.google.com/calendar/u/0/r/day/{cursor.year}/{cursor.month:02}/{cursor.day:02}?pli=1#main_7|{cursor.strftime('%H')}"
                break

        all_slots.append((cursor.time(), slot_end.time(), status, slot_link))
        cursor = slot_end

    return all_slots

def send_telegram_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_USER_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    response = requests.post(url, data=payload)
    print("Telegram status code:", response.status_code)
    print("Telegram response text:", response.text)
    return response.ok

def generate_weekly_slots():
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    weekly_data = []

    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() not in [2, 4, 5]:
            continue
        slots = get_slots_with_status(CALENDAR_ID, day, WORK_START, WORK_END)
        weekly_data.append({
            'date': day.strftime('%A, %d %b'),
            'slots': [(s[0].strftime('%H:%M'), s[1].strftime('%H:%M'), s[2], s[3]) for s in slots]
        })

    return weekly_data

def generate_text_summary():
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    message = "🗕 Available 1-Hour Free Slots This Week:\n\n"


    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() >= 5:
            continue

        slots = get_slots_with_status(CALENDAR_ID, day, WORK_START, WORK_END)
        free_slots = [s for s in slots if isinstance(s[2], str) and s[2].strip() == "Free"]

        if free_slots:
            message += f"{day.strftime('%A, %d %b')}\n"

            for s in free_slots:
                message += f"  {s[0]} - {s[1]} ✅ → <a href='{CALENDLY_URL}'>Book this</a>\n"



            message += "\n"

    return message


@app.route('/')
def web_output():
    weekly_data = generate_weekly_slots()
    html_template = '''
    <html>
    <head>
        <title>CH Sports Rehab – Availability</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: Arial, sans-serif;
                padding: 1em;
            }
            .header {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 1em;
            }
            .header img {
                height: 80px;
            }
            .week-grid {
                display: flex;
                flex-wrap: wrap;
                gap: 1em;
            }
            .day-column {
                flex: 1 1 calc(33% - 1em);
                border: 1px solid #ccc;
                padding: 0.5em;
                box-sizing: border-box;
                min-width: 250px;
            }
            ul {
                padding-left: 1em;
                margin: 0;
            }
            li {
                margin: 0.3em 0;
                font-size: 1rem;
            }
            @media (max-width: 768px) {
                .day-column {
                    flex: 1 1 100%;
                }
                li {
                    font-size: 0.95rem;
                }
                .header h1 {
                    font-size: 1.2rem;
                }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <img src="https://raw.githubusercontent.com/andymhull69/calcheck/feb25330be251d81bb19a19ee197fc906eb5ab59/CHsportrehab.jpeg" alt="CH Sports Rehab Logo">
            <h1>CH Sports Rehab – Appointment Availability</h1>
        </div>
        <hr>
        <div class="week-grid">
            {% for day in data %}
            <div class="day-column">
                <h3>{{ day.date }}</h3>
                <ul>
                    {% for slot in day.slots %}
                    <li style="color: {{ 'green' if 'Free' in slot[2] else 'red' }};">
                        <a href="{{ slot[3] }}" target="_blank">{{ slot[0] }} - {{ slot[1] }}</a>
                        : {{ slot[2]|safe }}
                    </li>
                    {% endfor %}
                </ul>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    '''
    return render_template_string(html_template, data=weekly_data)

@app.route('/trigger/<secret>')
def trigger_bot(secret):
    if secret != TRIGGER_SECRET:
        abort(403)
    message = generate_text_summary()
    send_telegram_message(message)
    return 'Telegram update sent.'

@app.route('/health')
def health():
    return "OK", 200

# === MAIN ENTRY POINT ===
if __name__ == '__main__':
    # Send summary to Telegram and print to console
    if TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID:
        message = generate_text_summary()
        print(message)
        send_telegram_message(message)

    # Start the web server
    app.run(host='0.0.0.0', port=81)
