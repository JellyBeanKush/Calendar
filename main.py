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
ACCENT_GOLD_GLOW = (255, 215, 0, 255) 

CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
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

def create_image(events, now):
    img = Image.new("RGBA", (1920, 1080), BRAND_PURPLE_DARK)
    draw = ImageDraw.Draw(img)
    
    # 1. Background Texture
    midnight_edges = (5, 0, 15, 255)
    max_diag = math.sqrt(960**2 + 540**2)
    for y in range(1080):
        dy = (540 - y)**2
        for x in range(1920):
            if y % 4 == 0:
                dist = math.sqrt((960 - x)**2 + dy)
                ratio = min(dist / max_diag, 1.0)
                r = int(BRAND_PURPLE_LIGHT[0] * (1 - ratio) + midnight_edges[0] * ratio)
                g = int(BRAND_PURPLE_LIGHT[1] * (1 - ratio) + midnight_edges[1] * ratio)
                b = int(BRAND_PURPLE_LIGHT[2] * (1 - ratio) + midnight_edges[2] * ratio)
                draw.point((x, y), fill=(r, g, b, 230))
    
    # 2. SYMMETRY ENGINE: CALCULATE EXPANDED BOXES
    # We want the margin to match the original left-side look (approx 100px)
    GLOBAL_MARGIN = 100 
    
    # Calculate box_w to fill width: (1920 - (2 * margin)) / 7
    box_w = (1920 - (2 * GLOBAL_MARGIN)) // 7
    
    # Get current month rows
    month_cal = calendar.monthcalendar(now.year, now.month)
    num_rows = len(month_cal)
    
    # Calculate box_h to fill height: (1080 - (2 * margin)) / num_rows
    box_h = (1080 - (2 * GLOBAL_MARGIN)) // num_rows
    
    gap = 18 # Internal padding between neon boxes

    # 3. Fonts
    title_f = ImageFont.truetype("ariblk.ttf", 150) 
    num_f = ImageFont.truetype("arial.ttf", 36) 
    ev_f = ImageFont.truetype("arial.ttf", 24)

    event_map = {d: [] for d in range(1, 32)}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        event_map[int(start_str[8:10])].append(e)

    # 4. Render Grid
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            coords = [
                GLOBAL_MARGIN + c * box_w, 
                GLOBAL_MARGIN + r * box_h, 
                GLOBAL_MARGIN + c * box_w + box_w - gap, 
                GLOBAL_MARGIN + r * box_h + box_h - gap
            ]
            
            # Draw Today with Gold Accent, others with Purple
            is_today = (day == now.day)
            color = ACCENT_GOLD_GLOW if is_today else NEON_PURPLE_GLOW
            bg_fill = (50, 30, 10, 220) if is_today else (15, 5, 25, 200)
            
            draw_heavy_neon_bloom(draw, coords, color, intensity=18 if is_today else 10)
            draw.rounded_rectangle(coords, radius=15, fill=bg_fill)
            draw.text((coords[0] + 20, coords[1] + 15), str(day), font=num_f, fill=(255, 255, 255, 255 if is_today else 180))

            # Center-aligned event text
            curr_y = coords[1] + 75
            for ev in event_map.get(day, []):
                t_str = format_time(ev['start'].get('dateTime'))
                line = f"{t_str} | {ev['summary']}" if t_str else ev['summary']
                for chunk in wrap_text(line, ev_f, box_w - 50):
                    if curr_y + 26 > coords[3]: break
                    draw.text((coords[0] + (box_w - gap)//2, curr_y), chunk, font=ev_f, fill=(255, 255, 255), anchor="mm")
                    curr_y += 32

    # 5. DYNAMIC TITLE POSITIONING
    # We place the title exactly in the vertical middle of the top negative space margin.
    title_text = now.strftime("%B %Y").upper()
    title_center_y = GLOBAL_MARGIN // 2
    draw.text((960, title_center_y), title_text, font=title_f, fill=ACCENT_GOLD_GLOW, anchor="mm")

    img.convert("RGB").save("out.png")

def post_to_discord():
    if not WEBHOOK_URL: return
    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID and str(MESSAGE_ID).lower() != 'none' else None
    with open("out.png", "rb") as f:
        files = {"file": ("calendar.png", f, "image/png")}
        if clean_id: requests.patch(f"{WEBHOOK_URL}/messages/{clean_id}", data={"payload_json": json.dumps(payload)}, files=files)
        else: requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)

if __name__ == "__main__":
    t = get_local_now()
    create_image(get_events(t), t)
    post_to_discord()
