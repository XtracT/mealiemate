"""
Module: ha_mqtt
----------------
Provides helper functions for registering and updating MQTT entities in Home Assistant,
plus a log() function for appending messages to MQTT sensors.
"""

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
import aiomqtt

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_DISCOVERY_PREFIX = "homeassistant"

# Buffers used to store log text for each sensor before publishing
log_buffers = {}

async def setup_mqtt_switch(script_id, script_name):
    """
    Register an MQTT switch in Home Assistant asynchronously.
    """
    unique_id = f"{script_id}"
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{unique_id}/state"
    command_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{unique_id}/set"
    config_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{unique_id}/config"

    discovery_payload = {
        "name": f"{script_name}",
        "command_topic": command_topic,
        "state_topic": state_topic,
        "unique_id": unique_id,
        "device": {
            "identifiers": ["mealiemate"],
            "name": "MealieMate",
            "manufacturer": "Custom Script",
            "model": "MealieMate",
            "sw_version": "0.1"
        },
        "payload_on": "ON",
        "payload_off": "OFF",
        "optimistic": False
    }

    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        await client.publish(state_topic, "OFF", retain=True)

async def setup_mqtt_sensor(script_id, sensor_id, sensor_name):
    """
    Register an MQTT sensor (timestamp device class) in Home Assistant asynchronously.
    """
    unique_id = f"{script_id}_{sensor_id}"
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/state"
    attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/attributes"
    config_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/config"

    discovery_payload = {
        "name": f"{sensor_name}",
        "state_topic": state_topic,
        "json_attributes_topic": attributes_topic,
        "unique_id": unique_id,
        "device_class": "timestamp",
        "icon": "mdi:clipboard-text",
        "device": {
            "identifiers": ["mealiemate"],
            "name": "MealieMate",
            "manufacturer": "Custom Script",
            "model": "MealieMate",
            "sw_version": "0.1"
        },
    }

    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)

    log_buffers[(script_id, sensor_id)] = ""

async def setup_mqtt_number(script_id, number_id, number_name, default_value, min_value=1, max_value=1000, step=1, unit=""):
    """
    Register an MQTT Number entity (input) in Home Assistant asynchronously.
    """
    unique_id = f"{script_id}_{number_id}"
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/number/{unique_id}/state"
    command_topic = f"{MQTT_DISCOVERY_PREFIX}/number/{unique_id}/set"
    config_topic = f"{MQTT_DISCOVERY_PREFIX}/number/{unique_id}/config"

    discovery_payload = {
        "name": number_name,
        "state_topic": state_topic,
        "command_topic": command_topic,
        "unique_id": unique_id,
        "min": min_value,
        "max": max_value,
        "step": step,
        "mode": "box",
        "unit_of_measurement": unit,
        "retain": True,
        "device": {
            "identifiers": ["mealiemate"],
            "name": "MealieMate",
            "manufacturer": "Custom Script",
            "model": "MealieMate",
            "sw_version": "0.1"
        }
    }

    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        await client.publish(state_topic, str(default_value), retain=True)


async def setup_mqtt_text(script_id, text_id, text_name, default_value="", max_length=255):
    """
    Register an MQTT Text entity in Home Assistant asynchronously.
    """
    unique_id = f"{script_id}_{text_id}"
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/text/{unique_id}/state"
    command_topic = f"{MQTT_DISCOVERY_PREFIX}/text/{unique_id}/set"
    config_topic = f"{MQTT_DISCOVERY_PREFIX}/text/{unique_id}/config"

    discovery_payload = {
        "name": text_name,
        "state_topic": state_topic,
        "command_topic": command_topic,
        "unique_id": unique_id,
        "mode": "text",  # Ensures it is treated as a text field
        "max": max_length,
        "retain": True,
        "device": {
            "identifiers": ["mealiemate"],
            "name": "MealieMate",
            "manufacturer": "Custom Script",
            "model": "MealieMate",
            "sw_version": "0.1"
        }
    }

    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        await client.publish(state_topic, str(default_value), retain=True)

async def setup_mqtt_service_status(script_id, sensor_id, sensor_name):
    """
    Register an MQTT binary sensor to indicate the service status in Home Assistant.
    """
    unique_id = f"{script_id}_{sensor_id}"
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{unique_id}/state"
    config_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{unique_id}/config"

    discovery_payload = {
        "name": f"{sensor_name}",
        "state_topic": state_topic,
        "unique_id": unique_id,
        "payload_on": "ON",
        "payload_off": "OFF",
        "device": {
            "identifiers": ["mealiemate"],
            "name": "MealieMate",
            "manufacturer": "Custom Script",
            "model": "MealieMate",
            "sw_version": "0.1"
        },
    }

    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)

async def log(script_id, sensor_id, message, reset=False):
    """
    Log messages to a Home Assistant MQTT sensor by appending to an attribute field.
    """
    print(message)

    if (script_id, sensor_id) not in log_buffers:
        # Sensor not initialized, no need to publish MQTT log.
        return
    
    if reset:
        log_buffers[(script_id, sensor_id)] = ""

    log_buffers[(script_id, sensor_id)] += message + "\n"

    state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/state"
    attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/attributes"

    state_value = datetime.now(timezone.utc).isoformat()

    async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
        await client.publish(state_topic, state_value, retain=True)
        await client.publish(
            attributes_topic,
            json.dumps({"full_text": log_buffers[(script_id, sensor_id)]}),
            retain=True
        )
