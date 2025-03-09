"""
Module: ha_mqtt
----------------
Provides helper functions for registering and updating MQTT entities in Home Assistant,
plus enhanced logging functions for both console and Home Assistant sensors.

This module handles:
1. MQTT discovery for Home Assistant integration
2. Registering switches, sensors, numbers, and text inputs
3. Standardized logging with consistent emoji usage
4. Filtering logs to ensure Home Assistant sensors only receive important information
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Tuple, Any, Optional, Union
from dotenv import load_dotenv
import aiomqtt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_DISCOVERY_PREFIX = "homeassistant"

if not MQTT_BROKER:
    logger.warning("MQTT_BROKER not found in environment variables")

# Buffers used to store log text for each sensor before publishing
log_buffers: Dict[Tuple[str, str], str] = {}

# Log level constants
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Emoji mapping for different log types
EMOJI_MAP = {
    # Log levels
    "debug": "🔍",
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
    "critical": "🚨",
    
    # Categories
    "start": "🚀",
    "complete": "✅",
    "progress": "🔄",
    "gpt": "🤖",
    "data": "📊",
    "update": "📝",
    "network": "🌐",
    "time": "⏱️",
    "config": "⚙️",
    "skip": "⏭️",
    "stop": "🛑",
    "success": "🎉",
}

# Common device info used across all entities
DEVICE_INFO = {
    "identifiers": ["mealiemate"],
    "name": "MealieMate",
    "manufacturer": "Custom Script",
    "model": "MealieMate",
    "sw_version": "0.2"  # Updated version
}

async def setup_mqtt_switch(script_id: str, script_name: str) -> bool:
    """
    Register an MQTT switch in Home Assistant asynchronously.
    
    Args:
        script_id: Unique identifier for the script
        script_name: Human-readable name for the switch
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
        unique_id = f"{script_id}"
        state_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{unique_id}/state"
        command_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{unique_id}/set"
        config_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{unique_id}/config"

        discovery_payload = {
            "name": f"{script_name}",
            "command_topic": command_topic,
            "state_topic": state_topic,
            "unique_id": unique_id,
            "device": DEVICE_INFO,
            "payload_on": "ON",
            "payload_off": "OFF",
            "optimistic": False,
            "icon": "mdi:script-text-outline"
        }

        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, "OFF", retain=True)
            logger.info(f"Registered MQTT switch: {script_name}")
            return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT switch '{script_name}': {str(e)}")
        return False

async def setup_mqtt_sensor(script_id: str, sensor_id: str, sensor_name: str) -> bool:
    """
    Register an MQTT sensor (timestamp device class) in Home Assistant asynchronously.
    
    Args:
        script_id: Unique identifier for the script
        sensor_id: Unique identifier for this specific sensor
        sensor_name: Human-readable name for the sensor
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
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
            "device": DEVICE_INFO,
        }

        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            logger.info(f"Registered MQTT sensor: {sensor_name}")

        log_buffers[(script_id, sensor_id)] = ""
        return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT sensor '{sensor_name}': {str(e)}")
        return False

async def setup_mqtt_number(
    script_id: str, 
    number_id: str, 
    number_name: str, 
    default_value: int, 
    min_value: int = 1, 
    max_value: int = 1000, 
    step: int = 1, 
    unit: str = ""
) -> bool:
    """
    Register an MQTT Number entity (input) in Home Assistant asynchronously.
    
    Args:
        script_id: Unique identifier for the script
        number_id: Unique identifier for this specific number input
        number_name: Human-readable name for the number input
        default_value: Initial value for the number
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        step: Step size for incrementing/decrementing
        unit: Unit of measurement (optional)
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
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
            "icon": "mdi:numeric",
            "device": DEVICE_INFO
        }

        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, str(default_value), retain=True)
            logger.info(f"Registered MQTT number: {number_name} with default value {default_value}")
            return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT number '{number_name}': {str(e)}")
        return False


