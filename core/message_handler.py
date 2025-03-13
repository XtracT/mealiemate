"""
Module: message_handler
----------------------
Provides a class for handling MQTT messages and dispatching them to the appropriate plugins.

This module implements the MqttMessageHandler class, which is responsible for:
1. Processing incoming MQTT messages
2. Identifying which plugin the message is for
3. Dispatching the message to the appropriate handler
4. Starting and stopping plugins via the PluginManager
5. Updating plugin configurations
"""

import logging
from typing import Dict, Any, Optional

from core.plugin_registry import PluginRegistry
from core.container import Container
from core.services import MqttService
from core.plugin_manager import PluginManager

# Configure logging
logger = logging.getLogger(__name__)

class MqttMessageHandler:
    """Handles MQTT messages and dispatches them to the appropriate plugins."""

    def __init__(self, registry: PluginRegistry, container: Container, plugin_manager: PluginManager):
        """
        Initializes the MqttMessageHandler.

        Args:
            registry: The plugin registry containing all discovered plugins.
            container: The dependency injection container.
            plugin_manager: The plugin manager for starting and stopping plugins.
        """
        self._registry = registry
        self._container = container
        self._plugin_manager = plugin_manager
        self._mqtt_service = container.resolve(MqttService)
        if not self._mqtt_service:
            raise ValueError("MQTT service not found in container")

    async def process_message(self, topic: str, payload: str) -> None:
        """
        Processes an MQTT message and takes appropriate action.

        Args:
            topic: MQTT topic of the message.
            payload: Decoded payload of the message.
        """
        # Extract entity ID from topic
        raw_id = topic.split("/")[-2]  # e.g. "shopping_list_generator_mealplan_length"

        # If topic includes "mealiemate_" as a prefix, remove it
        if raw_id.startswith("mealiemate_"):
            raw_id = raw_id.removeprefix("mealiemate_")

        plugin_id = None
        entity_id = ""

        # Find which plugin this message is for
        for candidate_id in self._registry.get_all_plugins().keys():
            if raw_id.startswith(candidate_id):
                plugin_id = candidate_id
                # Extract the entity ID (part after the plugin ID)
                if len(raw_id) > len(candidate_id):
                    entity_id = raw_id[len(candidate_id) + 1:]  # e.g. "mealplan_length"
                break

        # Validate plugin ID
        if not plugin_id or plugin_id not in self._registry.get_all_plugins():
            await self._mqtt_service.warning("mealiemate", f"Unknown plugin ID in MQTT message: {raw_id}")
            return

        # Get the plugin class from the registry
        plugin_cls = self._registry.get_plugin(plugin_id)
        if not plugin_cls:
            logger.error(f"Plugin {plugin_id} not found in registry")
            await self._mqtt_service.error("mealiemate", f"Plugin {plugin_id} not found")
            return

        # Determine the type of message and dispatch to the appropriate handler
        if "switch" in topic:
            await self._handle_switch_command(plugin_id, entity_id, payload)
        elif "number" in topic:
            await self._handle_number_update(plugin_id, entity_id, payload)
        elif "text" in topic:
            await self._handle_text_update(plugin_id, entity_id, payload)
        elif "button" in topic and payload == "PRESS":
            await self._handle_button_command(plugin_id, entity_id)
        else:
            await self._mqtt_service.warning(plugin_id, f"Unknown command: {payload}")

    async def _handle_switch_command(self, plugin_id: str, entity_id: str, payload: str) -> None:
        """
        Handle a switch command (ON/OFF).
        
        Args:
            plugin_id: ID of the plugin
            entity_id: ID of the entity (empty for main plugin switch)
            payload: Command payload ("ON" or "OFF")
        """
        if entity_id == "":  # Main plugin switch
            if payload == "ON":
                await self._plugin_manager.start_plugin(plugin_id)
            elif payload == "OFF":
                await self._plugin_manager.stop_plugin(plugin_id)
        else:  # Additional plugin switches
            # Create plugin instance with dependencies injected
            try:
                plugin_cls = self._registry.get_plugin(plugin_id)
                plugin = self._container.inject(plugin_cls)
                entities = plugin.get_mqtt_entities()

                # Find the switch in the switches dictionary
                if "switches" in entities:
                    for switch_id, switch in entities["switches"].items():
                        if switch["id"] == entity_id:
                            # Update the plugin's instance variable based on entity_id
                            attr_name = f"_{switch_id}"
                            if hasattr(plugin, attr_name):
                                # Convert payload to boolean
                                value = payload == "ON"

                                # Store in persistent configuration
                                self._plugin_manager.store_plugin_config(plugin_id, attr_name, value)

                                # Update the switch state in Home Assistant
                                await self._mqtt_service.set_switch_state(f"{plugin_id}_{entity_id}", payload)

                                await self._mqtt_service.info(plugin_id, f"Updated switch {entity_id} to {payload}", category="data")
                                return
                            else:
                                logger.warning(f"Plugin {plugin_id} has no attribute {attr_name}")
                                await self._mqtt_service.warning(plugin_id, f"Unknown switch attribute: {attr_name}")
                                return

                # If we get here, the switch was not found in the switches dictionary
                await self._mqtt_service.warning(plugin_id, f"Unknown switch: {entity_id}")
            except Exception as e:
                logger.error(f"Error handling switch command for {plugin_id}: {str(e)}")
                await self._mqtt_service.error(plugin_id, f"Error handling switch command: {str(e)}")

    async def _handle_number_update(self, plugin_id: str, entity_id: str, payload: str) -> None:
        """
        Handle a number update.
        
        Args:
            plugin_id: ID of the plugin
            entity_id: ID of the entity
            payload: New value
        """
        try:
            # Create plugin instance with dependencies injected
            plugin_cls = self._registry.get_plugin(plugin_id)
            plugin = self._container.inject(plugin_cls)
            
            # Check if this is a float type number
            entities = plugin.get_mqtt_entities()
            is_float = False
            if "numbers" in entities:
                for number_id, number in entities["numbers"].items():
                    if number["id"] == entity_id and number.get("type") == "float":
                        is_float = True
                        break

            # Parse as float or int based on the type
            if is_float:
                value = float(payload)
            else:
                value = int(payload)

            # Update the plugin's instance variable based on entity_id
            # This assumes the plugin has instance variables named _entity_id
            attr_name = f"_{entity_id}"
            if hasattr(plugin, attr_name):
                # Store in persistent configuration
                self._plugin_manager.store_plugin_config(plugin_id, attr_name, value)

                await self._mqtt_service.info(plugin_id, f"Updated number {entity_id} to {value}", category="data")
            else:
                logger.warning(f"Plugin {plugin_id} has no attribute {attr_name}")
                await self._mqtt_service.warning(plugin_id, f"Unknown number entity: {entity_id}")
        except ValueError:
            await self._mqtt_service.error(plugin_id, f"Invalid number value received: {payload}")
        except KeyError:
            logger.error(f"Unknown number entity: {entity_id} for plugin {plugin_id}")
        except Exception as e:
            logger.error(f"Error handling number update for {plugin_id}: {str(e)}")
            await self._mqtt_service.error(plugin_id, f"Error handling number update: {str(e)}")

    async def _handle_text_update(self, plugin_id: str, entity_id: str, payload: str) -> None:
        """
        Handle a text update.
        
        Args:
            plugin_id: ID of the plugin
            entity_id: ID of the entity
            payload: New text value
        """
        try:
            # Create plugin instance with dependencies injected
            plugin_cls = self._registry.get_plugin(plugin_id)
            plugin = self._container.inject(plugin_cls)
            
            # Update the plugin's configuration
            text = str(payload)

            # Update the plugin's instance variable based on entity_id
            # This assumes the plugin has instance variables named _entity_id
            attr_name = f"_{entity_id}"
            if hasattr(plugin, attr_name):
                # Store in persistent configuration
                self._plugin_manager.store_plugin_config(plugin_id, attr_name, text)

                await self._mqtt_service.info(plugin_id, f"Updated text {entity_id} to: {text[:30]}...", category="data")
            else:
                logger.warning(f"Plugin {plugin_id} has no attribute {attr_name}")
                await self._mqtt_service.warning(plugin_id, f"Unknown text entity: {entity_id}")
        except ValueError:
            await self._mqtt_service.error(plugin_id, f"Invalid string value received: {payload}")
        except KeyError:
            logger.error(f"Unknown text entity: {entity_id} for plugin {plugin_id}")
        except Exception as e:
            logger.error(f"Error handling text update for {plugin_id}: {str(e)}")
            await self._mqtt_service.error(plugin_id, f"Error handling text update: {str(e)}")

    async def _handle_button_command(self, plugin_id: str, entity_id: str) -> None:
        """
        Handle a button command.
        
        Args:
            plugin_id: ID of the plugin
            entity_id: ID of the entity
        """
        logger.info(f"Button press received for {plugin_id}_{entity_id}")
        await self._mqtt_service.info(plugin_id, f"Button {entity_id} pressed", category="data")

        # Get the running plugin instance if it exists
        running_plugin = self._plugin_manager.get_running_plugin_instance(plugin_id)
        if running_plugin:
            logger.debug(f"Found running instance of {plugin_id}, object ID: {id(running_plugin)}")

            # Handle ingredient merger plugin buttons
            if plugin_id == "ingredient_merger":
                if entity_id == "accept_button":
                    # Set the user accepted flag and trigger the event on the RUNNING instance
                    if hasattr(running_plugin, "_user_accepted") and hasattr(running_plugin, "_user_decision_received"):
                        running_plugin._user_accepted = True
                        running_plugin._user_decision_received.set()
                        logger.debug(f"Set accept flag for ingredient merger plugin (running instance)")
                    else:
                        logger.warning(f"Running plugin instance doesn't have expected attributes")
                elif entity_id == "reject_button":
                    # Set the user rejected flag and trigger the event on the RUNNING instance
                    if hasattr(running_plugin, "_user_accepted") and hasattr(running_plugin, "_user_decision_received"):
                        running_plugin._user_accepted = False
                        running_plugin._user_decision_received.set()
                        logger.debug(f"Set reject flag for ingredient merger plugin (running instance)")
                    else:
                        logger.warning(f"Running plugin instance doesn't have expected attributes")

            # Handle shopping list generator plugin buttons
            elif plugin_id == "shopping_list_generator":
                if entity_id == "continue_to_next_batch":
                    # Trigger the event on the RUNNING instance to continue to next batch
                    if hasattr(running_plugin, "_user_decision_received"):
                        running_plugin._user_decision_received.set()
                        logger.debug(f"Triggered continue button for shopping list generator plugin (running instance)")
                    else:
                        logger.warning(f"Running plugin instance doesn't have expected attributes")
        else:
            logger.warning(f"Button press received for {plugin_id}_{entity_id}, but plugin is not running")