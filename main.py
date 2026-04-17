import os
import json
import datetime
import requests
import calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- CONFIG ---
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

# GitHub Secrets
CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")

def get_events():
    creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
    service = build('calendar', 'v3', credentials=creds)
    
    now = datetime.datetime.utcnow()
    start_month = now.replace(day=1, hour=0, minute=0, second=0).isoformat() + 'Z'
    _, last_day = calendar.monthrange(now.year, now.month)
    end_month = now.replace(day=last_day, hour=23, minute=59, second=59).isoformat() + 'Z'
    
    res = service.events().list(
        calendarId=CALENDAR_ID, 
        timeMin=start_month, 
        timeMax=end_month, 
        singleEvents=True, 
        orderBy='startTime'
    ).execute()
    return res.get('items', [])

def create_image(events):
    base = Image.open("bg.png").convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    
    # Professional, Large Fonts
    font_title = ImageFont.truetype("arial.ttf", 95)
    font_days = ImageFont.truetype("arial.ttf", 50)
    font_date_num = ImageFont.truetype("arial.ttf", 45)
    font_event = ImageFont.truetype("arial.ttf", 24)

    now = datetime.datetime.now()
    month_cal = calendar.monthcalendar(now.year, now.month)
    month_name = now.strftime("%B %Y").upper()

    # Draw Title
    draw_ov.text((1920//2, 100), month_name, font=font_title, fill=(255, 182, 193), anchor="mm")

    # Maximized Grid Settings
    margin_x, margin_y = 50, 240
    cell_w, cell_h = 265, 160
    padding = 8

    # Day Labels
    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for i, day in enumerate(weekdays):
        draw_ov.text((margin_x + i*cell_w + cell_w//2, margin_y - 60), day, font=font_days, fill="white", anchor="mm")

    # Event Mapping
    event_map = {}
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
        event_map.setdefault(dt.day, []).append(e)

    # Drawing the Grid
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue

            x1, y1 = margin_x + c * cell_w, margin_y + r * cell_h
            x2, y2 = x1 + cell_w - padding, y1 + cell_h - padding

            # High Opacity Boxes (240/255) to ensure readability over hex bg
            box_color = (15, 15, 25, 240) 
            border_color = (255, 255, 255, 80)
            
            if day == now.day:
                box_color = (255, 182, 193, 180) # Brand Pink Highlight
                border_color = (255, 255, 255, 200)

            draw_ov.rectangle([x1, y1, x2, y2], fill=box_color, outline=border_color, width=3)
            draw_ov.text((x1 + 15, y1 + 10), str(day), font=font_date_num, fill=(255, 255, 255, 230))

            if day in event_map:
                ev_y = y1 + 70
                for ev in event_map[day][:3]:
                    # Time + Name Formatting
                    start_iso = ev['start'].get('dateTime', ev['start'].get('date'))
                    dt_ev = datetime.datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    time_str = dt_ev.strftime('%I%p').lower().lstrip('0')
                    
                    full_text = f"• {time_str} - {ev['summary']}"
                    # Truncate if too long for the wider boxes
                    display_text = (full_text[:28] + '..') if len(full_text) > 28 else full_text
                    
                    draw_ov.text((x1 + 15, ev_y), display_text, font=font_event, fill="white")
                    ev_y += 30

    combined = Image.alpha_composite(base, overlay)
    combined.convert("RGB").save("out.png")

def post_to_discord():
    with open("out.png", "rb") as f:
        # CLEAN EMBED: No title, no description. Just the image.
        payload = {
            "payload_json": json.dumps({
                "embeds": [{
                    "image": {"url": "attachment://out.png"},
                    "color": 0xFFB6C1
                }]
            })
        }
        files = {"files[0]": ("out.png", f)}
        
        if MESSAGE_ID and str(MESSAGE_ID).lower() != "none":
            url = f"{WEBHOOK_URL}/messages/{MESSAGE_ID}"
            requests.patch(url, data=payload, files=files)
        else:
            url = f"{WEBHOOK_URL}?wait=true"
            r = requests.post(url, data=payload, files=files)
            if r.status_code == 200:
                print(f"NEW MESSAGE ID: {r.json().get('id')}")

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
