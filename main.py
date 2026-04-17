import os, json, datetime, requests, calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- BRAND CONFIG ---
BRAND_PURPLE_DARK = (15, 5, 30, 255)
BRAND_PURPLE_LIGHT = (40, 15, 60, 255)
NEON_PURPLE = (180, 50, 255, 255)
ACCENT_GOLD = (255, 215, 0, 255) 

# GitHub Secrets
CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

# Set Calendar to Sunday Start
calendar.setfirstweekday(calendar.SUNDAY)

def get_events():
    creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0).isoformat() + 'Z'
    _, last_day = calendar.monthrange(now.year, now.month)
    end = now.replace(day=last_day, hour=23, minute=59, second=59).isoformat() + 'Z'
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=start, timeMax=end, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def draw_heavy_neon(draw, coords, color, intensity=15):
    """Enhanced Bloom: Layered transparency to simulate light bleed."""
    for i in range(intensity, 0, -1):
        # Soften the glow as it spreads further out
        alpha = int(140 * (1 / (i ** 1.3)))
        glow_color = (*color[:3], alpha)
        draw.rounded_rectangle(
            [coords[0]-i, coords[1]-i, coords[2]+i, coords[3]+i],
            radius=15, outline=glow_color, width=i
        )
    # Brightest inner 'tube'
    draw.rounded_rectangle(coords, radius=15, outline=(255, 255, 255, 255), width=2)
    draw.rounded_rectangle(coords, radius=15, outline=(*color[:3], 255), width=4)

def find_dynamic_title_spot(month_cal):
    """Calculates best empty spot in the Sunday-start grid."""
    # Top row check (First week)
    row0 = month_cal[0]
    trailing_blanks = 0
    for day in reversed(row0):
        if day == 0: trailing_blanks += 1
        else: break
            
    # Bottom row check (Last week)
    last_row = month_cal[-1]
    leading_blanks = 0
    for day in last_row:
        if day == 0: leading_blanks += 1
        else: break

    # Logic to prioritize the gap for the HoneyBear title
    if trailing_blanks >= 3:
        return 0, 7 - trailing_blanks
    elif leading_blanks >= 3:
        return len(month_cal)-1, 0
    return 0, 2 # Default fallback

def draw_gradient(draw, rect, color_top, color_bottom):
    x0, y0, x1, y1 = rect
    h = y1 - y0
    for y in range(h):
        ratio = y / h
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        draw.line([(x0, y0 + y), (x1, y0 + y)], fill=(r, g, b, 255), width=1)

def create_image(events):
    img = Image.new("RGBA", (1920, 1080))
    draw = ImageDraw.Draw(img)
    
    # 1. Background Gradient
    royal_blue_dark = (5, 5, 40, 255)
    draw_gradient(draw, (0, 0, 1920, 1080), BRAND_PURPLE_DARK, royal_blue_dark)

    # 2. Setup Fonts
    font_path = "arial.ttf"
    title_font = ImageFont.truetype(font_path, 85) 
    day_font = ImageFont.truetype(font_path, 35)   
    num_font = ImageFont.truetype(font_path, 35) # Smaller day numbers
    ev_size = 20

    now = datetime.datetime.now()
    month_label = now.strftime("%B %Y").upper()
    month_cal = calendar.monthcalendar(now.year, now.month)

    # 3. Dynamic Title Capsule
    grid_start_y, grid_start_x = 280, 80
    box_w, box_h, gap = 245, 150, 18
    tr_week_idx, tr_day_idx = find_dynamic_title_spot(month_cal)

    t_box_cx = grid_start_x + tr_day_idx * box_w + (box_w * 1.5 if tr_day_idx == 0 else box_w // 2)
    t_box_cy = grid_start_y + tr_week_idx * box_h + box_h // 2
    t_box = [t_box_cx - 300, t_box_cy - 60, t_box_cx + 300, t_box_cy + 60]
    
    draw_heavy_neon(draw, t_box, ACCENT_GOLD, intensity=12)
    draw.text((t_box_cx, t_box_cy - 5), month_label, font=title_font, fill=ACCENT_GOLD, anchor="mm")

    # 4. Sunday-Start Weekday Labels
    weekdays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for i, day in enumerate(weekdays):
        draw.text((grid_start_x + i*box_w + box_w//2, 240), day, font=day_font, fill=ACCENT_GOLD, anchor="mm")

    # Event Mapping
    event_map = {}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        event_map.setdefault(dt.day, []).append(e)

    # 5. Drawing Day Cells
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            
            x1, y1 = grid_start_x + c * box_w, grid_start_y + r * box_h
            x2, y2 = x1 + box_w - gap, y1 + box_h - gap
            
            if day == now.day:
                draw_heavy_neon(draw, [x1, y1, x2, y2], ACCENT_GOLD, intensity=10)
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(40, 25, 60, 255))
            else:
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill=(10, 5, 20, 255), outline=NEON_PURPLE, width=2)
            
            draw.text((x1 + 15, y1 + 10), str(day), font=num_font, fill=(255, 255, 255, 200))

            if day in event_map:
                curr_y = y1 + 60
                for ev in event_map[day][:4]: 
                    s_iso = ev['start'].get('dateTime', ev['start'].get('date'))
                    ev_dt = datetime.datetime.fromisoformat(s_iso.replace('Z', '+00:00'))
                    t_str = ev_dt.strftime('%I%p').lower().lstrip('0')
                    full_txt = f"• {t_str} - {ev['summary']}"
                    draw.text((x1 + 15, curr_y), full_txt, font=ImageFont.truetype(font_path, ev_size), fill=(255, 255, 255))
                    curr_y += 24

    img.convert("RGB").save("out.png")

def post_to_discord():
    if not WEBHOOK_URL: return
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID and str(MESSAGE_ID).lower() != 'none' else None
    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    try:
        with open("out.png", "rb") as f:
            files = {"file": ("calendar.png", f, "image/png")}
            if clean_id:
                url = f"{WEBHOOK_URL}/messages/{clean_id}"
                r = requests.patch(url, data={"payload_json": json.dumps(payload)}, files=files)
                if r.status_code == 404:
                    f.seek(0)
                    r = requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
            else:
                r = requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
            print(f"Status: {r.status_code} | ID: {r.json().get('id', 'N/A')}")
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
