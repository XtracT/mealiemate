"""
Module: main_new
----------------
Similar to main.py, but includes a graceful shutdown procedure to publish OFF before exiting.
"""

import asyncio
import os
import signal
import traceback
import sys
import importlib
from datetime import datetime, timezone
from dotenv import load_dotenv
import aiomqtt

import ha_mqtt

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_DISCOVERY_PREFIX = "homeassistant"

running_tasks = {}
mqtt_message_queue = asyncio.Queue()

SCRIPTS = ["recipe_tagger", "meal_planner","shopping_list_generator","mealplan_fetcher"]
SCRIPT_MAP = {}
for script_name in SCRIPTS:
    module = importlib.import_module(script_name)
    SCRIPT_MAP[module.SCRIPT_CONFIG["id"]] = module.SCRIPT_CONFIG

async def setup_mqtt_entities():
    for script_id, script in SCRIPT_MAP.items():
        if script["switch"]:
            await ha_mqtt.setup_mqtt_switch(script_id, SCRIPT_MAP[script_id]["name"])

        for sensor in script["sensors"]:
            await ha_mqtt.setup_mqtt_sensor(script_id, sensor["id"], sensor["name"])

        for input_number in script.get("input_numbers", []):
            await ha_mqtt.setup_mqtt_number(script_id, input_number["id"], input_number["name"], input_number["default_value"],)

        for input_text in script.get("input_texts", []):
            await ha_mqtt.setup_mqtt_input_text(script_id, input_text["id"], input_text["name"], input_text["text"],)

    await ha_mqtt.setup_mqtt_service_status("mealiemate", "status", "MealieMate Status")

async def update_switch_state(script_id, state):
    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{script_id}/state"
        await client.publish(topic, payload=state, retain=True)

async def execute_script(script_id, script_func):
    print(f"🏁 Starting: {script_id}")
    await update_switch_state(script_id, "ON")

    task = asyncio.create_task(SCRIPT_MAP[script_id]["execute_function"]())
    running_tasks[script_id] = task

    try:
        await task
        print(f"✅ Completed successfully: {script_id}")
    except asyncio.CancelledError:
        print(f"🛑 Stopped manually: {script_id}")
    except Exception as e:
        # Option 1) Print a detailed traceback
        traceback.print_exc()
        print(f"⚠️ Error in {script_id}: {str(e)}")

        # Option 2) Print just the file name + line number
        exc_type, exc_value, exc_tb = sys.exc_info()
        file_name = exc_tb.tb_frame.f_code.co_filename
        line_no = exc_tb.tb_lineno
        print(f"⚠️ Error in {script_id} at {file_name}:{line_no} → {e}")
    finally:
        running_tasks.pop(script_id, None)
        await update_switch_state(script_id, "OFF")

async def mqtt_listener():
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/mealiemate_status/state"
    will_msg = aiomqtt.Will(topic=state_topic, payload="OFF", qos=1, retain=True)

    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT, will=will_msg, timeout=5) as client:
        await client.publish(state_topic, payload="ON", retain=True)

        await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/switch/+/set")
        await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/number/+/set")
        await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/text/+/set")

        async for message in client.messages:
            await mqtt_message_queue.put((str(message.topic), message.payload.decode()))

async def process_message(topic, payload):

    raw_id = topic.split("/")[-2]  # e.g. "shopping_list_generator_mealplan_length"

    # If your topic includes "mealiemate_" as a prefix, remove it:
    if raw_id.startswith("mealiemate_"):
        raw_id = raw_id.removeprefix("mealiemate_")

    script_id = None
    sensor_id = None

    # Try each known script in SCRIPT_MAP
    for candidate_id in SCRIPT_MAP:
        # If raw_id starts with "shopping_list_generator_", then we found our script
        if raw_id.startswith(candidate_id):
            script_id = candidate_id
            # The rest after the underscore is the suffix
            sensor_id = raw_id[len(candidate_id + "_"):]  # e.g. "mealplan_length"
            break

    print(script_id + ' ; '+ sensor_id)

    if script_id not in SCRIPT_MAP:
        print(f"⚠️ Unknown script: {script_id}")
        return
    
    if "number" in topic:
        try:
            ## TODO: update this so that everything is in input numbers 
            value = int(payload)
            SCRIPT_MAP[script_id]["parameters"]["num_days"] = value
            print(f"📊 Updated {script_id} parameter: days = {value}")
        except ValueError:
            print(f"⚠️ Invalid number received: {payload}")
        return

    if "text" in topic:
        try:
            text = str(payload)
            for item in SCRIPT_MAP[script_id].get("input_texts", []):
                if item.get("id") == sensor_id:  # Find the correct input_text entry
                    item["text"] = text  # Update the value

            print(f"📊 Updated {script_id} {sensor_id}: {text}")
        except ValueError:
            print(f"⚠️ Invalid string received: {payload}")
        return

    if payload == "ON":
        if script_id in running_tasks:
            print(f"⏭️ {script_id}: Already running")
            return
        asyncio.create_task(execute_script(script_id, SCRIPT_MAP[script_id]))
    elif payload == "OFF":
        if script_id not in running_tasks:
            print(f"⏭️ {script_id}: Not running")
            return
        print(f"🔚 Stopping: {script_id}")
        task = running_tasks.pop(script_id)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

async def mqtt_message_processor():
    while True:
        try:
            topic, payload = await asyncio.wait_for(mqtt_message_queue.get(), timeout=5)
            await process_message(topic, payload)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"⚠️ Processing error: {str(e)}")
            await asyncio.sleep(1)

async def main():
    print("🌟 MealieMate - Service Started")

    # Graceful shutdown
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler():
        print("🔔 Received shutdown signal")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await setup_mqtt_entities()

    listener_task = asyncio.create_task(mqtt_listener())
    processor_task = asyncio.create_task(mqtt_message_processor())

    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass

    print("🔦 Shutting down gracefully...")
    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/mealiemate_status/state"
        await client.publish(state_topic, payload="OFF", retain=True)

    for t in (listener_task, processor_task):
        t.cancel()
    await asyncio.gather(listener_task, processor_task, return_exceptions=True)

    print("👋 Bye!")

if __name__ == "__main__":
    asyncio.run(main())
