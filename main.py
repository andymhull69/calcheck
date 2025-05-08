from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, time, timedelta
import pytz
import requests
import os
import sys
from flask import Flask, render_template_string, abort, request
import gspread

# === CONFIG ===
SERVICE_ACCOUNT_FILE = 'service_account.json'
CALENDAR_ID = 'ef36429c4a9bdee0b32f09b65483c67e5ab7f472423d19c9ece75a139e0de79c@group.calendar.google.com'
TIMEZONE = 'Europe/London'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = os.getenv('TELEGRAM_USER_ID')
TRIGGER_SECRET = os.getenv('TRIGGER_SECRET')
CALENDLY_URL = 'https://calendly.com/ch-sports-rehab/session'

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/calendar.readonly']
)
service = build('calendar', 'v3', credentials=creds)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # protect against overly large posts

# === FUNCTIONS ===
def get_slots_with_status(calendar_id, date):
    day_of_week = date.weekday()
    if day_of_week == 2:  # Wednesday
        work_start = "15:00"
        work_end = "20:00"
    elif day_of_week == 4:  # Friday
        work_start = "08:00"
        work_end = "19:00"
    elif day_of_week == 5:  # Saturday
        work_start = "08:00"
        work_end = "12:00"
    else:
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
        slot_link = CALENDLY_URL

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

    # Group consecutive free slots
    grouped_slots = []
    prev = None
    for slot in all_slots:
        if slot[2] != "Free":
            grouped_slots.append(slot)
            prev = None
            continue
        if prev and prev[2] == "Free" and prev[1] == slot[0]:
            prev = (prev[0], slot[1], "Free", CALENDLY_URL)
            grouped_slots[-1] = prev
        else:
            prev = slot
            grouped_slots.append(slot)

    return grouped_slots

def generate_weekly_slots():
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    weekly_data = []
    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() not in [2, 4, 5]:
            continue
        slots = get_slots_with_status(CALENDAR_ID, day)
        weekly_data.append({
            'date': day.strftime('%A, %d %b'),
            'slots': [(s[0].strftime('%H:%M'), s[1].strftime('%H:%M'), s[2], s[3]) for s in slots]
        })
    return weekly_data

