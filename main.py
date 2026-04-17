import os
import json
import datetime
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# --- ENV VARS ---
# These must be set in your GitHub Repository Secrets
try:
    CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    # Message ID will be None on the very first run
    MESSAGE_ID = os.getenv("MESSAGE_ID")
except Exception as e:
    print(f"ERROR: Missing environment variables. {e}")
    exit(1)

# Your Google Calendar ID (from Calendar Settings)
CALENDAR_ID = "YOUR_CALENDAR_ID_HERE" 

def get_events():
    print("Connecting to Google Calendar API...")
    try:
        creds = service_account.Credentials.from_service_account_info(CREDS_JSON)
        service = build('calendar', 'v3', credentials=creds)
        
        # Define time range: Now to 7 days from now
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        week_later = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat() + 'Z'
        
        print(f"Fetching events from {now} to {week_later}...")
        res = service.events().list(
            calendarId=CALENDAR_ID, 
            timeMin=now, 
            timeMax=week_later,
            maxResults=10, 
            singleEvents=True, 
            orderBy='startTime'
        ).execute()
        
        events = res.get('items', [])
        print(f"Successfully retrieved {len(events)} events.")
        return events
    except Exception as e:
        print(f"CRITICAL ERROR fetching from Google: {e}")
        return []

def create_image(events):
    print("Generating visual schedule image (1920x1080)...")
    try:
        # Load your background and font
        img = Image.open("bg.png").convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        # Ensure arial.ttf is in your GitHub repo root
        font_day = ImageFont.truetype("arial.ttf", 60)
        font_event = ImageFont.truetype("arial.ttf", 45)
        
        x_offset = 150
        y_pos = 280 

        if not events:
            draw.text((x_offset, y_pos), "No streams scheduled for this week!", font=font_day, fill="white")
        
        for event in events:
            # Handle Start Time
            start = event['start'].get('dateTime', event['start'].get('date'))
            dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
            
            day_text = dt.strftime('%A').upper()
            event_text = f"{event['summary']} @ {dt.strftime('%I:%M %p')}"

            # Draw Day Name (Light Pink / HB Brand style)
            draw.text((x_offset, y_pos), day_text, font=font_day, fill=(255, 182, 193))
            
            # Draw Event details (White)
            draw.text((x_offset + 450, y_pos + 12), event_text, font=font_event, fill="white")
            
            y_pos += 100 # Vertical spacing between events

        img.save("out.png")
        print("Image saved successfully as out.png")
    except Exception as e:
        print(f"ERROR generating image: {e}")

def post_to_discord():
    print("Preparing to send to Discord...")
    if not os.path.exists("out.png"):
        print("ERROR: out.png was never created. Aborting.")
        return

    with open("out.png", "rb") as f:
        # Prepare the Discord Embed
        payload = {
            "payload_json": json.dumps({
                "embeds": [{
                    "title": "📅│ᴄᴀʟᴇɴᴅᴀʀ",
                    "description": "Weekly community schedule update!",
                    "image": {"url": "attachment://out.png"},
                    "color": 0xFFB6C1 # Pink
                }]
            })
        }
        files = {"files[0]": ("out.png", f)}
        
        # Decide if we are updating or posting new
        if MESSAGE_ID and MESSAGE_ID.strip() != "" and MESSAGE_ID != "None":
            print(f"Updating existing message: {MESSAGE_ID}")
            url = f"{WEBHOOK_URL}/messages/{MESSAGE_ID}"
            r = requests.patch(url, data=payload, files=files)
        else:
            print("No Message ID found. Sending as a NEW message...")
            url = f"{WEBHOOK_URL}?wait=true"
            r = requests.post(url, data=payload, files=files)
            
        print(f"Discord Response Code: {r.status_code}")
        
        if r.status_code in [200, 204]:
            print("Success! Discord has been updated.")
            if not MESSAGE_ID or MESSAGE_ID == "None":
                new_id = r.json().get('id')
                print(f"*** ACTION REQUIRED ***\nSave this Message ID in your GitHub Secrets as 'MESSAGE_ID': {new_id}")
        else:
            print(f"FAILED to update Discord. Response: {r.text}")

if __name__ == "__main__":
    current_events = get_events()
    create_image(current_events)
    post_to_discord()
