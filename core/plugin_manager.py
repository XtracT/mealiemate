"""
Module: plugin_manager
---------------------
Provides functionality for managing plugin lifecycle and configuration.

This module implements the PluginManager class, which is responsible for:
1. Starting and stopping plugins
2. Tracking running plugin instances
3. Managing plugin configurations
4. Applying configurations to plugins
"""

import asyncio
import logging
import traceback
import sys
from typing import Dict, Any, Optional, List, Type

from core.plugin import Plugin
from core.plugin_registry import PluginRegistry
from core.container import Container
from core.services import MqttService

# Configure logging
logger = logging.getLogger(__name__)

class PluginManager:
    """Manages plugin lifecycle and configuration."""
    
    def __init__(self, registry: PluginRegistry, container: Container, mqtt_service: MqttService):
        """
        Initialize the PluginManager.
        
        Args:
            registry: The plugin registry containing all discovered plugins
            container: The dependency injection container
            mqtt_service: The MQTT service for communication
        """
        self._registry = registry
        self._container = container
        self._mqtt_service = mqtt_service
        
        # Track running tasks, plugin instances, and configurations
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._running_plugin_instances: Dict[str, Plugin] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
    
    async def start_plugin(self, plugin_id: str) -> bool:
        """
        Start a plugin by ID.
        
        Args:
            plugin_id: ID of the plugin to start
            
        Returns:
            True if the plugin was started successfully, False otherwise
        """
        # Check if plugin is already running
        if plugin_id in self._running_tasks:
            await self._mqtt_service.info(plugin_id, "Plugin is already running", category="skip")
            return False
            
        await self._mqtt_service.info(plugin_id, "Starting plugin", category="start")
        
        # Get the plugin class from the registry
        plugin_cls = self._registry.get_plugin(plugin_id)
        if not plugin_cls:
            logger.error(f"Plugin {plugin_id} not found in registry")
            await self._mqtt_service.error(plugin_id, f"Plugin {plugin_id} not found")
            return False
            
        # Create plugin instance with dependencies injected
        try:
            plugin = self._container.inject(plugin_cls)
            
            # Apply any stored configuration values to the plugin
            self.apply_config_to_plugin(plugin)

            # Reset plugin sensors
            await self._reset_plugin_sensors(plugin)
        except Exception as e:
            logger.error(f"Error creating plugin instance for {plugin_id}: {str(e)}")
            await self._mqtt_service.error(plugin_id, f"Error creating plugin instance: {str(e)}")
            return False
        
        # Store the plugin instance and create task for the plugin
        self._running_plugin_instances[plugin_id] = plugin
        task = asyncio.create_task(self._execute_plugin(plugin_id, plugin))
        self._running_tasks[plugin_id] = task
        logger.debug(f"Stored running plugin instance for {plugin_id}, object ID: {id(plugin)}")
        
        # Update switch state to ON
        await self._mqtt_service.set_switch_state(plugin_id, "ON")
        
        return True
    
    async def stop_plugin(self, plugin_id: str) -> bool:
        """
        Stop a running plugin by ID.
        
        Args:
            plugin_id: ID of the plugin to stop
            
        Returns:
            True if the plugin was stopped successfully, False otherwise
        """
        if plugin_id not in self._running_tasks:
            await self._mqtt_service.info(plugin_id, "Plugin is not running", category="skip")
            return False
            
        await self._mqtt_service.info(plugin_id, "Stopping plugin", category="stop")
        
        # Update switch state to OFF immediately when the user requests to stop the plugin
        await self._mqtt_service.set_switch_state(plugin_id, "OFF")


        
        # Cancel the task
        task = self._running_tasks.pop(plugin_id)
        task.cancel()
        
        try:
            await asyncio.wait_for(task, timeout=1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            await self._mqtt_service.info(plugin_id, "Plugin cancelled or timed out during shutdown", category="stop")
        
        # Reset progress sensors and others with "Stopped" activity when manually stopped
        plugin_cls = self._registry.get_plugin(plugin_id)
        if plugin_cls:
            plugin = self._container.inject(plugin_cls)

            # Check if this plugin has a progress sensor by looking at its MQTT entities
            entities = plugin.get_mqtt_entities()
            if "sensors" in entities and "progress" in entities["sensors"]:
                await self._mqtt_service.update_progress(plugin_id, "progress", 0, "Stopped")
        
            # Reset plugin sensors
            await self._reset_plugin_sensors(plugin)

        # Remove the plugin instance
        self._running_plugin_instances.pop(plugin_id, None)
        logger.debug(f"Removed plugin instance for {plugin_id} from running_plugin_instances")
        
        return True

    async def _reset_plugin_sensors(self, plugin: Plugin) -> None:
        """Reset sensors defined by the plugin."""
        plugin_id = plugin.id
        if hasattr(plugin, "reset_sensors"):
            try:
                sensor_ids = plugin.reset_sensors
                if isinstance(sensor_ids, list):
                    for sensor_id in sensor_ids:
                        await self._mqtt_service.reset_sensor(plugin_id, sensor_id)
                        logger.debug(f"Resetting {sensor_id} sensor for plugin {plugin_id}")
                else:
                    logger.warning(f"Plugin {plugin_id} has reset_sensors attribute, but it is not a list.")
            except Exception as e:
                logger.error(f"Error resetting sensors for plugin {plugin_id}: {str(e)}")

    async def _execute_plugin(self, plugin_id: str, plugin: Plugin) -> None:
        """
        Execute a plugin and handle its lifecycle.
        
        Args:
            plugin_id: ID of the plugin to execute
            plugin: The plugin instance to execute
        """
        try:
            # Wait for the plugin to complete
            await plugin.execute()
            await self._mqtt_service.success(plugin_id, "Plugin completed successfully")
            # Update switch state to OFF only when the plugin completes successfully
            await self._mqtt_service.set_switch_state(plugin_id, "OFF")
        except asyncio.CancelledError:
            await self._mqtt_service.info(plugin_id, "Plugin stopped manually", category="stop")
            # Update switch state to OFF when the plugin is cancelled
            await self._mqtt_service.set_switch_state(plugin_id, "OFF")
        except Exception as e:
            # Log detailed error information
            logger.error(f"Error in plugin {plugin_id}: {str(e)}", exc_info=True)
            
            # Print a detailed traceback to the console
            traceback.print_exc()
            
            # Get file name and line number for quick reference
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_tb:
                file_name = exc_tb.tb_frame.f_code.co_filename
                line_no = exc_tb.tb_lineno
                await self._mqtt_service.error(plugin_id, f"Error at {file_name}:{line_no} → {e}")
            else:
                await self._mqtt_service.error(plugin_id, f"Error: {str(e)}")
            # Update switch state to OFF when the plugin encounters an error
            await self._mqtt_service.set_switch_state(plugin_id, "OFF")
        finally:
            # Clean up
            self._running_tasks.pop(plugin_id, None)
            self._running_plugin_instances.pop(plugin_id, None)
            logger.debug(f"Removed plugin instance for {plugin_id} from running_plugin_instances")
    
    def is_plugin_running(self, plugin_id: str) -> bool:
        """
        Check if a plugin is currently running.
        
        Args:
            plugin_id: ID of the plugin to check
            
        Returns:
            True if the plugin is running, False otherwise
        """
        return plugin_id in self._running_tasks
    
    def get_running_plugins(self) -> List[str]:
        """
        Get a list of all currently running plugins.
        
        Returns:
            List of plugin IDs that are currently running
        """
        return list(self._running_tasks.keys())
    
    def apply_config_to_plugin(self, plugin: Plugin) -> None:
        """
        Apply stored configuration values to a plugin instance.
        
        Args:
            plugin: The plugin instance to apply configuration to
        """
        plugin_id = plugin.id
        if plugin_id in self._plugin_configs:
            logger.debug(f"Applying stored configuration for {plugin_id}: {self._plugin_configs[plugin_id]}")
            for attr_name, value in self._plugin_configs[plugin_id].items():
                if hasattr(plugin, attr_name):
                    setattr(plugin, attr_name, value)
                    logger.debug(f"Applied stored config {attr_name}={value} to {plugin_id}")
                else:
                    logger.warning(f"Plugin {plugin_id} has no attribute {attr_name}")
    
    def store_plugin_config(self, plugin_id: str, attr_name: str, value: Any) -> None:
        """
        Store a configuration value for a plugin.
        
        Args:
            plugin_id: ID of the plugin
            attr_name: Name of the attribute to store
            value: Value to store
        """
        if plugin_id not in self._plugin_configs:
            self._plugin_configs[plugin_id] = {}
        
        self._plugin_configs[plugin_id][attr_name] = value
        logger.debug(f"Stored config for {plugin_id}: {attr_name}={value}")
        
        # If the plugin is currently running, update its configuration
        if plugin_id in self._running_plugin_instances:
            plugin = self._running_plugin_instances[plugin_id]
            if hasattr(plugin, attr_name):
                setattr(plugin, attr_name, value)
                logger.debug(f"Updated running plugin instance {plugin_id} attribute {attr_name} to {value}")
            else:
                logger.warning(f"Running plugin instance {plugin_id} has no attribute {attr_name}")
    
    def get_plugin_config(self, plugin_id: str, attr_name: str) -> Optional[Any]:
        """
        Get a stored configuration value for a plugin.
        
        Args:
            plugin_id: ID of the plugin
            attr_name: Name of the attribute to retrieve
            
        Returns:
            The stored value, or None if not found
        """
        if plugin_id in self._plugin_configs and attr_name in self._plugin_configs[plugin_id]:
            return self._plugin_configs[plugin_id][attr_name]
        return None
    
    def get_plugin_configs(self, plugin_id: str) -> Dict[str, Any]:
        """
        Get all stored configuration values for a plugin.
        
        Args:
            plugin_id: ID of the plugin
            
        Returns:
            Dictionary of attribute names to values
        """
        return self._plugin_configs.get(plugin_id, {})
    
    def get_running_plugin_instance(self, plugin_id: str) -> Optional[Plugin]:
        """
        Get a running plugin instance by ID.
        
        Args:
            plugin_id: ID of the plugin
            
        Returns:
            The plugin instance if running, None otherwise
        """
        return self._running_plugin_instances.get(plugin_id)