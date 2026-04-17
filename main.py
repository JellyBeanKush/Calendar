import os, json, datetime, requests, calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- BRAND CONFIG ---
# HoneyBear Squish Colors
BRAND_PURPLE = (20, 5, 40)
NEON_PURPLE = (160, 32, 240)
ACCENT_GOLD = (255, 215, 0)
CYAN_GLOW = (0, 255, 255) # Added as a secondary neon highlight

# GitHub Secrets
CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

def get_events():
    creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0).isoformat() + 'Z'
    _, last_day = calendar.monthrange(now.year, now.month)
    end = now.replace(day=last_day, hour=23, minute=59, second=59).isoformat() + 'Z'
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=start, timeMax=end, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def draw_neon_rect(draw, coords, color, intensity=5):
    """Draws a rounded rectangle with a neon bloom effect."""
    for i in range(intensity, 0, -1):
        alpha = int(255 * (1 / (i * 2)))
        glow_color = (*color, alpha)
        draw.rounded_rectangle(
            [coords[0]-i, coords[1]-i, coords[2]+i, coords[3]+i],
            radius=15, outline=glow_color, width=i
        )
    draw.rounded_rectangle(coords, radius=15, outline=(*color, 255), width=2)

def create_image(events):
    # 1. Base Canvas & Neon Grid Background
    img = Image.new("RGBA", (1920, 1080), BRAND_PURPLE)
    draw = ImageDraw.Draw(img)
    
    # Draw a subtle "Scanline" / Hex pattern effect
    for y in range(0, 1080, 40):
        draw.line([(0, y), (1920, y)], fill=(255, 255, 255, 5), width=1)

    # 2. Setup Fonts
    font_path = "arial.ttf"
    title_font = ImageFont.truetype(font_path, 110)
    day_font = ImageFont.truetype(font_path, 50)
    num_font = ImageFont.truetype(font_path, 42)
    ev_size = 22

    now = datetime.datetime.now()
    month_label = now.strftime("%B %Y").upper()

    # 3. Separated Neon Title Box
    # Centered at the top with a Golden Yellow glow
    t_box = [400, 50, 1520, 200]
    draw_neon_rect(draw, t_box, ACCENT_GOLD)
    draw.text((1920//2, 125), month_label, font=title_font, fill=ACCENT_GOLD, anchor="mm")

    # 4. Grid Config
    margin_x, margin_y = 70, 340
    col_w, row_h = 250, 140
    pad = 15

    # Neon Weekday Labels
    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for i, day in enumerate(weekdays):
        draw.text((margin_x + i*col_w + col_w//2, margin_y - 60), day, font=day_font, fill=ACCENT_GOLD, anchor="mm")

    # Map Events
    event_map = {}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        event_map.setdefault(dt.day, []).append(e)

    # 5. Drawing Day Cells
    month_cal = calendar.monthcalendar(now.year, now.month)
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            
            x1, y1 = margin_x + c * col_w, margin_y + r * row_h
            x2, y2 = x1 + col_w - pad, y1 + row_h - pad
            
            # Box Style - Fully Opaque base
            # Purple borders for general days, Golden for "Today"
            box_fill = (10, 5, 25, 255)
            glow_color = NEON_PURPLE
            
            if day == now.day:
                box_fill = (30, 15, 50, 255)
                glow_color = ACCENT_GOLD

            draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=box_fill)
            draw_neon_rect(draw, [x1, y1, x2, y2], glow_color, intensity=4)
            
            # Date Number
            draw.text((x1 + 15, y1 + 10), str(day), font=num_font, fill=(255, 255, 255, 220))

            # Events (Time - Name)
            if day in event_map:
                curr_y = y1 + 65
                for ev in event_map[day][:3]:
                    s_iso = ev['start'].get('dateTime', ev['start'].get('date'))
                    ev_dt = datetime.datetime.fromisoformat(s_iso.replace('Z', '+00:00'))
                    t_str = ev_dt.strftime('%I%p').lower().lstrip('0')
                    full_txt = f"• {t_str} - {ev['summary']}"
                    
                    # Scaling
                    f_ev = ImageFont.truetype(font_path, ev_size)
                    while f_ev.getlength(full_txt) > (col_w - 40) and f_ev.size > 12:
                        f_ev = ImageFont.truetype(font_path, f_ev.size - 1)
                    
                    draw.text((x1 + 15, curr_y), full_txt, font=f_ev, fill=(255, 255, 255))
                    curr_y += 24

    img.convert("RGB").save("out.png")

def post_to_discord():
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID and str(MESSAGE_ID).lower() != 'none' else None
    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    with open("out.png", "rb") as f:
        files = {"file": ("calendar.png", f, "image/png")}
        if clean_id:
            requests.patch(f"{WEBHOOK_URL}/messages/{clean_id}", data={"payload_json": json.dumps(payload)}, files=files)
        else:
            requests.post(f"{WEBHOOK_URL}", data={"payload_json": json.dumps(payload)}, files=files)

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
