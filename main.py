import caldav
from caldav.elements import dav, cdav
from datetime import datetime, timedelta
import os

# === CONFIG ===
ICLOUD_USERNAME = os.getenv('ICLOUD_USERNAME')  # your Apple ID email
ICLOUD_PASSWORD = os.getenv('ICLOUD_APP_PASSWORD')  # your app-specific password

# === CONNECT TO ICLOUD CALDAV ===
try:
    client = caldav.DAVClient(
        url='https://caldav.icloud.com/',
        username=ICLOUD_USERNAME,
        password=ICLOUD_PASSWORD
    )

    principal = client.principal()
    calendars = principal.calendars()

    print("✅ Connected to iCloud CalDAV")
    print(f"Found {len(calendars)} calendar(s):")
    for calendar in calendars:
        if calendar.name.lower() == 'bramhallclinic':
            print("✅ Using calendar:", calendar.name)
            selected_calendar = calendar
            break
    else:
        print("❌ Calendar 'bramhallclinic' not found.")
        selected_calendar = None

except Exception as e:
    print("❌ Failed to connect to iCloud CalDAV:", e)

# === GET FREE TIME SLOTS ===
from datetime import time as dtime

def get_working_hours_for_day(day):
    if day.weekday() == 2:  # Wednesday
        return dtime(15, 0), dtime(20, 0)
    elif day.weekday() == 4:  # Friday
        return dtime(8, 0), dtime(19, 0)
    elif day.weekday() == 5:  # Saturday
        return dtime(8, 0), dtime(12, 0)
    return None, None

def get_free_slots(calendar, day):
    start_time, end_time = get_working_hours_for_day(day)
    if not start_time:
        return []

    start_dt = datetime.combine(day, start_time)
    end_dt = datetime.combine(day, end_time)

    results = calendar.date_search(start=start_dt, end=end_dt)
    busy_times = [(e.vobject_instance.vevent.dtstart.value, e.vobject_instance.vevent.dtend.value) for e in results]

    free_slots = []
    cursor = start_dt
    while cursor + timedelta(minutes=15) <= end_dt:
        slot_end = cursor + timedelta(minutes=15)
        conflict = False
        for bstart, bend in busy_times:
            if cursor < bend and slot_end > bstart:
                conflict = True
                break
        if not conflict:
            free_slots.append((cursor.time(), slot_end.time()))
        cursor = slot_end

    return free_slots

# === FLASK WEB OUTPUT ===
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def show_slots():
    if not selected_calendar:
        return "Calendar not found."

    today = datetime.now().date()
    week_slots = []

    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() in [2, 4, 5]:
            slots = get_free_slots(selected_calendar, day)
            slot_data = [(s[0].strftime('%H:%M'), s[1].strftime('%H:%M')) for s in slots]
            week_slots.append({
                'date': day.strftime('%A, %d %b'),
                'slots': slot_data
            })

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>CH Sports Rehab – Bramhall Schedule</title>
        <style>
            body { font-family: Arial; padding: 20px; max-width: 900px; margin: auto; }
            h1 { color: #2c3e50; }
            .day { margin-top: 30px; }
            .slot { margin-left: 15px; color: green; font-weight: bold; }
            img.logo { width: 200px; margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <img src="https://raw.githubusercontent.com/andymhull69/calcheck/feb25330be251d81bb19a19ee197fc906eb5ab59/CHsportrehab.jpeg" class="logo" alt="CH Sports Rehab Logo">
        <h1>CH Sports Rehab – Bramhall Schedule</h1>
        {% for day in week_slots %}
            <div class="day">
                <strong>{{ day.date }}</strong>
                {% if day.slots %}
                    <ul>
                        {% for s in day.slots %}
                            <li class="slot">{{ s[0] }} - {{ s[1] }} ✅</li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <p>No free slots</p>
                {% endif %}
            </div>
        {% endfor %}
        <br><p><a href="https://calendly.com/ch-sports-rehab/session" target="_blank">Book via Calendly</a></p>
    </body>
    </html>'''
    '''
    return render_template_string(html, week_slots=week_slots)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
