import os, json, datetime, requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- ENV VARS ---
CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MESSAGE_ID = os.getenv("MESSAGE_ID")
CALENDAR_ID = "YOUR_CALENDAR_ID_HERE" # Put your Calendar ID from Step 1 here!

def get_events():
    creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    # Fetch next 7 days
    res = service.events().list(calendarId=CALENDAR_ID, timeMin=now, maxResults=7, singleEvents=True, orderBy='startTime').execute()
    return res.get('items', [])

def create_image(events):
    img = Image.open("bg.png").convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    # Load Fonts - Using a larger size for 1080p
    font_day = ImageFont.truetype("arial.ttf", 65)
    font_event = ImageFont.truetype("arial.ttf", 45)
    
    # Starting Position (Centered vertically for 7 events)
    x_offset = 200
    y_pos = 250 

    if not events:
        draw.text((x_offset, y_pos), "No upcoming streams scheduled!", font=font_day, fill="white")
    
    for event in events:
        # Time Formatting
        start = event['start'].get('dateTime', event['start'].get('date'))
        dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
        
        day_text = dt.strftime('%A').upper()
        event_text = f"{event['summary']} @ {dt.strftime('%I:%M %p')}"

        # Draw Day (with a slight shadow for readability)
        draw.text((x_offset + 3, y_pos + 3), day_text, font=font_day, fill=(0, 0, 0, 150))
        draw.text((x_offset, y_pos), day_text, font=font_day, fill=(255, 182, 193)) # Light pink/HB brand color

        # Draw Event details
        draw.text((x_offset + 400, y_pos + 15), event_text, font=font_event, fill="white")
        
        y_pos += 110 # Space between rows

    img.save("out.png")

def post_to_discord():
    with open("out.png", "rb") as f:
        payload = {
            "payload_json": json.dumps({
                "embeds": [{
                    "title": "📅│ᴄᴀʟᴇɴᴅᴀʀ",
                    "description": "Weekly schedule for the HoneyBearSquish community!",
                    "image": {"url": "attachment://out.png"},
                    "color": 0xFFB6C1 
                }]
            })
        }
        files = {"files[0]": ("out.png", f)}
        
        if MESSAGE_ID and MESSAGE_ID != "None":
            requests.patch(f"{WEBHOOK_URL}/messages/{MESSAGE_ID}", data=payload, files=files)
        else:
            r = requests.post(f"{WEBHOOK_URL}?wait=true", data=payload, files=files)
            print(f"FIRST RUN SUCCESS! Save this Message ID in your GitHub Secrets: {r.json()['id']}")

if __name__ == "__main__":
    try:
        events = get_events()
        create_image(events)
        post_to_discord()
    except Exception as e:
        print(f"Error occurred: {e}")
