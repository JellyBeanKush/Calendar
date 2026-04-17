import os, json, datetime, requests, calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- BRAND & CONFIG ---
BRAND_PURPLE_DARK = (15, 5, 30, 255)
NEON_PURPLE = (180, 50, 255, 255)
ACCENT_GOLD = (255, 215, 0, 255) 

# Calendar Settings
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"
calendar.setfirstweekday(calendar.SUNDAY) #

# GitHub Secret Loading
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")

def get_events():
    """Fetches Google Calendar events for the current month."""
    if not CREDS_JSON:
        print("ERROR: GOOGLE_CREDS_JSON missing!")
        return []
    
    creds = service_account.Credentials.from_service_account_info(json.loads(CREDS_JSON))
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0).isoformat() + 'Z'
    _, last_day = calendar.monthrange(now.year, now.month)
    end = now.replace(day=last_day, hour=23, minute=59, second=59).isoformat() + 'Z'
    
    res = service.events().list(
        calendarId=CALENDAR_ID, 
        timeMin=start, 
        timeMax=end, 
        singleEvents=True, 
        orderBy='startTime'
    ).execute()
    return res.get('items', [])

def draw_neon_bloom(draw, coords, color, intensity=12):
    """Creates a feathered light-bleed effect for a true neon glow."""
    for i in range(intensity, 0, -1):
        # Quadratic falloff for softer edges
        alpha = int(150 * (1 / (i ** 1.3)))
        glow_color = (*color[:3], alpha)
        draw.rounded_rectangle(
            [coords[0]-i, coords[1]-i, coords[2]+i, coords[3]+i],
            radius=15, outline=glow_color, width=i
        )
    # Bright inner core
    draw.rounded_rectangle(coords, radius=15, outline=(255, 255, 255, 255), width=2)
    draw.rounded_rectangle(coords, radius=15, outline=(*color[:3], 255), width=4)

def find_best_title_spot(month_cal):
    """Scans the Sunday-start grid for large empty spaces."""
    row0 = month_cal[0]
    trailing_blanks = sum(1 for d in row0 if d == 0)
    
    last_row = month_cal[-1]
    leading_blanks = sum(1 for d in last_row if d == 0)

    # If first week has space (e.g. Mon-Tue are empty)
    if trailing_blanks >= 3:
        return 0, 7 - trailing_blanks
    # If last week has space (e.g. Thu-Sat are empty)
    if leading_blanks >= 3:
        return len(month_cal)-1, 0
    
    return 0, 2 # Fallback to top center-ish

def create_image(events):
    # Base Image creation
    img = Image.new("RGBA", (1920, 1080), BRAND_PURPLE_DARK)
    draw = ImageDraw.Draw(img)
    
    # Load Fonts
    font_bold = "arialbd.ttf"
    font_reg = "arial.ttf"
    title_f = ImageFont.truetype(font_bold, 80)
    day_f = ImageFont.truetype(font_reg, 35)
    num_f = ImageFont.truetype(font_reg, 32) # Smaller numbers
    ev_f = ImageFont.truetype(font_reg, 20)

    now = datetime.datetime.now()
    month_cal = calendar.monthcalendar(now.year, now.month)
    
    # 1. Dynamic Title Placement
    grid_x, grid_y = 80, 280
    box_w, box_h = 245, 150
    tw_idx, td_idx = find_best_title_spot(month_cal)
    
    # Calculate capsule position based on empty grid spot
    cx = grid_x + td_idx * box_w + (box_w * 1.5 if td_idx == 0 else box_w // 2)
    cy = grid_y + tw_idx * box_h + box_h // 2
    t_box = [cx - 300, cy - 60, cx + 300, cy + 60]
    
    draw_neon_bloom(draw, t_box, ACCENT_GOLD, intensity=15)
    draw.text((cx, cy - 5), now.strftime("%B %Y").upper(), font=title_f, fill=ACCENT_GOLD, anchor="mm")

    # 2. Weekday Headers (Sunday Start)
    weekdays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for i, d in enumerate(weekdays):
        draw.text((grid_x + i*box_w + box_w//2, 240), d, font=day_f, fill=ACCENT_GOLD, anchor="mm")

    # 3. Map Events to Days
    event_map = {d: [] for d in range(1, 32)}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        d_val = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')).day
        event_map[d_val].append(e)

    # 4. Draw the Calendar Grid
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue # Skip empty days
            
            x1, y1 = grid_x + c * box_w, grid_y + r * box_h
            x2, y2 = x1 + box_w - 18, y1 + box_h - 18
            
            if day == now.day:
                # Today's cell: Accent Gold bloom
                draw_neon_bloom(draw, [x1, y1, x2, y2], ACCENT_GOLD, intensity=10)
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(40, 25, 60, 255))
            else:
                # Regular cell: Neon Purple border
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(10, 5, 20, 255), outline=NEON_PURPLE, width=3)
            
            # Day Number
            draw.text((x1 + 15, y1 + 10), str(day), font=num_f, fill=(255, 255, 255, 180))

            # Event Text
            curr_ev_y = y1 + 55
            for ev in event_map.get(day, [])[:4]: # Max 4 per box
                txt = f"• {ev['summary'][:22]}"
                draw.text((x1 + 15, curr_ev_y), txt, font=ev_f, fill=(255, 255, 255))
                curr_ev_y += 24

    img.convert("RGB").save("out.png")

def post_to_discord():
    """Patches the existing message or posts a new one if missing."""
    if not WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL missing!")
        return
    
    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID and str(MESSAGE_ID).lower() != 'none' else None

    try:
        with open("out.png", "rb") as f:
            files = {"file": ("calendar.png", f, "image/png")}
            if clean_id:
                url = f"{WEBHOOK_URL}/messages/{clean_id}"
                r = requests.patch(url, data={"payload_json": json.dumps(payload)}, files=files)
                if r.status_code == 404: # If message was deleted, post fresh
                    f.seek(0)
                    r = requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
            else:
                r = requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
            
            print(f"Discord Status: {r.status_code}")
    except Exception as e:
        print(f"ERROR posting to Discord: {e}")

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
