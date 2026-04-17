import os, json, datetime, requests, calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- BRAND CONFIG ---
# HoneyBearSquish official palette
BRAND_PURPLE_DARK = (15, 5, 30, 255)  # The dark canvas
BRAND_PURPLE_LIGHT = (40, 15, 60, 255) # The vignette center
NEON_PURPLE = (180, 50, 255, 255)
ACCENT_GOLD = (255, 215, 0, 255) 

# GitHub Secret Loading
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

# Set Sunday Start
calendar.setfirstweekday(calendar.SUNDAY) #

def get_events():
    creds = service_account.Credentials.from_service_account_info(json.loads(CREDS_JSON))
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0).isoformat() + 'Z'
    _, last_day = calendar.monthrange(now.year, now.month)
    end = now.replace(day=last_day, hour=23, minute=59, second=59).isoformat() + 'Z'
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=start, timeMax=end, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def draw_heavy_neon(draw, coords, color, intensity=16):
    """ Procedural multi-pass bloom effect."""
    for i in range(intensity, 0, -1):
        alpha = int(180 * (1 / (i ** 1.3)))
        glow_color = (*color[:3], alpha)
        draw.rounded_rectangle(
            [coords[0]-i, coords[1]-i, coords[2]+i, coords[3]+i],
            radius=15, outline=glow_color, width=i
        )
    # Bright center 'tube'
    draw.rounded_rectangle(coords, radius=15, outline=(255, 255, 255, 255), width=2)
    draw.rounded_rectangle(coords, radius=15, outline=(*color[:3], 255), width=4)

def draw_textured_gradient(draw, rect, color_center, color_edges):
    """Draws a procedural vignette and scanline background."""
    x0, y0, x1, y1 = rect
    width = x1 - x0
    height = y1 - y0
    
    # Precompute the diagonal distance of the canvas for faster calculation
    import math
    max_dist = math.sqrt((width/2)**2 + (height/2)**2)
    
    for y in range(height):
        for x in range(width):
            # 1. Vignette Gradient (Radial from center)
            dist = math.sqrt((width/2 - x)**2 + (height/2 - y)**2)
            ratio = min(dist / max_dist, 1.0)
            
            # Linear Interpolation
            r = int(color_center[0] * (1 - ratio) + color_edges[0] * ratio)
            g = int(color_center[1] * (1 - ratio) + color_edges[1] * ratio)
            b = int(color_center[2] * (1 - ratio) + color_edges[2] * ratio)
            
            # 2. Subtle Scanline Texture (every 4 pixels)
            a = 255
            if y % 4 == 0:
                a = 235 # Make every 4th line slightly dimmer

            draw.point((x + x0, y + y0), fill=(r, g, b, a))

def create_image(events):
    img = Image.new("RGBA", (1920, 1080), BRAND_PURPLE_DARK)
    draw = ImageDraw.Draw(img)
    
    # 1. Non-flat Textured Background Layer
    midnight_edges = (5, 0, 15, 255)
    draw_textured_gradient(draw, (0, 0, 1920, 1080), BRAND_PURPLE_LIGHT, midnight_edges)

    # 2. Setup Fonts (Updated to specific load Arial Black)
    # Verify these filenames match your uploaded files
    font_bold = "arialbd.ttf"
    font_blk = "ariblk.ttf" # NEW: Arial Black specifically
    font_reg = "arial.ttf"

    title_font = ImageFont.truetype(font_blk, 90) # Punchy Arial Black
    day_font = ImageFont.truetype(font_reg, 35)   
    num_font = ImageFont.truetype(font_reg, 32) # Smaller numbers, clear numbers
    ev_size = 20

    now = datetime.datetime.now()
    month_label = now.strftime("%B %Y").upper()

    # Smaller Month Title (Centered)
    t_box = [650, 40, 1270, 160]
    draw_heavy_neon(draw, t_box, ACCENT_GOLD, intensity=10)
    draw.text((1920//2, 105), month_label, font=title_font, fill=ACCENT_GOLD, anchor="mm")

    # Taller Grid Config
    margin_x, margin_y = 80, 240
    col_w, row_h = 245, 170 
    pad = 18

    # Sunday-Start labels
    weekdays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for i, day in enumerate(weekdays):
        draw.text((margin_x + i*col_w + col_w//2, margin_y - 40), day, font=day_font, fill=ACCENT_GOLD, anchor="mm")

    event_map = {}
    for e in events:
        start_str = e['start'].get('dateTime', e['start'].get('date'))
        # stream locally: eval based on Pacific Time
        dt_start = datetime.datetime.fromisoformat(start_str.replace('Z', '-07:00'))
        event_map.setdefault(dt_start.day, []).append(e)

    month_cal = calendar.monthcalendar(now.year, now.month)
    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            
            x1, y1 = margin_x + c * col_w, margin_y + r * row_h
            x2, y2 = x1 + col_w - pad, y1 + row_h - pad
            
            # Pure Neon Cells: outline only, heavy bloom, no background
            current_fill = (0, 0, 0, 0) # Removed flat flat fill
            current_outline = NEON_PURPLE
            
            if day == now.day:
                # Today highlight: Radiating golden bloom
                current_outline = ACCENT_GOLD
                draw_heavy_neon(draw, [x1, y1, x2, y2], ACCENT_GOLD, intensity=10)
            else:
                # Regular days: outline only
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, outline=current_outline, width=3)
            
            # Date Number
            draw.text((x1 + 15, y1 + 10), str(day), font=num_f, fill=(255, 255, 255, 230))

            if day in event_map:
                curr_y = y1 + 60
                for ev in event_map[day][:4]: 
                    s_iso = ev['start'].get('dateTime', ev['start'].get('date'))
                    ev_dt = datetime.datetime.fromisoformat(s_iso.replace('Z', '-07:00'))
                    t_str = ev_dt.strftime('%I%p').lower().lstrip('0')
                    full_txt = f"• {t_str} - {ev['summary']}"
                    
                    f_ev = ImageFont.truetype(font_reg, ev_size)
                    while f_ev.getlength(full_txt) > (col_w - 45) and f_ev.size > 12:
                        f_ev = ImageFont.truetype(font_reg, f_ev.size - 1)
                    
                    draw.text((x1 + 15, curr_y), full_txt, font=f_ev, fill=(255, 255, 255))
                    curr_y += 24

    img.convert("RGB").save("out.png")

def post_to_discord():
    if not WEBHOOK_URL: return
    payload = {"embeds": [{"image": {"url": "attachment://calendar.png"}, "color": 16761095}]}
    with open("out.png", "rb") as f:
        files = {"file": ("calendar.png", f, "image/png")}
        if MESSAGE_ID and MESSAGE_ID.lower() != 'none':
            requests.patch(f"{WEBHOOK_URL}/messages/{MESSAGE_ID}", data={"payload_json": json.dumps(payload)}, files=files)
        else:
            requests.post(f"{WEBHOOK_URL}?wait=true", data={"payload_json": json.dumps(payload)}, files=files)

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
