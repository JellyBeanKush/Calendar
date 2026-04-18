import os, json, datetime, requests, calendar
import math
try:
    import zoneinfo
except ImportError:
    pass 
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- BRAND CONFIG ---
BRAND_PURPLE_DARK = (10, 2, 20, 255)
BRAND_PURPLE_LIGHT = (40, 15, 60, 255)
NEON_PURPLE_GLOW = (180, 50, 255, 255)
ACCENT_GOLD_GLOW = (218, 165, 32, 255) 

# Paths for GitHub Actions
SAVE_PATH = "out.png"
ID_FILE = "message_id.txt"

CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

calendar.setfirstweekday(calendar.SUNDAY) 

def get_local_now():
    try: return datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    except: return datetime.datetime.now()

def get_events(now):
    creds = service_account.Credentials.from_service_account_info(json.loads(CREDS_JSON))
    service = build('calendar', 'v3', credentials=creds)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    start = utc_now.replace(day=1, hour=0, minute=0, second=0).isoformat().replace('+00:00', 'Z')
    _, last_day = calendar.monthrange(now.year, now.month)
    end = utc_now.replace(day=last_day, hour=23, minute=59, second=59).isoformat().replace('+00:00', 'Z')
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=start, timeMax=end, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def format_time(time_str):
    if not time_str or 'T' not in time_str: return ""
    dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    dt_local = dt.astimezone(datetime.timezone(datetime.timedelta(hours=-7)))
    return dt_local.strftime("%I%p").lstrip('0').lower()

def wrap_text(text, font, max_width):
    lines = []
    words = text.split()
    while words:
        line = ''
        while words:
            test_line = line + words[0] + ' '
            try: w = font.getlength(test_line)
            except: w = font.getsize(test_line)[0]
            if w <= max_width: line += words.pop(0) + ' '
            else: break
        if not line: line = words.pop(0)
        lines.append(line.strip())
    return lines

def draw_heavy_neon_bloom(draw, coords, color, intensity=16):
    for i in range(intensity, 0, -1):
        alpha = int(180 * (1 / (i ** 1.3)))
        glow_color = (*color[:3], alpha)
        draw.rounded_rectangle([coords[0]-i, coords[1]-i, coords[2]+i, coords[3]+i], radius=15, outline=glow_color, width=i)
    draw.rounded_rectangle(coords, radius=15, outline=(255, 255, 255, 255), width=2)
    draw.rounded_rectangle(coords, radius=15, outline=(*color[:3], 255), width=4)

def get_month_title_position(month_cal, box_w, box_h, margin_x, margin_y):
    top_blanks = [i for i, day in enumerate(month_cal[0]) if day == 0]
    bot_blanks = [i for i, day in enumerate(month_cal[-1]) if day == 0]
    if len(top_blanks) >= len(bot_blanks) and len(top_blanks) > 0:
        x_start, x_end = margin_x + (top_blanks[0] * box_w), margin_x + (top_blanks[-1] * box_w) + box_w
        y_start, y_end = margin_y, margin_y + box_h
    else:
        x_start, x_end = margin_x + (bot_blanks[0] * box_w), margin_x + (bot_blanks[-1] * box_w) + box_w
        y_start, y_end = margin_y + (len(month_cal)-1) * box_h, margin_y + (len(month_cal)-1) * box_h + box_h
    return (x_start + x_end) // 2, (y_start + y_end) // 2

