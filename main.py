import os, json, datetime, requests, calendar, time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- CONFIG ---
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

# Brand Colors (HoneyBear Squish)
BRAND_PURPLE = (25, 10, 45)       # Deep base purple
ACCENT_GOLD = (255, 215, 0)      # Golden Yellow accent
BOX_BG = (15, 5, 30, 255)         # Fully opaque dark boxes
HIGHLIGHT_PURPLE = (60, 20, 100, 255) # Today's highlight

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
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=start_month, timeMax=end_month, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def get_font(name, size):
    try:
        return ImageFont.truetype(name, size)
    except:
        return ImageFont.load_default()

def create_image(events):
    # 1. Create Procedural Background (1920x1080)
    base = Image.new("RGBA", (1920, 1080), BRAND_PURPLE)
    draw = ImageDraw.Draw(base)
    
    # Add a subtle "Month-Themed" pattern (Geometric Borders)
    # This creates a golden yellow inner frame that changes slightly based on the month
    border_thickness = 15
    draw.rectangle([20, 20, 1900, 1060], outline=ACCENT_GOLD, width=border_thickness)

    # 2. Setup Fonts
    font_title = get_font("arial.ttf", 90)
    font_days = get_font("arial.ttf", 50)
    font_date_num = get_font("arial.ttf", 45)
    BASE_EVENT_SIZE = 24

    now = datetime.datetime.now()
    month_name = now.strftime("%B %Y").upper()

    # 3. Dedicated Month Title Box
    # Separated into its own high-visibility box at the top
    title_box_y = 60
    title_box_h = 150
    draw.rectangle([100, title_box_y, 1820, title_box_y + title_box_h], fill=(0, 0, 0, 180), outline=ACCENT_GOLD, width=5)
    draw.text((1920//2, title_box_y + (title_box_h // 2)), month_name, font=font_title, fill=ACCENT_GOLD, anchor="mm")

    # 4. Grid Layout
    margin_x, margin_y = 50, 320
    cell_w, cell_h = 260, 140
    padding = 10
    max_text_width = cell_w - 30

    # Weekday Labels
    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for i, day_name in enumerate(weekdays):
        draw.text((margin_x + i*cell_w + cell_w//2, margin_y - 60), day_name, font=font_days, fill=ACCENT_GOLD, anchor="mm")

    # Map Events
    event_map = {}
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
        event_map.setdefault(dt.day, []).append(e)

    # 5. Build Calendar Grid
    month_cal = calendar.monthcalendar(now.year, now.month)
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            
            x1, y1 = margin_x + c * cell_w, margin_y + r * cell_h
            x2, y2 = x1 + cell_w - padding, y1 + cell_h - padding
            
            # Day Box - Now highly opaque
            current_box_color = BOX_BG
            current_border = (255, 255, 255, 60)
            
            if day == now.day:
                current_box_color = HIGHLIGHT_PURPLE
                current_border = ACCENT_GOLD

            draw.rectangle([x1, y1, x2, y2], fill=current_box_color, outline=current_border, width=3)
            
            # Date Number
            draw.text((x1 + 15, y1 + 10), str(day), font=font_date_num, fill=(255, 255, 255, 230))

            # Events
            if day in event_map:
                ev_y = y1 + 65
                for ev in event_map[day][:3]:
                    start_iso = ev['start'].get('dateTime', ev['start'].get('date'))
                    dt_ev = datetime.datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    time_str = dt_ev.strftime('%I%p').lower().lstrip('0')
                    full_text = f"• {time_str} - {ev['summary']}"
                    
                    # Shrink font if text is too long
                    current_size = BASE_EVENT_SIZE
                    current_font = get_font("arial.ttf", current_size)
                    while current_font.getlength(full_text) > max_text_width and current_size > 12:
                        current_size -= 1
                        current_font = get_font("arial.ttf", current_size)
                    
                    draw.text((x1 + 15, ev_y), full_text, font=current_font, fill="white")
                    ev_y += 28

    base.convert("RGB").save("out.png")

def post_to_discord():
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID and str(MESSAGE_ID).lower() != 'none' else None
    payload = {
        "embeds": [{
            "image": {"url": "attachment://calendar.png"},
            "color": 16761095 # Golden Yellow
        }]
    }

    with open("out.png", "rb") as f:
        files = {"file": ("calendar.png", f, "image/png")}
        
        if clean_id:
            url = f"{WEBHOOK_URL}/messages/{clean_id}"
            r = requests.patch(url, data={"payload_json": json.dumps(payload)}, files=files)
            if r.status_code >= 400:
                f.seek(0)
                r = requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
                print(f"NEW MESSAGE ID: {r.json().get('id')}")
        else:
            r = requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
            if r.status_code < 300:
                print(f"NEW MESSAGE ID: {r.json().get('id')}")

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
