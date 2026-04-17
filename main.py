import os, json, datetime, requests, calendar
try:
    import zoneinfo
except ImportError:
    pass 
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- THE PURE NEON PALETTE --- 
BRAND_PURPLE_DARK = (15, 5, 30, 255)
NEON_PURPLE_GLOW = (180, 50, 255, 255)
ACCENT_GOLD_GLOW = (255, 215, 0, 255) 

# GitHub Secret Loading
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

calendar.setfirstweekday(calendar.SUNDAY) 

def get_local_now():
    try:
        return datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    except Exception:
        return datetime.datetime.now()

def get_events(now):
    creds = service_account.Credentials.from_service_account_info(json.loads(CREDS_JSON))
    service = build('calendar', 'v3', credentials=creds)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    start = utc_now.replace(day=1, hour=0, minute=0, second=0).isoformat().replace('+00:00', 'Z')
    _, last_day = calendar.monthrange(now.year, now.month)
    end = utc_now.replace(day=last_day, hour=23, minute=59, second=59).isoformat().replace('+00:00', 'Z')
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=start, timeMax=end, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def wrap_text(text, font, max_width):
    lines = []
    words = text.split()
    while words:
        line = ''
        while words:
            test_line = line + words[0] + ' '
            try:
                w = font.getlength(test_line)
            except AttributeError:
                w = font.getsize(test_line)[0]
            if w <= max_width:
                line += words.pop(0) + ' '
            else:
                break
        if not line: line = words.pop(0)
        lines.append(line.strip())
    return lines

def draw_heavy_neon_bloom(draw, coords, color, intensity=16):
    """Heavy multi-pass bloom for maximum neon saturation."""
    for i in range(intensity, 0, -1):
        alpha = int(180 * (1 / (i ** 1.3)))
        glow_color = (*color[:3], alpha)
        draw.rounded_rectangle([coords[0]-i, coords[1]-i, coords[2]+i, coords[3]+i], radius=15, outline=glow_color, width=i)
    draw.rounded_rectangle(coords, radius=15, outline=(255, 255, 255, 255), width=2)
    draw.rounded_rectangle(coords, radius=15, outline=(*color[:3], 255), width=4)

def find_best_title_center(month_cal):
    """Finds empty grid space for the floating title."""
    last_row = month_cal[-1]
    leading_blanks = sum(1 for d in last_row if d == 0)
    if leading_blanks >= 2:
        return len(month_cal)-1, 7 - leading_blanks, leading_blanks
    row0 = month_cal[0]
    trailing_blanks = sum(1 for d in row0 if d == 0)
    if trailing_blanks >= 2:
        return 0, 0, trailing_blanks
    return -1, -1, 0 # No space fallback

def create_image(events, now):
    img = Image.new("RGBA", (1920, 1080), BRAND_PURPLE_DARK)
    draw = ImageDraw.Draw(img)
    
    # Fonts
    font_bold = "arialbd.ttf"
    font_reg = "arial.ttf"
    title_f = ImageFont.truetype(font_bold, 140) # Even larger title
    day_f = ImageFont.truetype(font_reg, 35)
    num_f = ImageFont.truetype(font_reg, 32) 
    ev_f = ImageFont.truetype(font_reg, 22)

    month_cal = calendar.monthcalendar(now.year, now.month)
    
    # Grid Config: grid_y moved up (80), box_h increased (190) for vertical fill
    grid_x, grid_y = 80, 80
    box_w, box_h, gap = 245, 190, 18
    max_txt_w = box_w - 40 

    # 1. Weekday Headers
    weekdays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for i, d in enumerate(weekdays):
        draw.text((grid_x + i*box_w + box_w//2, 45), d, font=day_f, fill=ACCENT_GOLD_GLOW, anchor="mm")

    # 2. Map Events
    event_map = {d: [] for d in range(1, 32)}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        try:
            d_val = int(start_str[8:10]) # Direct string slice for speed
            event_map[d_val].append(e)
        except: pass

    # 3. Draw Grid
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            
            x1, y1 = grid_x + c * box_w, grid_y + r * box_h
            x2, y2 = x1 + box_w - gap, y1 + box_h - gap
            
            if day == now.day:
                draw_heavy_neon_bloom(draw, [x1, y1, x2, y2], ACCENT_GOLD_GLOW, intensity=14)
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(45, 25, 65, 255))
            else:
                draw_heavy_neon_bloom(draw, [x1, y1, x2, y2], NEON_PURPLE_GLOW, intensity=10)
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(15, 5, 25, 255))
            
            draw.text((x1 + 15, y1 + 10), str(day), font=num_f, fill=(255, 255, 255, 180))

            curr_y = y1 + 55
            for ev in event_map.get(day, []):
                wrapped = wrap_text(f"• {ev['summary']}", ev_f, max_txt_w)
                for line in wrapped:
                    if curr_y + 25 > y2: break
                    draw.text((x1 + 15, curr_y), line, font=ev_f, fill=(255, 255, 255))
                    curr_y += 26
                if curr_y + 25 > y2: break

    # 4. Floating Neon Title (Month Only, No Border)
    tw_idx, td_start, gap_len = find_best_title_center(month_cal)
    month_text = now.strftime("%B").upper()
    
    if tw_idx != -1:
        # Center in the blank grid space
        tx = grid_x + (td_start * box_w) + (gap_len * box_w // 2) - (gap // 2)
        ty = grid_y + (tw_idx * box_h) + (box_h // 2) - (gap // 2)
        # Draw soft glow behind text for "neon" feel
        draw.text((tx, ty), month_text, font=title_f, fill=ACCENT_GOLD_GLOW, anchor="mm")
    else:
        # Fallback if no grid space: float at very bottom center
        draw.text((960, 1020), month_text, font=title_f, fill=ACCENT_GOLD_GLOW, anchor="mm")

    img.convert("RGB").save("out.png")

def post_to_discord():
    if not WEBHOOK_URL: return
    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID and str(MESSAGE_ID).lower() != 'none' else None
    with open("out.png", "rb") as f:
        files = {"file": ("calendar.png", f, "image/png")}
        if clean_id:
            requests.patch(f"{WEBHOOK_URL}/messages/{clean_id}", data={"payload_json": json.dumps(payload)}, files=files)
        else:
            requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)

if __name__ == "__main__":
    t = get_local_now()
    create_image(get_events(t), t)
    post_to_discord()