def draw_centered_events(draw, coords, events, font_path, box_w, gap, is_grey=False):
    base_font_size = 25
    all_lines = []
    for ev in events:
        t_str = format_time(ev['start'].get('dateTime'))
        summary = ev.get('summary', '').upper() if is_grey else ev.get('summary', '')
        line = f"{t_str} | {summary}" if t_str else summary
        all_lines.append(line)

    current_size = base_font_size
    def get_layout(f_size):
        f = ImageFont.truetype(font_path, f_size)
        lh = int(f_size * 1.35)
        wrapped = []
        for l in all_lines:
            wrapped.extend(wrap_text(l, f, box_w - 40))
        return wrapped, lh

    chunks, lh = get_layout(current_size)
    available_h = (coords[3] - coords[1]) - 75 
    
    while len(chunks) * lh > available_h and current_size > 12:
        current_size -= 1
        chunks, lh = get_layout(current_size)

    if not chunks: return

    final_font = ImageFont.truetype(font_path, current_size)
    total_text_h = len(chunks) * lh
    start_y = coords[1] + 70 + (available_h - total_text_h) // 2
    
    curr_y = start_y
    for chunk in chunks:
        tw = final_font.getlength(chunk)
        bg_alpha = 60 if is_grey else 100
        text_alpha = 100 if is_grey else 255
        draw.rounded_rectangle([coords[0]+(box_w-gap)//2 - tw//2 - 8, curr_y - (lh//2) + 2, 
                                coords[0]+(box_w-gap)//2 + tw//2 + 8, curr_y + (lh//2) - 2], 
                                radius=6, fill=(0, 0, 0, bg_alpha))
        draw.text((coords[0] + (box_w - gap)//2, curr_y), chunk, font=final_font, fill=(255, 255, 255, text_alpha), anchor="mm")
        curr_y += lh

def create_image(events, now):
    img = Image.new("RGBA", (1920, 1080), BRAND_PURPLE_DARK)
    draw = ImageDraw.Draw(img)
    
    midnight_edges = (5, 0, 15, 255)
    max_diag = math.sqrt(960**2 + 540**2)
    for y in range(0, 1080, 4):
        dy = (540 - y)**2
        for x in range(1920):
            dist = math.sqrt((960 - x)**2 + dy)
            ratio = min(dist / max_diag, 1.0)
            r = int(BRAND_PURPLE_LIGHT[0] * (1 - ratio) + midnight_edges[0] * ratio)
            g = int(BRAND_PURPLE_LIGHT[1] * (1 - ratio) + midnight_edges[1] * ratio)
            b = int(BRAND_PURPLE_LIGHT[2] * (1 - ratio) + midnight_edges[2] * ratio)
            draw.point((x, y), fill=(r, g, b, 230))
    
    GLOBAL_MARGIN = 25 
    box_w = (1920 - (2 * GLOBAL_MARGIN)) // 7
    month_cal = calendar.monthcalendar(now.year, now.month)
    num_rows = len(month_cal)
    box_h = (1080 - (2 * GLOBAL_MARGIN)) // num_rows
    gap = 12 

    title_f = ImageFont.truetype("ariblk.ttf", 185) 
    num_f = ImageFont.truetype("arial.ttf", 32) 
    font_path = "arial.ttf"

    event_map = {d: [] for d in range(1, 32)}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        event_map[int(start_str[8:10])].append(e)

    today_data = None
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            coords = [GLOBAL_MARGIN + c * box_w, GLOBAL_MARGIN + r * box_h, 
                      GLOBAL_MARGIN + c * box_w + box_w - gap, GLOBAL_MARGIN + r * box_h + box_h - gap]
            
            day_events = event_map.get(day, [])
            is_no_stream = any("NO STREAM" in ev.get('summary', '').upper() for ev in day_events)
            is_weekend = (c == 0 or c == 6)
            has_events = len(day_events) > 0

            if day == now.day:
                today_data = coords
                continue

            if is_no_stream or (is_weekend and not has_events):
                draw.rounded_rectangle(coords, radius=15, outline=(100, 100, 120, 50), width=2, fill=(20, 20, 30, 150))
                draw.text((coords[0] + 18, coords[1] + 18), str(day), font=num_f, fill=(255, 255, 255, 60))
                if has_events:
                    draw_centered_events(draw, coords, day_events, font_path, box_w, gap, is_grey=True)
            else:
                draw_heavy_neon_bloom(draw, coords, NEON_PURPLE_GLOW, intensity=10)
                draw.rounded_rectangle(coords, radius=15, fill=(15, 5, 25, 200))
                draw.text((coords[0] + 18, coords[1] + 18), str(day), font=num_f, fill=(255, 255, 255, 130))
                draw_centered_events(draw, coords, day_events, font_path, box_w, gap)

    if today_data:
        draw_heavy_neon_bloom(draw, today_data, ACCENT_GOLD_GLOW, intensity=22)
        draw.rounded_rectangle(today_data, radius=15, fill=(50, 30, 10, 230))
        draw.text((today_data[0] + 18, today_data[1] + 18), str(now.day), font=num_f, fill=(255, 255, 255, 255))
        draw_centered_events(draw, today_data, event_map.get(now.day, []), font_path, box_w, gap)

    title_text = now.strftime("%B").upper()
    tx, ty = get_month_title_position(month_cal, box_w, box_h, GLOBAL_MARGIN, GLOBAL_MARGIN)
    draw.text((tx, ty), title_text, font=title_f, fill=ACCENT_GOLD_GLOW, anchor="mm")

    img.convert("RGB").save(SAVE_PATH)

def post_to_discord():
    if not WEBHOOK_URL: return
    
    # Try to read the old ID from our tracking file
    old_id = None
    if os.path.exists(ID_FILE):
        with open(ID_FILE, "r") as f:
            old_id = f.read().strip()

    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    
    with open(SAVE_PATH, "rb") as f:
        files = {"file": ("calendar.png", f, "image/png")}
        
        # 1. Attempt SILENT EDIT if we have an ID
        if old_id and old_id.lower() != 'none':
            try:
                res = requests.patch(
                    f"{WEBHOOK_URL}/messages/{old_id}?wait=true", 
                    data={"payload_json": json.dumps(payload)}, 
                    files=files
                )
                if res.status_code == 200:
                    print(f"SILENT UPDATE SUCCESSFUL for message: {old_id}")
                    return # Mission accomplished
                else:
                    print(f"Silent update failed (Status {res.status_code}). Reposting...")
            except Exception as e:
                print(f"Error during patch: {e}")

        # 2. FALLBACK: POST NEW if edit failed or no ID exists
        res = requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)
        if res.status_code in [200, 201, 204]:
            new_id = res.json().get('id')
            with open(ID_FILE, "w") as f:
                f.write(str(new_id))
            print(f"CREATED NEW BASE MESSAGE: {new_id}")

if __name__ == "__main__":
    t = get_local_now()
    create_image(get_events(t), t)
    post_to_discord()
