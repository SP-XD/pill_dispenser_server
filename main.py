from mqtt_handler import start_mqtt_listener
from database import init_db
from mqtt_publisher import (
   send_dispense_command,
   send_refill_command,
   set_hard_mode,
   publish_schedule,
   publish_settings
)
import time
# from api_server import start_api  # Optional if REST needed

if __name__ == "__main__":
    print("Starting Pill Server...")
    init_db()
    start_mqtt_listener()
    # start_api()  
    
    # time.sleep(10)
   
    # # Dispense from module1
    # send_dispense_command("device1", "module1")

    # # Refill module2 with 20 pills
    # send_refill_command("device1", "module2", 20)

    # print("hey")    
    # # Enable or disable hard mode
    # set_hard_mode("device1", enabled=True)

    # # Push new schedule
    # publish_schedule("device1", [
    #     {
    #         "time": "08:00",
    #         "dispenser_modules": ["module1", "module2"],
    #         "days": ["Mon", "Wed", "Fri"],
    #         "until_date": "2025-07-01"
    #     },
    #     {
    #         "time": "20:00",
    #         "dispenser_modules": ["module2"],
    #         "days": ["alternate"]
    #     }
    # ])

    # # Push updated settings like threshold or hard mode config
    # publish_settings("device1", {
    #     "hard_mode": True, })

    input("Press Enter to quit...\n")
