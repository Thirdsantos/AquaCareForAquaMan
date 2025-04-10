import os
import json
import asyncio
import websockets
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db, messaging
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Firebase setup
firebase_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

if firebase_credentials:
    creds = json.loads(firebase_credentials)
    if not firebase_admin._apps:
        cred = credentials.Certificate(creds)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://aquamans-47d16-default-rtdb.asia-southeast1.firebasedatabase.app/"
        })
        print("✅ Firebase Connected Successfully!")
else:
    print("❌ Error: GOOGLE_APPLICATION_CREDENTIALS_JSON not found.")
    exit()

# Firebase DB references
refPh = db.reference("Notification/PH")
refTemp = db.reference("Notification/Temperature")
refTurb = db.reference("Notification/Turbidity")
ref = db.reference("Sensors")
refNotif = db.reference("Notifications")

@app.route("/")
def index():
    return "AQUACARE THE BRIDGE BETWEEN THE GAPS"

async def handle_websocket(websocket, path):
    await websocket.send(json.dumps({"message": "✅ You're now connected to the WebSocket server"}))

    try:
        async for message in websocket:
            print(f"📩 Received message: {message}")
            try:
                data = json.loads(message)

                if isinstance(data, dict):
                    if "PH" in data and "Temperature" in data and "Turbidity" in data:
                        sensor_data = {
                            "PH": data["PH"],
                            "Temperature": data["Temperature"],
                            "Turbidity": data["Turbidity"]
                        }

                        updateToDb(sensor_data)
                        await checkThreshold(sensor_data, websocket)

                        await websocket.send(json.dumps({"PH": sensor_data["PH"]}))
                        await websocket.send(json.dumps({"Temperature": sensor_data["Temperature"]}))
                        await websocket.send(json.dumps({"Turbidity": sensor_data["Turbidity"]}))
                    else:
                        await websocket.send(json.dumps({"error": "Invalid data format"}))
                else:
                    await websocket.send(json.dumps({"error": "Invalid JSON structure"}))
            except Exception as e:
                print(f"❌ Error handling message: {e}")
                await websocket.send(json.dumps({"error": "Error processing data"}))
    except Exception as e:
        print(f"❌ Connection error: {e}")
    finally:
        print("🔌 A client disconnected.")

def updateToDb(data):
    ref.update(data)
    print("✅ Successfully updated Firebase")

def send_fcm_notification(title, body):
    # Send FCM message to a topic
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        topic='alerts',  # Assuming devices are subscribed to 'alerts' topic
    )
    
    try:
        response = messaging.send(message)
        print(f"📲 FCM: Successfully sent message: {response}")
    except Exception as e:
        print(f"❌ FCM error: {e}")

async def checkThreshold(data, websocket):
    ph_value = refPh.get()
    temp_value = refTemp.get()
    turb_value = refTurb.get()

    ph = data["PH"]
    temp = data["Temperature"]
    turb = data["Turbidity"]

    if ph_value and ph_value["Min"] != 0 and ph_value["Max"] != 0:
        if ph < ph_value["Min"] or ph > ph_value["Max"]:
            alert_msg = "⚠️ PH value is out of range!"
            await websocket.send(json.dumps({"alertForPH": alert_msg}))
            send_fcm_notification("PH Alert", alert_msg)

    if temp_value and temp_value["Min"] != 0 and temp_value["Max"] != 0:
        if temp < temp_value["Min"] or temp > temp_value["Max"]:
            alert_msg = "⚠️ Temperature value is out of range!"
            await websocket.send(json.dumps({"alertForTemp": alert_msg}))
            send_fcm_notification("Temperature Alert", alert_msg)

    if turb_value and turb_value["Min"] != 0 and turb_value["Max"] != 0:
        if turb < turb_value["Min"] or turb > turb_value["Max"]:
            alert_msg = "⚠️ Turbidity value is out of range!"
            await websocket.send(json.dumps({"alertForTurb": alert_msg}))
            send_fcm_notification("Turbidity Alert", alert_msg)

async def start_websocket_server():
    port = int(os.environ.get("PORT", 10000))  # Important for Render
    server = await websockets.serve(handle_websocket, "0.0.0.0", port)
    print(f"🚀 WebSocket server is running on port {port}...")
    await server.wait_closed()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_websocket_server())