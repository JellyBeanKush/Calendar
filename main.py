import os, json, datetime, requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- ENV VARS ---
CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
CALENDAR_ID = "YOUR_CALENDAR_ID_HERE" # Hardcode or use another secret

def get_events():
    creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=now, maxResults=7, singleEvents=True).execute()
    return res.get('items', [])

def create_image(events):
    img = Image.open("bg.png").convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("Arial.ttf", 50) # Make sure Arial.ttf is in your repo!
    
    y = 300
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
        text = f"{dt.strftime('%a')}: {event['summary']}"
        draw.text((200, y), text, font=font, fill="white")
        y += 100
    img.save("out.png")

def post_to_discord():
    with open("out.png", "rb") as f:
        payload = {"payload_json": json.dumps({"embeds": [{"title": "📅│ᴄᴀʟᴇɴᴅᴀʀ", "image": {"url": "attachment://out.png"}}]})}
        files = {"files[0]": ("out.png", f)}
        if MESSAGE_ID:
            requests.patch(f"{WEBHOOK_URL}/messages/{MESSAGE_ID}", data=payload, files=files)
        else:
            r = requests.post(f"{WEBHOOK_URL}?wait=true", data=payload, files=files)
            print(f"FIRST RUN ID: {r.json()['id']}")

if __name__ == "__main__":
    events = get_events()
    create_image(events)
    post_to_discord()
