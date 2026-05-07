"""
Module: mqtt_service
------------------
Provides an implementation of the MqttService interface using the ha_mqtt module.

This module wraps the existing ha_mqtt functionality in a class that implements
the MqttService interface, making it compatible with the dependency injection system.
"""

import logging
from typing import Dict, Any, Optional, Union

from core.services import MqttService
import utils.ha_mqtt as ha_mqtt

# Configure logging
logger = logging.getLogger(__name__)

class MqttServiceImpl(MqttService):
    """Implementation of the MqttService interface using ha_mqtt."""
    
    async def setup_mqtt_switch(self, plugin_id: str, name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        return await ha_mqtt.setup_mqtt_switch(plugin_id, name, device_info)
    
    async def setup_mqtt_sensor(self, plugin_id: str, sensor_id: str, name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        return await ha_mqtt.setup_mqtt_sensor(plugin_id, sensor_id, name, device_info)
    
    async def setup_mqtt_number(
        self, 
        plugin_id: str, 
        number_id: str, 
        name: str, 
        default_value: int, 
        min_value: int = 1, 
        max_value: int = 1000, 
        step: int = 1, 
        unit: str = "",
        device_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        return await ha_mqtt.setup_mqtt_number(
            plugin_id, number_id, name, default_value, min_value, max_value, step, unit, device_info
        )
    
    async def setup_mqtt_text(
        self, 
        plugin_id: str, 
        text_id: str, 
        name: str, 
        default_value: str = "", 
        max_length: int = 255,
        device_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        return await ha_mqtt.setup_mqtt_text(plugin_id, text_id, name, default_value, max_length, device_info)
    
    async def setup_mqtt_button(self, plugin_id: str, button_id: str, name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        return await ha_mqtt.setup_mqtt_button(plugin_id, button_id, name, device_info)
    
    async def setup_mqtt_binary_sensor(self, plugin_id: str, sensor_id: str, name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        return await ha_mqtt.setup_mqtt_binary_sensor(plugin_id, sensor_id, name, device_info)
    
    async def setup_mqtt_image(self, plugin_id: str, image_id: str, name: str, image_topic: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        return await ha_mqtt.setup_mqtt_image(plugin_id, image_id, name, image_topic, device_info)
        
    async def setup_mqtt_progress(self, plugin_id: str, sensor_id: str, name: str, device_info: Optional[Dict[str, Any]] = None) -> bool:
        return await ha_mqtt.setup_mqtt_progress(plugin_id, sensor_id, name, device_info)
    
    async def log(
        self, 
        plugin_id: str, 
        sensor_id: str, 
        message: str, 
        reset: bool = False, 
        level: int = 20,
        category: Optional[str] = None,
        log_to_ha: bool = True,
        extra_attributes: Optional[Dict[str, str]] = None
    ) -> bool:
        return await ha_mqtt.log(plugin_id, sensor_id, message, reset, level, category, log_to_ha, extra_attributes=extra_attributes)
    
    async def debug(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.debug(plugin_id, message, sensor_id, category, extra_attributes)
    
    async def info(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.info(plugin_id, message, sensor_id, category, extra_attributes)
    
    async def warning(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.warning(plugin_id, message, sensor_id, category, extra_attributes)
    
    async def error(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.error(plugin_id, message, sensor_id, category, extra_attributes)
    
    async def critical(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.critical(plugin_id, message, sensor_id, category, extra_attributes)
    
    async def gpt_decision(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.gpt_decision(plugin_id, message, sensor_id, extra_attributes)
    
    async def progress(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.progress(plugin_id, message, sensor_id, extra_attributes)
    
    async def success(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, extra_attributes: Optional[Dict[str, str]] = None) -> bool:
        return await ha_mqtt.success(plugin_id, message, sensor_id, extra_attributes)
    
    async def reset_sensor(self, plugin_id: str, sensor_id: str) -> bool:
        return await ha_mqtt.reset_sensor(plugin_id, sensor_id)
    
    async def update_progress(self, plugin_id: str, sensor_id: str, percentage: int, activity: str) -> bool:
        return await ha_mqtt.update_progress(plugin_id, sensor_id, percentage, activity)
        
    async def set_switch_state(self, switch_id: str, state: str) -> bool:
        return await ha_mqtt.set_switch_state(switch_id, state)
        
    async def set_binary_sensor_state(self, sensor_id: str, state: str) -> bool:
        return await ha_mqtt.set_binary_sensor_state(sensor_id, state)
        
    async def set_text_state(self, text_id: str, state: str) -> bool:
        return await ha_mqtt.set_text_state(text_id, state)
        
    async def publish_mqtt_image(self, topic: str, payload: bytes, retain: bool = False, qos: int = 0) -> bool:
        return await ha_mqtt.publish_mqtt_image(topic, payload, retain, qos)
