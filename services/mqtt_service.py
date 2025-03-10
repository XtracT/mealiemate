"""
Module: mqtt_service
------------------
Provides an implementation of the MqttService interface using the ha_mqtt module.

This module wraps the existing ha_mqtt functionality in a class that implements
the MqttService interface, making it compatible with the dependency injection system.
"""

import logging
from typing import Dict, Any, Optional

from core.services import MqttService
import utils.ha_mqtt as ha_mqtt

# Configure logging
logger = logging.getLogger(__name__)

class MqttServiceImpl(MqttService):
    """Implementation of the MqttService interface using ha_mqtt."""
    
    async def setup_mqtt_switch(self, plugin_id: str, name: str) -> bool:
        """
        Register an MQTT switch in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            name: Human-readable name for the switch
            
        Returns:
            True if registration was successful, False otherwise
        """
        return await ha_mqtt.setup_mqtt_switch(plugin_id, name)
    
    async def setup_mqtt_sensor(self, plugin_id: str, sensor_id: str, name: str) -> bool:
        """
        Register an MQTT sensor in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific sensor
            name: Human-readable name for the sensor
            
        Returns:
            True if registration was successful, False otherwise
        """
        return await ha_mqtt.setup_mqtt_sensor(plugin_id, sensor_id, name)
    
    async def setup_mqtt_number(
        self, 
        plugin_id: str, 
        number_id: str, 
        name: str, 
        default_value: int, 
        min_value: int = 1, 
        max_value: int = 1000, 
        step: int = 1, 
        unit: str = ""
    ) -> bool:
        """
        Register an MQTT Number entity in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            number_id: Unique identifier for this specific number input
            name: Human-readable name for the number input
            default_value: Initial value for the number
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            step: Step size for incrementing/decrementing
            unit: Unit of measurement (optional)
            
        Returns:
            True if registration was successful, False otherwise
        """
        return await ha_mqtt.setup_mqtt_number(
            plugin_id, number_id, name, default_value, min_value, max_value, step, unit
        )
    
    async def setup_mqtt_text(
        self, 
        plugin_id: str, 
        text_id: str, 
        name: str, 
        default_value: str = "", 
        max_length: int = 255
    ) -> bool:
        """
        Register an MQTT Text entity in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            text_id: Unique identifier for this specific text input
            name: Human-readable name for the text input
            default_value: Initial value for the text field
            max_length: Maximum allowed length for the text
            
        Returns:
            True if registration was successful, False otherwise
        """
        return await ha_mqtt.setup_mqtt_text(plugin_id, text_id, name, default_value, max_length)
    
    async def setup_mqtt_button(self, plugin_id: str, button_id: str, name: str) -> bool:
        """
        Register an MQTT button in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            button_id: Unique identifier for this specific button
            name: Human-readable name for the button
            
        Returns:
            True if registration was successful, False otherwise
        """
        return await ha_mqtt.setup_mqtt_button(plugin_id, button_id, name)
    
    async def setup_mqtt_service_status(self, plugin_id: str, sensor_id: str, name: str) -> bool:
        """
        Register an MQTT binary sensor to indicate the service status in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific status sensor
            name: Human-readable name for the status sensor
            
        Returns:
            True if registration was successful, False otherwise
        """
        return await ha_mqtt.setup_mqtt_service_status(plugin_id, sensor_id, name)
    
    async def log(
        self, 
        plugin_id: str, 
        sensor_id: str, 
        message: str, 
        reset: bool = False, 
        level: int = 20,  # INFO
        category: Optional[str] = None,
        log_to_ha: bool = True
    ) -> bool:
        """
        Enhanced log function that handles both console and Home Assistant logging.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for the sensor to log to
            message: Message text to log
            reset: If True, clear the existing log buffer before adding this message
                   Note: For feedback, dough_recipe, and mealplan sensors, reset is always True
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            category: Optional category for emoji selection
            log_to_ha: Whether to log to Home Assistant (set to False for debug messages)
            
        Returns:
            True if logging was successful, False otherwise
        """
        return await ha_mqtt.log(plugin_id, sensor_id, message, reset, level, category, log_to_ha)
    
    async def debug(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log a debug message (not sent to Home Assistant)."""
        return await ha_mqtt.debug(plugin_id, message, sensor_id, category)
    
    async def info(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log an info message."""
        return await ha_mqtt.info(plugin_id, message, sensor_id, category)
    
    async def warning(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log a warning message."""
        return await ha_mqtt.warning(plugin_id, message, sensor_id, category)
    
    async def error(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log an error message."""
        return await ha_mqtt.error(plugin_id, message, sensor_id, category)
    
    async def critical(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log a critical message."""
        return await ha_mqtt.critical(plugin_id, message, sensor_id, category)
    
    async def gpt_decision(self, plugin_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
        """Log a GPT decision."""
        return await ha_mqtt.gpt_decision(plugin_id, message, sensor_id)
    
    async def progress(self, plugin_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
        """Log a progress update."""
        return await ha_mqtt.progress(plugin_id, message, sensor_id)
    
    async def success(self, plugin_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
        """Log a success message."""
        return await ha_mqtt.success(plugin_id, message, sensor_id)
        
    async def setup_mqtt_progress(self, plugin_id: str, sensor_id: str, name: str) -> bool:
        """
        Register an MQTT progress sensor in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific sensor
            name: Human-readable name for the sensor
            
        Returns:
            True if registration was successful, False otherwise
        """
        return await ha_mqtt.setup_mqtt_progress(plugin_id, sensor_id, name)
    
    async def update_progress(self, plugin_id: str, sensor_id: str, percentage: int, activity: str) -> bool:
        """
        Update the progress sensor with current percentage and activity.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific sensor
            percentage: Progress percentage (0-100)
            activity: Current activity description
            
        Returns:
            True if update was successful, False otherwise
        """
        return await ha_mqtt.update_progress(plugin_id, sensor_id, percentage, activity)
