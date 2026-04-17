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
calendar.setfirstweekday(calendar.SUNDAY) # Sunday Start

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

def wrap_text(text, font, max_width):
    """Calculates word-wrapping to keep text within box horizontal bounds."""
    lines = []
    words = text.split()
    while words:
        line = ''
        while words and ImageFont.ImageFont.getlength(font, line + words[0]) <= max_width:
            line += (words.pop(0) + ' ')
        if not line: # Single word is wider than max_width
            line = words.pop(0)
        lines.append(line.strip())
    return lines

def draw_neon_bloom(draw, coords, color, intensity=12):
    """Creates a feathered light-bleed effect for a high-quality neon look."""
    for i in range(intensity, 0, -1):
        # Soften the glow with quadratic falloff
        alpha = int(150 * (1 / (i ** 1.3)))
        glow_color = (*color[:3], alpha)
        draw.rounded_rectangle(
            [coords[0]-i, coords[1]-i, coords[2]+i, coords[3]+i],
            radius=15, outline=glow_color, width=i
        )
    # Bright inner core tube
    draw.rounded_rectangle(coords, radius=15, outline=(255, 255, 255, 255), width=2)
    draw.rounded_rectangle(coords, radius=15, outline=(*color[:3], 255), width=4)

def create_image(events):
    # Canvas setup
    img = Image.new("RGBA", (1920, 1080), BRAND_PURPLE_DARK)
    draw = ImageDraw.Draw(img)
    
    # Font Logic
    font_bold = "arialbd.ttf"
    font_reg = "arial.ttf"
    title_f = ImageFont.truetype(font_bold, 90) # Bolded header
    day_f = ImageFont.truetype(font_reg, 35)
    num_f = ImageFont.truetype(font_reg, 32) # Smaller numbers
    ev_f = ImageFont.truetype(font_reg, 22)

    now = datetime.datetime.now()
    month_cal = calendar.monthcalendar(now.year, now.month)
    
    # 1. Grid & Vertical Fill
    grid_x, grid_y = 80, 180
    box_w, box_h, gap = 245, 172, 18
    max_txt_w = box_w - 40 # Margin for horizontal safety

    # 2. Dynamic Title Placement (Locked to Bottom)
    last_row = month_cal[-1]
    leading_blanks = sum(1 for d in last_row if d == 0)
    
    if leading_blanks >= 2:
        # Calculate gap in the last row for the HoneyBear gold capsule
        title_start_x = grid_x + (7 - leading_blanks) * box_w
        title_start_y = grid_y + (len(month_cal) - 1) * box_h
        t_rect = [title_start_x, title_start_y, title_start_x + (leading_blanks * box_w) - gap, title_start_y + box_h - gap]
        
        draw_neon_bloom(draw, t_rect, ACCENT_GOLD, intensity=15)
        draw.text((title_start_x + (leading_blanks * box_w)//2 - 10, title_start_y + box_h//2 - 5), 
                  now.strftime("%B %Y").upper(), font=title_f, fill=ACCENT_GOLD, anchor="mm")
    else:
        # Fallback to Top if the last week is full
        draw_neon_bloom(draw, [650, 30, 1270, 140], ACCENT_GOLD, intensity=15)
        draw.text((960, 85), now.strftime("%B %Y").upper(), font=title_f, fill=ACCENT_GOLD, anchor="mm")

    # 3. Weekday Labels (Sunday Start)
    weekdays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for i, d in enumerate(weekdays):
        draw.text((grid_x + i*box_w + box_w//2, 145), d, font=day_f, fill=ACCENT_GOLD, anchor="mm")

    # 4. Map Events to Days
    event_map = {d: [] for d in range(1, 32)}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        d_val = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')).day
        event_map[d_val].append(e)

    # 5. Draw the Calendar Grid
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            
            x1, y1 = grid_x + c * box_w, grid_y + r * box_h
            x2, y2 = x1 + box_w - gap, y1 + box_h - gap
            
            if day == now.day:
                # Today highlight
                draw_neon_bloom(draw, [x1, y1, x2, y2], ACCENT_GOLD, intensity=10)
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(40, 25, 60, 255))
            else:
                # Standard Neon Purple border
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(10, 5, 20, 255), outline=NEON_PURPLE, width=3)
            
            # Draw smaller day number
            draw.text((x1 + 15, y1 + 10), str(day), font=num_f, fill=(255, 255, 255, 160))

            # 6. Render Wrapped Events
            curr_y = y1 + 55
            for ev in event_map.get(day, []):
                summary = f"• {ev['summary']}"
                wrapped_lines = wrap_text(summary, ev_f, max_txt_w)
                
                for line in wrapped_lines:
                    # Final vertical boundary check
                    if curr_y + 25 > y2: break
                    draw.text((x1 + 15, curr_y), line, font=ev_f, fill=(255, 255, 255))
                    curr_y += 26
                
                if curr_y + 25 > y2: break

    img.convert("RGB").save("out.png")

def post_to_discord():
    """Updates the HoneyBearSquish Discord message."""
    if not WEBHOOK_URL: return
    
    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID and str(MESSAGE_ID).lower() != 'none' else None

    with open("out.png", "rb") as f:
        files = {"file": ("calendar.png", f, "image/png")}
        if clean_id:
            url = f"{WEBHOOK_URL}/messages/{clean_id}"
            r = requests.patch(url, data={"payload_json": json.dumps(payload)}, files=files)
            if r.status_code == 404: # Re-post if original was deleted
                f.seek(0)
                requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)
        else:
            requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
