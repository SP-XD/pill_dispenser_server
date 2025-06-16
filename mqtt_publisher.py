import json
import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT

def get_client():
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    return client

def publish_command(device_id, command_str):
    topic = f"pill/{device_id}/command"
    client = get_client()
    client.publish(topic, command_str)
    client.loop(2)  # ensure delivery

'''
Schedule format: 

# maintain one medicine per schedule
new_schedule = [
    {
        "time": "08:00",
        "dispenser_modules": ["module1"], # module1 == medicine 1
        "days": ["Mon", "Wed", "Fri"],
        "until_date": "2025-07-01"
    },
    {
        "time": "20:00",
        "dispenser_modules": ["module2"], # module2 == medicine 2
        "days": ["daily"]
    }
]
'''
def publish_schedule(device_id, schedule_obj):
    topic = f"pill/{device_id}/schedule/set"
    payload = json.dumps(schedule_obj)
    client = get_client()
    client.publish(topic, payload)
    client.loop(2)

def publish_settings(device_id, settings_obj):
    topic = f"pill/{device_id}/settings/update"
    payload = json.dumps(settings_obj)
    client = get_client()
    client.publish(topic, payload)
    client.loop(2)
    
# ────── Command Shortcuts (Wrappers) ──────
def send_dispense_command(device_id, dispenser_module):
    command = f"dispense:{dispenser_module}"
    publish_command(device_id, command)

def send_refill_command(device_id, dispenser_module, count):
    command = f"refill:{dispenser_module}:{count}"
    publish_command(device_id, command)

def set_hard_mode(device_id, enabled=True):
    command = f"set_hard_mode:{str(enabled).lower()}"
    publish_command(device_id, command)

def reset_pending_module(device_id, dispenser_module):
    command = f"reset_pending:{dispenser_module}"
    publish_command(device_id, command)

