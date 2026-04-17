import os, json, datetime, requests, calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- ENV VARS ---
CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
CALENDAR_ID = "YOUR_CALENDAR_ID_HERE" 

def get_events():
    creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
    service = build('calendar', 'v3', credentials=creds)
    
    # Get the start and end of the current month
    now = datetime.datetime.utcnow()
    start_month = now.replace(day=1, hour=0, minute=0, second=0).isoformat() + 'Z'
    _, last_day = calendar.monthrange(now.year, now.month)
    end_month = now.replace(day=last_day, hour=23, minute=59, second=59).isoformat() + 'Z'
    
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=start_month, timeMax=end_month, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def create_image(events):
    base = Image.open("bg.png").convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    
    # Fonts
    font_title = ImageFont.truetype("arial.ttf", 60)
    font_date = ImageFont.truetype("arial.ttf", 30)
    font_event = ImageFont.truetype("arial.ttf", 18)

    # Calendar Logic
    now = datetime.datetime.now()
    cal = calendar.monthcalendar(now.year, now.month)
    month_name = now.strftime("%B %Y").upper()

    # Draw Month Title
    draw_ov.text((1920//2, 80), month_name, font=font_title, fill=(255, 182, 193), anchor="mm")

    # Grid Settings
    margin_x, margin_y = 150, 180
    cell_w, cell_h = 230, 140
    padding = 10

    # Draw Day Labels (MON, TUE, etc)
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for i, day in enumerate(days):
        draw_ov.text((margin_x + i*cell_w + cell_w//2, margin_y - 40), day, font=font_date, fill="white", anchor="mm")

    # Mapping events to days
    event_map = {}
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        day = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).day
        event_map.setdefault(day, []).append(e['summary'])

    # Draw the Grid
    for r, week in enumerate(cal):
        for c, day in enumerate(week):
            x1 = margin_x + c * cell_w
            y1 = margin_y + r * cell_h
            x2, y2 = x1 + cell_w - padding, y1 + cell_h - padding

            if day == 0: continue # Skip empty days in the grid

            # Draw transparent box
            box_color = (40, 40, 40, 180) # Dark gray, 180/255 transparency
            if day == now.day: box_color = (80, 50, 70, 200) # Highlight today
            
            draw_ov.rectangle([x1, y1, x2, y2], fill=box_color, outline=(255, 255, 255, 50))
            
            # Draw Date Number
            draw_ov.text((x1 + 10, y1 + 5), str(day), font=font_date, fill=(255, 255, 255, 150))

            # Draw Events in the box
            if day in event_map:
                ev_y = y1 + 45
                for ev_title in event_map[day][:3]: # Show up to 3 events per box
                    # Truncate long titles
                    display_text = (ev_title[:22] + '..') if len(ev_title) > 22 else ev_title
                    draw_ov.text((x1 + 10, ev_y), f"• {display_text}", font=font_event, fill="white")
                    ev_y += 25

    # Combine background and overlay
    combined = Image.alpha_composite(base, overlay)
    combined.convert("RGB").save("out.png")

def post_to_discord():
    with open("out.png", "rb") as f:
        payload = {"payload_json": json.dumps({"embeds": [{"title": "📅│ᴄᴀʟᴇɴᴅᴀʀ", "image": {"url": "attachment://out.png"}, "color": 0xFFB6C1}]})}
        files = {"files[0]": ("out.png", f)}
        url = f"{WEBHOOK_URL}/messages/{MESSAGE_ID}" if (MESSAGE_ID and MESSAGE_ID != "None") else f"{WEBHOOK_URL}?wait=true"
        method = requests.patch if (MESSAGE_ID and MESSAGE_ID != "None") else requests.post
        r = method(url, data=payload, files=files)
        if not MESSAGE_ID or MESSAGE_ID == "None": print(f"NEW ID: {r.json().get('id')}")

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
