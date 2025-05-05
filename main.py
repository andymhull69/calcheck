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

# === DISPLAY FOR TEST ===
if selected_calendar:
    today = datetime.now().date()
    print("\n🗓 Free 15-minute slots this week:")

    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() in [2, 4, 5]:
            slots = get_free_slots(selected_calendar, day)
            print(f"{day.strftime('%A, %d %b')}")
            if slots:
                for s in slots:
                    print(f"  {s[0]} - {s[1]} ✅")
            else:
                print("  No free slots")
