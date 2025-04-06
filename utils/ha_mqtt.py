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
from aiomqtt import Client as MqttClient # Use an alias for clarity

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

# Global reference to the main MQTT client (set by core/app.py)
_main_client_ref: Optional[MqttClient] = None

def set_main_client_ref(client: MqttClient) -> None:
    """Sets the global reference to the main MQTT client."""
    global _main_client_ref
    if client:
        logger.info("Setting main MQTT client reference.")
        _main_client_ref = client
    else:
        logger.warning("Attempted to set main MQTT client reference to None.")
        _main_client_ref = None # Allow unsetting if needed

def _get_client() -> Optional[MqttClient]:
    """Gets the main MQTT client reference, logging an error if not set."""
    if not _main_client_ref:
        logger.error("Main MQTT client reference (_main_client_ref) not set. Cannot publish.")
    return _main_client_ref

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

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        await client.publish(state_topic, "OFF", retain=True) # Publish initial state
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

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        # No initial state needed for timestamp sensor, but clear buffer
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

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        await client.publish(state_topic, str(default_value), retain=True) # Publish initial state
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

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        await client.publish(state_topic, str(default_value), retain=True) # Publish initial state
        logger.info(f"Registered MQTT text: {text_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT text '{text_name}': {str(e)}")
        return False

async def setup_mqtt_button(script_id: str, button_id: str, button_name: str) -> bool:
    """
    Register an MQTT button in Home Assistant.
    
    Args:
        script_id: Unique identifier for the script
        button_id: Unique identifier for this specific button
        button_name: Human-readable name for the button
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
        unique_id = f"{script_id}_{button_id}"
        command_topic = f"{MQTT_DISCOVERY_PREFIX}/button/{unique_id}/command"
        config_topic = f"{MQTT_DISCOVERY_PREFIX}/button/{unique_id}/config"

        discovery_payload = {
            "name": f"{button_name}",
            "command_topic": command_topic,
            "unique_id": unique_id,
            "payload_press": "PRESS",
            "icon": "mdi:gesture-tap-button",
            "device": DEVICE_INFO,
        }

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        # Buttons don't have state, just config
        logger.info(f"Registered MQTT button: {button_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT button '{button_name}': {str(e)}")
        return False

async def setup_mqtt_binary_sensor(script_id: str, sensor_id: str, sensor_name: str) -> bool:
    """
    Register an MQTT binary sensor in Home Assistant.
    
    Args:
        script_id: Unique identifier for the script
        sensor_id: Unique identifier for this specific binary sensor (can be empty)
        sensor_name: Human-readable name for the binary sensor
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
        # If sensor_id is empty, use script_id as the unique_id
        unique_id = script_id if not sensor_id else f"{script_id}_{sensor_id}"
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

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        # Also publish initial state to ensure the entity is available immediately
        await client.publish(state_topic, "ON", retain=True)
        logger.info(f"Registered MQTT binary sensor: {sensor_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT binary sensor '{sensor_name}': {str(e)}")
        return False
        
