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
from aiomqtt import Client as MqttClient

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

# Root device info (for system-level entities: status sensor, AI model config)
ROOT_DEVICE_INFO: Dict[str, Any] = {
    "identifiers": ["mealiemate"],
    "name": "MealieMate",
    "manufacturer": "MealieMate",
    "model": "MealieMate",
    "sw_version": "0.2"
}


def get_device_info(plugin_id: str, plugin_name: str) -> Dict[str, Any]:
    """Build per-plugin device info for HA MQTT discovery.

    Plugin devices are linked as children of the root MealieMate device
    via ``via_device``, creating a parent-child hierarchy in HA.
    """
    return {
        "identifiers": [f"mealiemate_{plugin_id}"],
        "name": f"MealieMate - {plugin_name}",
        "manufacturer": "MealieMate",
        "model": "MealieMate Plugin",
        "sw_version": "0.2",
        "via_device": "mealiemate",
    }


class MqttStateManager:
    """Manages MQTT client reference and sensor log buffers.

    Encapsulates the mutable state that was previously stored in module-level
    globals, making it testable and allowing multiple independent instances.
    """

    def __init__(self) -> None:
        self._main_client_ref: Optional[MqttClient] = None
        self.log_buffers: Dict[Tuple[str, str], str] = {}

    def set_main_client_ref(self, client: Optional[MqttClient]) -> None:
        """Set (or unset) the MQTT client reference."""
        if client:
            logger.info("Setting main MQTT client reference.")
            self._main_client_ref = client
        else:
            logger.warning("Unsetting main MQTT client reference.")
            self._main_client_ref = None

    def _get_client(self) -> Optional[MqttClient]:
        """Get the MQTT client, logging an error if not set."""
        if not self._main_client_ref:
            logger.error("Main MQTT client reference not set. Cannot publish.")
        return self._main_client_ref

    # ------------------------------------------------------------------
    # Entity setup methods
    # ------------------------------------------------------------------

    async def setup_mqtt_switch(self, script_id: str, script_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        device = device_info or ROOT_DEVICE_INFO
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
                "device": device,
                "payload_on": "ON",
                "payload_off": "OFF",
                "optimistic": False,
                "icon": "mdi:script-text-outline"
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, "OFF", retain=True)
            logger.info(f"Registered MQTT switch: {script_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT switch '{script_name}': {str(e)}")
            return False

    async def setup_mqtt_sensor(self, script_id: str, sensor_id: str, sensor_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        device = device_info or ROOT_DEVICE_INFO
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
                "device": device,
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            logger.info(f"Registered MQTT sensor: {sensor_name}")
            self.log_buffers[(script_id, sensor_id)] = ""
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT sensor '{sensor_name}': {str(e)}")
            return False

    async def setup_mqtt_number(
        self,
        script_id: str,
        number_id: str,
        number_name: str,
        default_value: int,
        min_value: int = 1,
        max_value: int = 1000,
        step: int = 1,
        unit: str = "",
        device_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        device = device_info or ROOT_DEVICE_INFO
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
                "device": device
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, str(default_value), retain=True)
            logger.info(f"Registered MQTT number: {number_name} with default value {default_value}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT number '{number_name}': {str(e)}")
            return False

    async def setup_mqtt_text(
        self,
        script_id: str,
        text_id: str,
        text_name: str,
        default_value: str = "",
        max_length: int = 255,
        device_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        device = device_info or ROOT_DEVICE_INFO
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
                "mode": "text",
                "max": max_length,
                "retain": True,
                "icon": "mdi:form-textbox",
                "device": device
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, str(default_value), retain=True)
            logger.info(f"Registered MQTT text: {text_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT text '{text_name}': {str(e)}")
            return False

    async def setup_mqtt_button(self, script_id: str, button_id: str, button_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        device = device_info or ROOT_DEVICE_INFO
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
                "device": device,
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            logger.info(f"Registered MQTT button: {button_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT button '{button_name}': {str(e)}")
            return False

    async def setup_mqtt_binary_sensor(self, script_id: str, sensor_id: str, sensor_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        device = device_info or ROOT_DEVICE_INFO
        try:
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
                "device": device,
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, "ON", retain=True)
            logger.info(f"Registered MQTT binary sensor: {sensor_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT binary sensor '{sensor_name}': {str(e)}")
            return False

    async def setup_mqtt_image(self, plugin_id: str, image_id: str, name: str, image_topic: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        device = device_info or ROOT_DEVICE_INFO
        try:
            base_identifier = ROOT_DEVICE_INFO['identifiers'][0]
            unique_id = f"{base_identifier}_{plugin_id}_{image_id}"
            config_topic = f"{MQTT_DISCOVERY_PREFIX}/image/{unique_id}/config"

            discovery_payload = {
                "name": name,
                "unique_id": unique_id,
                "image_topic": image_topic,
                "content_type": "image/png",
                "icon": "mdi:image",
                "device": device,
                "availability_topic": f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{base_identifier}_status/state",
                "payload_available": "ON",
                "payload_not_available": "OFF",
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(image_topic, payload=b'', retain=False)
            logger.info(f"Registered MQTT image entity: {name} (Topic: {image_topic}) and published initial empty payload.")
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT image entity '{name}': {str(e)}")
            return False

    async def setup_mqtt_progress(self, script_id: str, sensor_id: str, sensor_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        device = device_info or ROOT_DEVICE_INFO
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
                "device": device,
            }

            client = self._get_client()
            if not client:
                return False
                
            await client.publish(config_topic, json.dumps(discovery_payload), retain=True)
            await client.publish(state_topic, "0", retain=True)
            await client.publish(attributes_topic, json.dumps({"activity": ""}), retain=True)
            logger.info(f"Registered MQTT progress sensor: {sensor_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup MQTT progress sensor '{sensor_name}': {str(e)}")
            return False

    # ------------------------------------------------------------------
    # Logging methods
    # ------------------------------------------------------------------

    async def log(
        self,
        script_id: str,
        sensor_id: str,
        message: str,
        reset: bool = False,
        level: int = INFO,
        category: Optional[str] = None,
        log_to_ha: bool = True,
        log_to_console: Optional[bool] = None,
        extra_attributes: Optional[Dict[str, str]] = None
    ) -> bool:
        if log_to_console is None:
            log_to_console = level >= WARNING or category in ["start", "stop", "success", "critical"]

        formatted_message = message

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

        if not log_to_ha or level < INFO:
            return True

        if (script_id, sensor_id) not in self.log_buffers:
            logger.warning(f"Attempted to log to uninitialized sensor: {script_id}_{sensor_id}")
            return False

        if reset:
            self.log_buffers[(script_id, sensor_id)] = ""

        self.log_buffers[(script_id, sensor_id)] += formatted_message + "\n"

        state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/state"
        attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/attributes"

        state_value = datetime.now(timezone.utc).isoformat()

        try:
            client = self._get_client()
            if not client:
                return False

            await client.publish(state_topic, state_value, retain=True)

            attributes = {"full_text": self.log_buffers[(script_id, sensor_id)]}
            if extra_attributes:
                attributes.update(extra_attributes)

            await client.publish(attributes_topic, json.dumps(attributes), retain=True)
            return True
        except Exception as e:
            logger.error(f"Failed to publish log message to MQTT: {str(e)}")
            return False

    async def debug(self, script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=DEBUG, category=category, log_to_ha=False, log_to_console=False, extra_attributes=extra_attributes)

    async def info(self, script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=INFO, category=category, log_to_ha=False, extra_attributes=extra_attributes)

    async def warning(self, script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=WARNING, category=category, log_to_ha=False, extra_attributes=extra_attributes)

    async def error(self, script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=ERROR, category=category, log_to_ha=False, extra_attributes=extra_attributes)

    async def critical(self, script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=CRITICAL, category=category, log_to_ha=False, extra_attributes=extra_attributes)

    async def gpt_decision(self, script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=INFO, category="gpt", log_to_ha=False, log_to_console=False, extra_attributes=extra_attributes)

    async def progress(self, script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=INFO, category="progress", log_to_ha=False, extra_attributes=extra_attributes)

    async def success(self, script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await self.log(script_id, sensor_id or "status", message, level=INFO, category="success", log_to_ha=False, log_to_console=True, extra_attributes=extra_attributes)

    # ------------------------------------------------------------------
    # Sensor state methods
    # ------------------------------------------------------------------

    async def reset_sensor(self, script_id: str, sensor_id: str) -> bool:
        logger.info(f"Resetting sensor: {script_id}_{sensor_id}")

        if (script_id, sensor_id) not in self.log_buffers:
            logger.warning(f"Attempted to reset uninitialized sensor: {script_id}_{sensor_id}")
            return False

        self.log_buffers[(script_id, sensor_id)] = ""

        state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/state"
        attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{script_id}_{sensor_id}/attributes"

        state_value = datetime.now(timezone.utc).isoformat()

        try:
            client = self._get_client()
            if not client:
                return False

            await client.publish(state_topic, state_value, retain=True)
            await client.publish(attributes_topic, json.dumps({"full_text": ""}), retain=True)
            return True
        except Exception as e:
            logger.error(f"Failed to reset sensor {script_id}_{sensor_id}: {str(e)}")
            return False

    async def update_progress(self, script_id: str, sensor_id: str, percentage: int, activity: str) -> bool:
        try:
            unique_id = f"{script_id}_{sensor_id}"
            state_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/state"
            attributes_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/attributes"

            percentage = max(0, min(100, percentage))

            if percentage == 100:
                activity = "Finished"
            elif percentage == 0 and activity.lower() == "stopped":
                activity = "Stopped"

            client = self._get_client()
            if not client:
                return False

            await client.publish(state_topic, str(percentage), retain=True)
            await client.publish(attributes_topic, json.dumps({"activity": activity}), retain=True)
            logger.debug(f"Updated progress for {script_id}_{sensor_id}: {percentage}% - {activity}")
            return True
        except Exception as e:
            logger.error(f"Failed to update progress for {script_id}: {str(e)}")
            return False

    async def set_switch_state(self, switch_id: str, state: str) -> bool:
        try:
            state_topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{switch_id}/state"

            client = self._get_client()
            if not client:
                return False

            await client.publish(state_topic, payload=state, retain=True)
            logger.debug(f"Set switch state for {switch_id} to {state}")
            return True
        except Exception as e:
            logger.error(f"Failed to set switch state for {switch_id}: {str(e)}")
            return False

    async def set_binary_sensor_state(self, sensor_id: str, state: str) -> bool:
        try:
            state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{sensor_id}/state"

            client = self._get_client()
            if not client:
                return False

            await client.publish(state_topic, payload=state, retain=True)
            logger.debug(f"Set binary sensor state for {sensor_id} to {state}")
            return True
        except Exception as e:
            logger.error(f"Failed to set binary sensor state for {sensor_id}: {str(e)}")
            return False

    async def set_text_state(self, text_id: str, state: str) -> bool:
        try:
            state_topic = f"{MQTT_DISCOVERY_PREFIX}/text/{text_id}/state"

            client = self._get_client()
            if not client:
                return False

            await client.publish(state_topic, payload=state, retain=True)
            logger.debug(f"Set text state for {text_id} to {state}")
            return True
        except Exception as e:
            logger.error(f"Failed to set text state for {text_id}: {str(e)}")
            return False

    async def publish_mqtt_image(self, topic: str, payload: bytes, retain: bool = False, qos: int = 0) -> bool:
        try:
            client = self._get_client()
            if not client:
                return False

            await client.publish(topic, payload=payload, qos=qos, retain=retain)
            logger.debug(f"Published image bytes to topic: {topic} ({len(payload)} bytes)")
            return True
        except Exception as e:
            logger.error(f"Failed to publish image bytes to MQTT topic '{topic}': {str(e)}")
            return False


# ---------------------------------------------------------------------------
# Module-level backwards-compatible wrappers
# ---------------------------------------------------------------------------
# These delegate to a default MqttStateManager instance so that existing code
# (e.g. core/app.py calling ha_mqtt.set_main_client_ref) keeps working.

_default_manager = MqttStateManager()

def set_main_client_ref(client: Optional[MqttClient]) -> None:
    _default_manager.set_main_client_ref(client)

async def setup_mqtt_switch(script_id: str, script_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
    return await _default_manager.setup_mqtt_switch(script_id, script_name, device_info)

async def setup_mqtt_sensor(script_id: str, sensor_id: str, sensor_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
    return await _default_manager.setup_mqtt_sensor(script_id, sensor_id, sensor_name, device_info)

async def setup_mqtt_number(
    script_id: str,
    number_id: str,
    number_name: str,
    default_value: int,
    min_value: int = 1,
    max_value: int = 1000,
    step: int = 1,
    unit: str = "",
    device_info: Optional[Dict[str, Any]] = None
) -> bool:
    return await _default_manager.setup_mqtt_number(script_id, number_id, number_name, default_value, min_value, max_value, step, unit, device_info)

async def setup_mqtt_text(
    script_id: str,
    text_id: str,
    text_name: str,
    default_value: str = "",
    max_length: int = 255,
    device_info: Optional[Dict[str, Any]] = None
) -> bool:
    return await _default_manager.setup_mqtt_text(script_id, text_id, text_name, default_value, max_length, device_info)

async def setup_mqtt_button(script_id: str, button_id: str, button_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
    return await _default_manager.setup_mqtt_button(script_id, button_id, button_name, device_info)

async def setup_mqtt_binary_sensor(script_id: str, sensor_id: str, sensor_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
    return await _default_manager.setup_mqtt_binary_sensor(script_id, sensor_id, sensor_name, device_info)

async def setup_mqtt_image(plugin_id: str, image_id: str, name: str, image_topic: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
    return await _default_manager.setup_mqtt_image(plugin_id, image_id, name, image_topic, device_info)

async def log(
    script_id: str,
    sensor_id: str,
    message: str,
    reset: bool = False,
    level: int = INFO,
    category: Optional[str] = None,
    log_to_ha: bool = True,
    log_to_console: Optional[bool] = None,
    extra_attributes: Optional[Dict[str, str]] = None
) -> bool:
    return await _default_manager.log(script_id, sensor_id, message, reset, level, category, log_to_ha, log_to_console, extra_attributes)

async def debug(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.debug(script_id, message, sensor_id, category, extra_attributes)

async def info(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.info(script_id, message, sensor_id, category, extra_attributes)

async def warning(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.warning(script_id, message, sensor_id, category, extra_attributes)

async def error(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.error(script_id, message, sensor_id, category, extra_attributes)

async def critical(script_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.critical(script_id, message, sensor_id, category, extra_attributes)

async def gpt_decision(script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.gpt_decision(script_id, message, sensor_id, extra_attributes)

async def progress(script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.progress(script_id, message, sensor_id, extra_attributes)

async def success(script_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
    return await _default_manager.success(script_id, message, sensor_id, extra_attributes)

async def setup_mqtt_progress(script_id: str, sensor_id: str, sensor_name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
    return await _default_manager.setup_mqtt_progress(script_id, sensor_id, sensor_name, device_info)

async def reset_sensor(script_id: str, sensor_id: str) -> bool:
    return await _default_manager.reset_sensor(script_id, sensor_id)

async def update_progress(script_id: str, sensor_id: str, percentage: int, activity: str) -> bool:
    return await _default_manager.update_progress(script_id, sensor_id, percentage, activity)

async def set_switch_state(switch_id: str, state: str) -> bool:
    return await _default_manager.set_switch_state(switch_id, state)

async def set_binary_sensor_state(sensor_id: str, state: str) -> bool:
    return await _default_manager.set_binary_sensor_state(sensor_id, state)

async def set_text_state(text_id: str, state: str) -> bool:
    return await _default_manager.set_text_state(text_id, state)

async def publish_mqtt_image(topic: str, payload: bytes, retain: bool = False, qos: int = 0) -> bool:
    return await _default_manager.publish_mqtt_image(topic, payload, retain, qos)