@app.route('/')
def web_output():
    weekly_data = generate_weekly_slots()
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CH Sports Rehab – Bramhall Clinic</title>
        <style>
            body { font-family: Arial; padding: 1px; max-width: 1250px; margin: 0 5px; overflow-x: hidden; }
            .mobile-banner { display: none; }
            h1 { color: #2c3e50; }
            .days-grid {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }
            .day {
                flex: 1 1 calc(31% - 5px);
                min-width: 200px;
                background: #f8f8f8;
                border-radius: 5px;
                padding: 10px;
            }
            .slot { margin-left: 5px; font-weight: bold; }
            .free { color: green; }
            .booked { color: red; }
            img.logo { width: 120px; margin-bottom: 10px; }
            @media (max-width: 700px) {
                .mobile-banner {
                    display: block;
                    background: #ffd; border: 2px dashed red;
                    text-align: center;
                    padding: 10px;
                    font-weight: bold;
                    border: 1px solid #ccc;
                    margin-bottom: 15px;
                }
                .days-grid {
                    flex-direction: column;
                }
                .day {
                    flex: 1 1 100%;
                    width: 100%;
                    margin-bottom: 20px;
                }
            }
        
        li { margin-bottom: 20px; }
        .card {
            border: 1px solid #ccc;
            border-radius: 8px;
            background: #fff;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            padding: 15px;
            margin-bottom: 20px;
        }
        textarea {
            width: 100%;
            font-family: Arial;
        }
        button {
            margin-top: 5px;
            background: #007BFF;
            color: #fff;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background: #0056b3;
        }
        </style>

    </head>
    <body>
        <button onclick="location.reload()" style="position: fixed; top: 60px; right: 10px; z-index: 1001; padding: 5px 10px; background-color: #007BFF; color: white; border: none; border-radius: 4px; cursor: pointer;">Refresh</button>
        <div class="mobile-banner">Mobile version</div>
        <header style="position: sticky; top: 0; background: white; z-index: 1000; padding: 10px 0; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; border-bottom: 1px solid #ccc;">
            <div style="grid-column: 1; display: flex; align-items: center; gap: 10px; padding-left: 25px;">
                <img src="https://raw.githubusercontent.com/andymhull69/calcheck/feb25330be251d81bb19a19ee197fc906eb5ab59/CHsportrehab.jpeg" class="logo" alt="CH Sports Rehab Logo">
            </div>
            <div style="grid-column: 2; text-align: center;">
                <h1 style="margin: 0;">CH Sports Rehab – Bramhall Clinic</h1>
            </div>
            <div style="grid-column: 3; text-align: right; font-size: 0.9em; color: #666; display: flex; align-items: end; justify-content: end; padding: 0 10px 10px 0; height: 100%;">
                Updated: {{ now.strftime('%A %d %b %Y, %H:%M') }}
            </div>
            </div>
            
        </header>
        <div class="days-grid">
        {% for day in data %}
            <div class="day">
                <strong>{{ day.date }}</strong>
                <ul>
                {% for slot in day.slots %}
                    <li class="slot">
                        {{ slot[0] }} - {{ slot[1] }} →
                        {% if slot[2] == 'Free' %}
                            <span class="free">Free</span>
                            <a href="{{ slot[3] }}" target="_blank">Book this</a>
                        {% else %}
                            <span class="booked" style="font-size: 0.85em;">{{ slot[2]|safe }}</span>
                            {% set match = slot[2]|safe %}
                            {% if 'mailto:' in match %}
                                {% set email_start = match.find('mailto:') + 7 %}
                                {% set email_end = match.find("'", email_start) %}
                                {% set email = match[email_start:email_end] %}
                                <a href="/responses?email={{ email }}" target="_blank">View Form Responses</a>
                            {% endif %}
                        {% endif %}
                    </li>
                {% endfor %}
                </ul>
            </div>
        {% endfor %}
        </div>
        
    </body>
    </html>
    '''
    from datetime import datetime as dt
    now = dt.now(pytz.timezone(TIMEZONE))
    return render_template_string(html_template, data=weekly_data, now=now)


def generate_text_summary():
    weekly_data = generate_weekly_slots()
    message = "📅 Available Free Slots This Week:\n"

    for day in weekly_data:
        free_slots = [s for s in day['slots'] if s[2] == 'Free']
        if free_slots:
            message += f"\n{day['date']}\n"

            for s in free_slots:
                message += f"  {s[0]} - {s[1]} ✅ → Book this: {CALENDLY_URL}\n"

    return message or "No free slots available."



def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_USER_ID,
        'text': text
    }
    response = requests.post(url, data=payload)
    print(f"Telegram response: {response.status_code} - {response.text}")

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

from flask import redirect, url_for

@app.route('/update_session', methods=['POST'])
def update_session():
    email = request.form.get('email')
    timestamp = request.form.get('timestamp')
    new_details = request.form.get('session_details', '')

    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    sh = gc.open("New Patient Form  (Responses)")
    ws = sh.sheet1
    records = ws.get_all_records()
    headers = ws.row_values(1)

    # Find matching row
    for idx, row in enumerate(records):
        if (row.get("Email Address", "").strip().lower() == email.strip().lower() and
            row.get("Timestamp") == timestamp):
            cell_row = idx + 2  # account for header
            if "session details" not in headers:
                ws.update_cell(1, len(headers) + 1, "session details")
                headers.append("session details")
            col = headers.index("session details") + 1
            ws.update_cell(cell_row, col, new_details)
            break
    return redirect(url_for('show_responses', email=email))


@app.route('/responses')
def show_responses():
    email = request.args.get('email')
    if not email:
        return "Missing email", 400

    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    sh = gc.open("New Patient Form  (Responses)")
    ws = sh.sheet1
    records = ws.get_all_records()
    filtered = [
        row for row in records
        if row.get("Email Address", "").strip().lower() == email.strip().lower()
    ]
    filtered.sort(key=lambda r: r.get("Timestamp", ""), reverse=True)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>Form Responses for {email}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f0f2f5; color: #333; }}
        h2 {{ margin-bottom: 20px; }}
        ul {{ list-style: none; padding: 0; }}
        details {{ margin-bottom: 15px; border: 1px solid #ccc; border-radius: 6px; background: #fff; padding: 10px; }}
        summary {{ cursor: pointer; font-weight: bold; font-size: 1.05em; }}
        li li {{ margin-left: 15px; padding: 2px 0; }}
    </style>
    </head>
    <body>
    <h2>Form Responses for {email}</h2>
    <ul>
    """

    for row in filtered:
        timestamp = row.get("Timestamp", "Unknown date/time")
        name = row.get("Full name", "Unknown name")
        session_details = row.get("session details", "")
        other_details = "".join(
            f"<li><strong>{k}:</strong> {v}</li>"
            for k, v in row.items() if k not in ['Timestamp', 'Full name']
        )

        html += f"""
        <li class="card">
            <details>
                <summary><strong>{timestamp}</strong> - {name}</summary>
                <ul>{other_details}</ul>
                <form method='POST' action='/update_session' style='margin-top: 10px;'>
                    <input type='hidden' name='email' value='{email}'>
                    <input type='hidden' name='timestamp' value='{timestamp}'>
                    <label><strong>Session Details:</strong></label><br>
                    <textarea name='session_details' rows='2' cols='60'>{session_details}</textarea><br>
                    <button type='submit'>Save</button>
                </form>
            </details>
        </li>
        """

    html += """
    </ul>
    </body>
    </html>
    """
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)