async def setup_mqtt_image(plugin_id: str, image_id: str, name: str, image_topic: str) -> bool:
    """
    Register an MQTT image entity in Home Assistant asynchronously.
    
    Args:
        plugin_id: Unique identifier for the plugin
        image_id: Unique identifier for this specific image entity
        name: Human-readable name for the image entity
        image_topic: The topic where the image bytes will be published
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
        # Use the first identifier from DEVICE_INFO for consistency
        base_identifier = DEVICE_INFO['identifiers'][0]
        unique_id = f"{base_identifier}_{plugin_id}_{image_id}"
        config_topic = f"{MQTT_DISCOVERY_PREFIX}/image/{unique_id}/config"

        discovery_payload = {
            "name": name,
            "unique_id": unique_id,
            "image_topic": image_topic,  # State topic where image bytes are published
            "content_type": "image/png",
            "icon": "mdi:image",
            "device": DEVICE_INFO,
            # Link availability to the main MealieMate status binary sensor
            "availability_topic": f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{base_identifier}_status/state", # Assuming status sensor unique_id is 'mealiemate_status'
            "payload_available": "ON",
            "payload_not_available": "OFF",
        }

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        # Publish an initial empty payload to the image topic to ensure HA initializes the entity
        await client.publish(image_topic, payload=b'', retain=False)
        logger.info(f"Registered MQTT image entity: {name} (Topic: {image_topic}) and published initial empty payload.")
        return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT image entity '{name}': {str(e)}")
        return False

async def log(
    script_id: str, 
    sensor_id: str, 
    message: str, 
    reset: bool = False, 
    level: int = INFO,
    category: Optional[str] = None,
    log_to_ha: bool = True,
    log_to_console: bool = None,
    extra_attributes: Optional[Dict[str, str]] = None
) -> bool:
    # Determine default log_to_console value based on level if not explicitly set
    if log_to_console is None:
        # By default, only log WARNING and above to console, unless it's a specific category
        log_to_console = level >= WARNING or category in ["start", "stop", "success", "critical"]
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
    
    # Format message with emoji
    formatted_message = message
    
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
        client = _get_client()
        if not client:
            return False # Error logged in _get_client

        await client.publish(state_topic, state_value, retain=True)
        
        # Create attributes dictionary with full_text
        attributes = {"full_text": log_buffers[(script_id, sensor_id)]}
        
        # Add any extra attributes if provided
        if extra_attributes:
            attributes.update(extra_attributes)
            
        await client.publish(
            attributes_topic,
            json.dumps(attributes),
            retain=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to publish log message to MQTT: {str(e)}")
        return False

# Convenience functions for different log levels
async def debug(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log a debug message (not sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=DEBUG, category=category, log_to_ha=False, log_to_console=False, extra_attributes=extra_attributes)

async def info(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log an info message."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category=category, log_to_ha=False, extra_attributes=extra_attributes)

async def warning(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log a warning message (sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=WARNING, category=category, log_to_ha=False, extra_attributes=extra_attributes)

async def error(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log an error message (sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=ERROR, category=category, log_to_ha=False, extra_attributes=extra_attributes)

async def critical(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log a critical message (sent to Home Assistant)."""
    return await log(script_id, sensor_id or "status", message, level=CRITICAL, category=category, log_to_ha=False, extra_attributes=extra_attributes)

