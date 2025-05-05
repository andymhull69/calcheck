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
        print("-", calendar.name)

except Exception as e:
    print("❌ Failed to connect to iCloud CalDAV:", e)