async def setup_mqtt_text(
    script_id: str, 
    text_id: str, 
    text_name: str, 
    default_value: str = "", 
    max_length: int = 255
) -> bool:
    """
    Register an MQTT Text entity in Home Assistant asynchronously.
    
    Args:
        script_id: Unique identifier for the script
        text_id: Unique identifier for this specific text input
        text_name: Human-readable name for the text input
        default_value: Initial value for the text field
        max_length: Maximum allowed length for the text
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
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
            "icon": "mdi:form-textbox",
            "device": DEVICE_INFO
        }

        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, str(default_value), retain=True)
            logger.info(f"Registered MQTT text: {text_name}")
            return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT text '{text_name}': {str(e)}")
        return False

async def setup_mqtt_service_status(script_id: str, sensor_id: str, sensor_name: str) -> bool:
    """
    Register an MQTT binary sensor to indicate the service status in Home Assistant.
    
    Args:
        script_id: Unique identifier for the script
        sensor_id: Unique identifier for this specific status sensor
        sensor_name: Human-readable name for the status sensor
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
        unique_id = f"{script_id}_{sensor_id}"
        state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{unique_id}/state"
        config_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{unique_id}/config"

        discovery_payload = {
            "name": f"{sensor_name}",
            "state_topic": state_topic,
            "unique_id": unique_id,
            "payload_on": "ON",
            "payload_off": "OFF",
            "device_class": "running",
            "icon": "mdi:check-circle-outline",
            "device": DEVICE_INFO,
        }

        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            logger.info(f"Registered MQTT service status: {sensor_name}")
            return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT service status '{sensor_name}': {str(e)}")
        return False

async def log(
    script_id: str, 
    sensor_id: str, 
    message: str, 
    reset: bool = False, 
    level: int = INFO,
    category: Optional[str] = None,
    log_to_ha: bool = True,
    log_to_console: bool = True
) -> bool:
    """
    Enhanced log function that handles both console and Home Assistant logging.
    
    Args:
        script_id: Unique identifier for the script
        sensor_id: Unique identifier for the sensor to log to
        message: Message text to log
        reset: If True, clear the existing log buffer before adding this message
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        category: Optional category for emoji selection
        log_to_ha: Whether to log to Home Assistant (set to False for debug messages)
        
    Returns:
        True if logging was successful, False otherwise
    """
    # Determine emoji based on level and category
    emoji = ""
    if category and category in EMOJI_MAP:
        emoji = EMOJI_MAP[category]
    elif level == DEBUG:
        emoji = EMOJI_MAP["debug"]
    elif level == INFO:
        emoji = EMOJI_MAP["info"]
    elif level == WARNING:
        emoji = EMOJI_MAP["warning"]
    elif level == ERROR:
        emoji = EMOJI_MAP["error"]
    elif level == CRITICAL:
        emoji = EMOJI_MAP["critical"]
    
    # Format message with emoji
    formatted_message = f"{emoji} {message}" if emoji else message
    
    # Log to console with appropriate level
    if log_to_console:
        if level == DEBUG:
            logger.debug(f"[{script_id}] {formatted_message}")
        elif level == INFO:
            logger.info(f"[{script_id}] {formatted_message}")
        elif level == WARNING:
            logger.warning(f"[{script_id}] {formatted_message}")
        elif level == ERROR:
            logger.error(f"[{script_id}] {formatted_message}")
        elif level == CRITICAL:
            logger.critical(f"[{script_id}] {formatted_message}")
    
    # Always print to console for visibility
    
    # Only log to Home Assistant if requested and level is appropriate
    # (DEBUG messages are typically not logged to HA)
    if not log_to_ha or level < INFO:
        return True
    
    # Check if sensor is initialized
    if (script_id, sensor_id) not in log_buffers:
        logger.warning(f"Attempted to log to uninitialized sensor: {script_id}_{sensor_id}")
        return False
    
    if reset:
        log_buffers[(script_id, sensor_id)] = ""

    log_buffers[(script_id, sensor_id)] += formatted_message + "\n"

    state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/state"
    attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/attributes"

    state_value = datetime.now(timezone.utc).isoformat()

    try:
        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            await client.publish(state_topic, state_value, retain=True)
            await client.publish(
                attributes_topic,
                json.dumps({"full_text": log_buffers[(script_id, sensor_id)]}),
                retain=True
            )
        return True
    except Exception as e:
        logger.error(f"Failed to publish log message to MQTT: {str(e)}")
        return False

# Convenience functions for different log levels
async def debug(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
    """Log a debug message (not sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=DEBUG, category=category, log_to_ha=False, log_to_console=True)

async def info(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
    """Log an info message."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category=category, log_to_ha=False, log_to_console=True)

async def warning(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
    """Log a warning message (sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=WARNING, category=category, log_to_ha=True, log_to_console=True)

async def error(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
    """Log an error message (sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=ERROR, category=category, log_to_ha=True, log_to_console=True)

async def critical(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
    """Log a critical message (sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=CRITICAL, category=category, log_to_ha=True, log_to_console=True)

# Special purpose logging functions
async def gpt_decision(script_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
    """Log a GPT decision (always sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category="gpt", log_to_ha=True, log_to_console=False)

async def progress(script_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
    """Log a progress update."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category="progress", log_to_ha=False, log_to_console=True)

async def success(script_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
    """Log a success message (sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category="success", log_to_ha=True, log_to_console=False)