# Special purpose logging functions
async def gpt_decision(script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log a GPT decision."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category="gpt", log_to_ha=False, log_to_console=False, extra_attributes=extra_attributes)

async def progress(script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log a progress update."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category="progress", log_to_ha=False, extra_attributes=extra_attributes)

async def success(script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    """Log a success message."""
    return await log(script_id, sensor_id or "status", message, level=INFO, category="success", log_to_ha=False, log_to_console=True, extra_attributes=extra_attributes)

async def setup_mqtt_progress(script_id: str, sensor_id: str, sensor_name: str) -> bool:
    """
    Register an MQTT progress sensor in Home Assistant.
    
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
            "unit_of_measurement": "%",
            "icon": "mdi:percent",
            "device": DEVICE_INFO,
        }

        client = _get_client()
        if not client:
            return False
            
        await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
        # Initialize with 0%
        await client.publish(state_topic, "0", retain=True)
        await client.publish(attributes_topic, json.dumps({"activity": ""}), retain=True)
        logger.info(f"Registered MQTT progress sensor: {sensor_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to setup MQTT progress sensor '{sensor_name}': {str(e)}")
        return False

async def reset_sensor(script_id: str, sensor_id: str) -> bool:
    """
    Reset a sensor by writing an empty string to it.
    
    Args:
        script_id: Unique identifier for the script
        sensor_id: Unique identifier for the sensor to reset
        
    Returns:
        True if reset was successful, False otherwise
    """
    logger.info(f"Resetting sensor: {script_id}_{sensor_id}")
    
    # Check if sensor is initialized
    if (script_id, sensor_id) not in log_buffers:
        logger.warning(f"Attempted to reset uninitialized sensor: {script_id}_{sensor_id}")
        return False
    
    # Reset the buffer directly without adding any emoji
    log_buffers[(script_id, sensor_id)] = ""
    
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/state"
    attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/attributes"
    
    state_value = datetime.now(timezone.utc).isoformat()
    
    try:
        client = _get_client()
        if not client:
            return False
            
        await client.publish(state_topic, state_value, retain=True) # Update timestamp
        await client.publish(
            attributes_topic,
            json.dumps({"full_text": ""}), # Clear attributes text
            retain=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to reset sensor {script_id}_{sensor_id}: {str(e)}")
        return False

async def update_progress(script_id: str, sensor_id: str, percentage: int, activity: str) -> bool:
    """
    Update the progress sensor with current percentage and activity.
    
    Args:
        script_id: Unique identifier for the script
        sensor_id: Unique identifier for this specific sensor
        percentage: Progress percentage (0-100)
        activity: Current activity description
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        unique_id = f"{script_id}_{sensor_id}"
        state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/state"
        attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/attributes"

        # Ensure percentage is within bounds
        percentage = max(0, min(100, percentage))
        
        # Special handling for completion and stopped states
        if percentage == 100:
            activity = "Finished"
        elif percentage == 0 and activity.lower() == "stopped":
            activity = "Stopped"
        
        client = _get_client()
        if not client:
            return False
            
        await client.publish(state_topic, str(percentage), retain=True)
        await client.publish(attributes_topic, json.dumps({"activity": activity}), retain=True)
        logger.debug(f"Updated progress for {script_id}_{sensor_id}: {percentage}% - {activity}") # Corrected log message
        return True
    except Exception as e:
        logger.error(f"Failed to update progress for {script_id}: {str(e)}")
        return False

async def set_switch_state(switch_id: str, state: str) -> bool:
    """
    Set the state of a switch in Home Assistant.
    
    Args:
        switch_id: ID of the switch (e.g. plugin_id_switch_id)
        state: New state ("ON" or "OFF")
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        state_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{switch_id}/state"
        
        client = _get_client()
        if not client:
            return False
            
        await client.publish(state_topic, payload=state, retain=True)
        logger.debug(f"Set switch state for {switch_id} to {state}")
        return True
    except Exception as e:
        logger.error(f"Failed to set switch state for {switch_id}: {str(e)}")
        return False

async def set_binary_sensor_state(sensor_id: str, state: str) -> bool:
    """
    Set the state of a binary sensor in Home Assistant.
    
    Args:
        sensor_id: ID of the binary sensor (e.g. script_id_sensor_id)
        state: New state ("ON" or "OFF")
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{sensor_id}/state"
        
        client = _get_client()
        if not client:
            return False
            
        await client.publish(state_topic, payload=state, retain=True)
        logger.debug(f"Set binary sensor state for {sensor_id} to {state}")
        return True
    except Exception as e:
        logger.error(f"Failed to set binary sensor state for {sensor_id}: {str(e)}")
        return False

async def publish_mqtt_image(topic: str, payload: bytes, retain: bool = False, qos: int = 0) -> bool:
    """
    Publish raw image bytes to a specific MQTT topic.

    Args:
        topic: The MQTT topic to publish to
        payload: The raw image bytes to publish
        retain: Whether the message should be retained
        qos: Quality of Service level

    Returns:
        True if publishing was successful, False otherwise
    """
    try:
        client = _get_client()
        if not client:
            return False
            
        await client.publish(topic, payload=payload, qos=qos, retain=retain)
        logger.debug(f"Published image bytes to topic: {topic} ({len(payload)} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to publish image bytes to MQTT topic '{topic}': {str(e)}")
        return False
