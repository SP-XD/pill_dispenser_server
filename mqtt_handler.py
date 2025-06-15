import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT, DEVICE_TOPIC
from database import log_event
from notifier import send_notification

# Derived topics
STATUS_TOPIC = f"{DEVICE_TOPIC}/status"
SCHEDULE_STATUS_TOPIC = f"{DEVICE_TOPIC}/schedule/status"
SETTINGS_STATUS_TOPIC = f"{DEVICE_TOPIC}/settings/status"
ALERTS_TOPIC = f"{DEVICE_TOPIC}/alerts"

def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker with result code:", rc)

    # Subscribe to all relevant topics from the device
    client.subscribe(STATUS_TOPIC)
    client.subscribe(SCHEDULE_STATUS_TOPIC)
    client.subscribe(SETTINGS_STATUS_TOPIC)
    client.subscribe(ALERTS_TOPIC)

    print("📡 Subscribed to:")
    print(f" - {STATUS_TOPIC}")
    print(f" - {SCHEDULE_STATUS_TOPIC}")
    print(f" - {SETTINGS_STATUS_TOPIC}")
    print(f" - {ALERTS_TOPIC}")

def on_message(client, userdata, msg):
    topic = msg.topic
    message = msg.payload.decode()
    print(f"[MQTT] ⬇ Message on `{topic}`: {message}")

    # Smart motor/module label extraction (if message follows pattern)
    motor = message.split(":")[0] if ":" in message else "system"

    # Log all events
    log_event(motor, message)

    # Trigger alerts based on content
    if topic.endswith("alerts") or any(phrase in message for phrase in ["Pills low", "NOT taken", "is empty", "⚠️", "❌"]):
        send_notification(f"🚨 ALERT: {message}")

def start_mqtt_listener():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
