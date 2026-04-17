import os, json, datetime, requests, calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- CONFIG ---
CALENDAR_ID = "9ead18f5408c70117b9a32e804a3b4f1178d95f19abbc240e6220674fdf52ea1@group.calendar.google.com"

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

def create_image(events):
    base = Image.open("bg.png").convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    
    font_title = ImageFont.truetype("arial.ttf", 95)
    font_days = ImageFont.truetype("arial.ttf", 50)
    font_date_num = ImageFont.truetype("arial.ttf", 45)
    font_event = ImageFont.truetype("arial.ttf", 24)

    now = datetime.datetime.now()
    month_cal = calendar.monthcalendar(now.year, now.month)
    month_name = now.strftime("%B %Y").upper()

    draw_ov.text((1920//2, 100), month_name, font=font_title, fill=(255, 182, 193), anchor="mm")

    margin_x, margin_y = 50, 240
    cell_w, cell_h = 265, 160
    padding = 8

    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for i, day in enumerate(weekdays):
        draw_ov.text((margin_x + i*cell_w + cell_w//2, margin_y - 60), day, font=font_days, fill="white", anchor="mm")

    event_map = {}
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
        event_map.setdefault(dt.day, []).append(e)

    for r, week in enumerate(month_cal):
        for c, day in enumerate(week):
            if day == 0: continue
            x1, y1 = margin_x + c * cell_w, margin_y + r * cell_h
            x2, y2 = x1 + cell_w - padding, y1 + cell_h - padding
            box_color = (15, 15, 25, 240) 
            border_color = (255, 255, 255, 80)
            if day == now.day:
                box_color = (255, 182, 193, 180)
                border_color = (255, 255, 255, 200)
            draw_ov.rectangle([x1, y1, x2, y2], fill=box_color, outline=border_color, width=3)
            draw_ov.text((x1 + 15, y1 + 10), str(day), font=font_date_num, fill=(255, 255, 255, 230))

            if day in event_map:
                ev_y = y1 + 70
                for ev in event_map[day][:3]:
                    start_iso = ev['start'].get('dateTime', ev['start'].get('date'))
                    dt_ev = datetime.datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    time_str = dt_ev.strftime('%I%p').lower().lstrip('0')
                    full_text = f"• {time_str} - {ev['summary']}"
                    display_text = (full_text[:28] + '..') if len(full_text) > 28 else full_text
                    draw_ov.text((x1 + 15, ev_y), display_text, font=font_event, fill="white")
                    ev_y += 30

    combined = Image.alpha_composite(base, overlay)
    combined.convert("RGB").save("out.png")

def post_to_discord():
    print(f"Current MESSAGE_ID: {MESSAGE_ID}")
    files = {"file": ("out.png", open("out.png", "rb"))}
    
    # We strip spaces just in case the Secret has one
    clean_id = str(MESSAGE_ID).strip() if MESSAGE_ID else None

    if clean_id and clean_id.lower() != "none":
        print(f"Attempting to PATCH message {clean_id}...")
        url = f"{WEBHOOK_URL}/messages/{clean_id}"
        r = requests.patch(url, files=files)
        if r.status_code == 404:
            print("Error: Message ID not found. It might have been deleted. Sending new...")
            r = requests.post(f"{WEBHOOK_URL}?wait=true", files=files)
            print(f"SAVE THIS NEW ID: {r.json().get('id')}")
    else:
        print("No Message ID found. Sending NEW message...")
        url = f"{WEBHOOK_URL}?wait=true"
        r = requests.post(url, files=files)
        if r.status_code == 200:
            print(f"SAVE THIS NEW ID: {r.json().get('id')}")
    
    print(f"Final Status: {r.status_code}")

if __name__ == "__main__":
    create_image(get_events())
    post_to_discord()
