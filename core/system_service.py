"""
Module: system_service
--------------------
Provides functionality for system-level tasks.

This module implements the SystemService class, which is responsible for:
1. Setting up MQTT entities for Home Assistant integration
2. Resetting special sensors
3. Sending status heartbeats
4. Checking for midnight to reset sensors
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple

from core.plugin_registry import PluginRegistry
from core.plugin_manager import PluginManager
from core.container import Container
from core.services import MqttService

# Configure logging
logger = logging.getLogger(__name__)

class SystemService:
    """Handles system-level tasks."""
    
    def __init__(self, registry: PluginRegistry, container: Container, plugin_manager: PluginManager):
        """
        Initialize the SystemService.
        
        Args:
            registry: The plugin registry containing all discovered plugins
            container: The dependency injection container
        """
        self._registry = registry
        self._container = container
        self._plugin_manager = plugin_manager


        self._mqtt_service = container.resolve(MqttService)
        if not self._mqtt_service:
            raise ValueError("MQTT service not found in container")
        
        # Track background tasks
        self._tasks: List[asyncio.Task] = []
    
    async def setup_mqtt_entities(self) -> None:
        """
        Set up all MQTT entities for Home Assistant discovery.
        
        This registers all switches, sensors, numbers, and text inputs for each plugin,
        plus a service status indicator for the overall application.
        """
        if not self._mqtt_service:
            logger.error("MQTT service not found in container")
            return
            
        await self._mqtt_service.info("mealiemate", "Setting up MQTT entities for Home Assistant discovery", category="config")
        
        # Set up entities for each plugin
        for plugin_id, plugin_cls in self._registry.get_all_plugins().items():
            try:
                # Create plugin instance with dependencies injected
                plugin = self._container.inject(plugin_cls)
                
                # Apply any stored configuration to the plugin instance
                # This ensures we use the latest values from retained messages
                self._plugin_manager.apply_config_to_plugin(plugin)
                
                # Get MQTT entity configuration from the plugin
                entities = plugin.get_mqtt_entities()
                
                # Set up switch for enabling/disabling the plugin
                if entities.get("switch", False):
                    await self._mqtt_service.setup_mqtt_switch(plugin.id, plugin.name)

                # Set up sensors for plugin output
                for sensor_id, sensor in entities.get("sensors", {}).items():
                    await self._mqtt_service.setup_mqtt_sensor(
                        plugin.id, 
                        sensor["id"], 
                        sensor["name"]
                    )
                    
                    # Initialize progress sensors to 0 with blank activity
                    if sensor_id == "progress":
                        await self._mqtt_service.setup_mqtt_progress(
                            plugin.id,
                            sensor["id"],
                            sensor["name"]
                        )
                        await self._mqtt_service.update_progress(plugin.id, sensor["id"], 0, "")

                # Set up number inputs for plugin configuration
                for number_id, number in entities.get("numbers", {}).items():
                    # Check if the number entity has type, min, max, step, and unit
                    min_value = number.get("min", 1)
                    max_value = number.get("max", 1000)
                    step = number.get("step", 1)
                    unit = number.get("unit", "")
                    
                    # Get the current value from the plugin instance
                    # This will reflect any retained messages that were processed
                    attr_name = f"_{number_id}"
                    current_value = getattr(plugin, attr_name, number["value"]) if hasattr(plugin, attr_name) else number["value"]
                    
                    # Log the value we're using (default or from configuration)
                    if hasattr(plugin, attr_name):
                        logger.debug(f"Setting up number {plugin.id}_{number_id} with configured value {current_value}")
                    else:
                        logger.debug(f"Setting up number {plugin.id}_{number_id} with default value {current_value}")
                    
                    await self._mqtt_service.setup_mqtt_number(
                        plugin.id,
                        number["id"],
                        number["name"],
                        current_value,  # Use current value from plugin instance
                        min_value,
                        max_value,
                        step,
                        unit
                    )

                # Set up text inputs for plugin configuration
                for text_id, text in entities.get("texts", {}).items():
                    # Get the current value from the plugin instance
                    # This will reflect any retained messages that were processed
                    attr_name = f"_{text_id}"
                    current_value = getattr(plugin, attr_name, text["text"]) if hasattr(plugin, attr_name) else text["text"]
                    
                    # Log the value we're using (default or from configuration)
                    if hasattr(plugin, attr_name):
                        logger.debug(f"Setting up text {plugin.id}_{text_id} with configured value {current_value}")
                    else:
                        logger.debug(f"Setting up text {plugin.id}_{text_id} with default value {current_value}")
                    
                    await self._mqtt_service.setup_mqtt_text(
                        plugin.id,
                        text["id"],
                        text["name"],
                        current_value  # Use current value from plugin instance
                    )
                    
                # Set up buttons for plugin interaction
                for button_id, button in entities.get("buttons", {}).items():
                    await self._mqtt_service.setup_mqtt_button(
                        plugin.id,
                        button["id"],
                        button["name"]
                    )
                    logger.debug(f"Registered MQTT button: {button['name']}")
                    
                # Set up additional switches for plugin configuration
                for switch_id, switch in entities.get("switches", {}).items():
                    # Get the current value from the plugin instance
                    attr_name = f"_{switch_id}"
                    current_value = getattr(plugin, attr_name, switch.get("value", False)) if hasattr(plugin, attr_name) else switch.get("value", False)
                    
                    # Log the value we're using (default or from configuration)
                    if hasattr(plugin, attr_name):
                        logger.debug(f"Setting up switch {plugin.id}_{switch_id} with configured value {current_value}")
                    else:
                        logger.debug(f"Setting up switch {plugin.id}_{switch_id} with default value {current_value}")
                    
                    # First set up the switch entity
                    await self._mqtt_service.setup_mqtt_switch(
                        f"{plugin.id}_{switch['id']}",
                        switch["name"]
                    )
                    
                    # Then set its state based on the current value
                    state = "ON" if current_value else "OFF"
                    await self._mqtt_service.set_switch_state(f"{plugin.id}_{switch['id']}", state)
                    
                logger.debug(f"Set up MQTT entities for plugin: {plugin.id}")
            except Exception as e:
                logger.error(f"Error setting up MQTT entities for plugin {plugin_id}: {str(e)}")

        # Set up overall service status indicator
        await self._mqtt_service.setup_mqtt_binary_sensor("mealiemate_status", "", "MealieMate Status")
        await self._mqtt_service.success("mealiemate", "MQTT entity setup complete")
    

    async def reset_special_sensors(self) -> None:
        """Reset all special sensors (feedback, dough_recipe, current_suggestion) for all plugins."""
        #TODO: This function should be done from the sensor configuration of each plugin
        if not self._mqtt_service:
            logger.error("MQTT service not found in container")
            return

        if not self._plugin_manager:
            logger.error("Plugin manager not found in container")
            return

        # Iterate through all plugins
        for plugin_id, plugin_cls in self._registry.get_all_plugins().items():
            try:
                # Create plugin instance with dependencies injected
                plugin = self._container.inject(plugin_cls)

                # Reset plugin sensors
                await self._plugin_manager._reset_plugin_sensors(plugin)
            except Exception as e:
                logger.error(f"Error resetting sensors for plugin {plugin_id}: {str(e)}")

    async def start_midnight_reset_task(self) -> asyncio.Task:
        """
        Start a task to check for midnight and reset special sensors.
        
        Returns:
            The asyncio task for the midnight reset check
        """
        task = asyncio.create_task(self._check_midnight_reset())
        self._tasks.append(task)
        return task
    
    async def _check_midnight_reset(self) -> None:
        """Periodically check if it's midnight and reset special sensors if it is."""
        if not self._mqtt_service:
            logger.error("MQTT service not found in container")
            return
        
        # Track the last day we performed a reset
        last_reset_day = datetime.now().day
        
        while True:
            try:
                # Get current time
                now = datetime.now()
                
                # Check if it's a new day (midnight passed)
                if now.day != last_reset_day:
                    logger.info("Midnight detected, resetting special sensors")
                    await self._mqtt_service.info("mealiemate", "Midnight detected, resetting special sensors", category="time")
                    
                    # Reset all special sensors
                    await self.reset_special_sensors()
                    
                    # Update the last reset day
                    last_reset_day = now.day
                
                # Check every minute
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                logger.info("Midnight reset task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in midnight reset check: {str(e)}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def start_heartbeat_task(self) -> asyncio.Task:
        """
        Start a task to send status heartbeats.
        
        Returns:
            The asyncio task for the heartbeat
        """
        task = asyncio.create_task(self._send_status_heartbeat())
        self._tasks.append(task)
        return task
    
    async def _send_status_heartbeat(self) -> None:
        """
        Periodically send a status heartbeat to Home Assistant to keep the device shown as available.
        
        Home Assistant has a timeout for MQTT devices, and if it doesn't receive updates
        periodically, it will mark the device as unavailable. This function sends a status
        update every hour to prevent that from happening.
        """
        while True:
            try:
                # Send a heartbeat every hour
                await self._mqtt_service.set_binary_sensor_state("mealiemate_status", "ON")
                logger.debug("Sent status heartbeat to Home Assistant")
                
                # Wait for an hour before sending the next heartbeat
                await asyncio.sleep(3600)  # 3600 seconds = 1 hour
            except asyncio.CancelledError:
                logger.info("Heartbeat task cancelled")
                break
            except Exception as e:
                logger.error(f"Error sending status heartbeat: {str(e)}")
                # If there was an error, wait a bit and try again
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def stop_all_tasks(self) -> None:
        """Stop all background tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()