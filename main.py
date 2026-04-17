import os, json, datetime, requests, calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- CONFIG ---
# Hardcoded as requested
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

# These come from your GitHub Secrets
CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")

def get_events():
    creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
    service = build('calendar', 'v3', credentials=creds)
    
    # Get the start and end of the current month
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
    # Load background (1920x1080)
    base = Image.open("bg.png").convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    
    # Fonts - Ensure arial.ttf is in your repo root!
    font_title = ImageFont.truetype("arial.ttf", 70)
    font_date = ImageFont.truetype("arial.ttf", 32)
    font_event = ImageFont.truetype("arial.ttf", 20)
    font_days_label = ImageFont.truetype("arial.ttf", 35)

    # Date Logic
    now = datetime.datetime.now()
    cal = calendar.monthcalendar(now.year, now.month)
    month_name = now.strftime("%B %Y").upper()

    # Draw Month Title (Centered at the top)
    draw_ov.text((1920//2, 80), month_name, font=font_title, fill=(255, 182, 193), anchor="mm")

    # Grid Settings
    margin_x, margin_y = 160, 200
    cell_w, cell_h = 230, 140
    padding = 12

    # Draw Weekday Labels
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for i, day in enumerate(days):
        draw_ov.text((margin_x + i*cell_w + cell_w//2, margin_y - 50), day, font=font_days_label, fill="white", anchor="mm")

    # Map events to days
    event_map = {}
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        day = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).day
        event_map.setdefault(day, []).append(e['summary'])

    # Build the Grid
    for r, week in enumerate(cal):
        for c, day in enumerate(week):
            if day == 0: continue 

            x1 = margin_x + c * cell_w
            y1 = margin_y + r * cell_h
            x2, y2 = x1 + cell_w - padding, y1 + cell_h - padding

            # Box Styling (Slightly transparent dark purple/gray)
            box_fill = (20, 20, 30, 160) # 160 transparency looks good on the hex bg
            border_color = (255, 255, 255, 60)
            
            if day == now.day:
                box_fill = (255, 182, 193, 100) # Soft pink highlight for "today"
                border_color = (255, 182, 193, 200)

            draw_ov.rectangle([x1, y1, x2, y2], fill=box_fill, outline=border_color, width=2)
            
            # Date Number
            draw_ov.text((x1 + 15, y1 + 10), str(day), font=font_date, fill=(255, 255, 255, 200))

            # Events
            if day in event_map:
                ev_y = y1 + 55
                for ev_title in event_map[day][:3]: # Limits to 3 events per day
                    short_title = (ev_title[:20] + '..') if len(ev_title) > 20 else ev_title
                    draw_ov.text((x1 + 15, ev_y), f"• {short_title}", font=font_event, fill="white")
                    ev_y += 25

    # Composite layers
    combined = Image.alpha_composite(base, overlay)
    combined.convert("RGB").save("out.png")

def post_to_discord():
    with open("out.png", "rb") as f:
        payload = {
            "payload_json": json.dumps({
                "embeds": [{
                    "title": "📅│ᴄᴀʟᴇɴᴅᴀʀ",
                    "description": f"Schedule for {datetime.datetime.now().strftime('%B')}",
                    "image": {"url": "attachment://out.png"},
                    "color": 0xFFB6C1
                }]
            })
        }
        files = {"files[0]": ("out.png", f)}
        
        # Determine if we Patch or Post
        if MESSAGE_ID and str(MESSAGE_ID).lower() != "none":
            url = f"{WEBHOOK_URL}/messages/{MESSAGE_ID}"
            r = requests.patch(url, data=payload, files=files)
        else:
            url = f"{WEBHOOK_URL}?wait=true"
            r = requests.post(url, data=payload, files=files)
            if r.status_code == 200:
                print(f"NEW MESSAGE ID (Save to Secrets!): {r.json().get('id')}")
        
        print(f"Status: {r.status_code}")

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
