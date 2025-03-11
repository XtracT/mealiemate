#!/usr/bin/env python3
"""
Module: main
------------
Main entry point for the MealieMate application.

This module:
1. Sets up the dependency injection container
2. Discovers and loads plugins
3. Sets up MQTT entities for Home Assistant integration
4. Handles MQTT message processing for plugin control
5. Provides graceful shutdown to ensure proper cleanup

Each plugin is registered with Home Assistant via MQTT discovery and can be
controlled through the Home Assistant UI.
"""

import asyncio
import os
import signal
import traceback
import sys
import importlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set, Coroutine, Callable
from dotenv import load_dotenv
import aiomqtt

from core.plugin import Plugin
from core.plugin_registry import PluginRegistry
from core.container import Container
from core.services import MqttService, MealieApiService, GptService
from services.mqtt_service import MqttServiceImpl
from services.mealie_api_service import MealieApiServiceImpl
from services.gpt_service import GptServiceImpl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MQTT configuration
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_DISCOVERY_PREFIX = "homeassistant"

if not MQTT_BROKER:
    logger.warning("MQTT_BROKER not found in environment variables")

# Track running tasks, message queue, and plugin configurations
running_tasks: Dict[str, asyncio.Task] = {}
mqtt_message_queue: asyncio.Queue = asyncio.Queue()
plugin_configs: Dict[str, Dict[str, Any]] = {}  # Store plugin configurations persistently

async def setup_mqtt_entities(registry: PluginRegistry, container: Container) -> None:
    """
    Set up all MQTT entities for Home Assistant discovery.
    
    This registers all switches, sensors, numbers, and text inputs for each plugin,
    plus a service status indicator for the overall application.
    
    Args:
        registry: The plugin registry containing all discovered plugins
        container: The dependency injection container
    """
    mqtt_service = container.resolve(MqttService)
    if not mqtt_service:
        logger.error("MQTT service not found in container")
        return
        
    await mqtt_service.info("mealiemate", "Setting up MQTT entities for Home Assistant discovery", category="config")
    
    # Set up entities for each plugin
    for plugin_id, plugin_cls in registry.get_all_plugins().items():
        try:
            # Create plugin instance with dependencies injected
            plugin = container.inject(plugin_cls)
            
            # Get MQTT entity configuration from the plugin
            entities = plugin.get_mqtt_entities()
            
            # Set up switch for enabling/disabling the plugin
            if entities.get("switch", False):
                await mqtt_service.setup_mqtt_switch(plugin.id, plugin.name)

            # Set up sensors for plugin output
            for sensor_id, sensor in entities.get("sensors", {}).items():
                await mqtt_service.setup_mqtt_sensor(
                    plugin.id, 
                    sensor["id"], 
                    sensor["name"]
                )
                
                # Initialize progress sensors to 0 with blank activity
                if sensor_id == "progress":
                    await mqtt_service.setup_mqtt_progress(
                        plugin.id,
                        sensor["id"],
                        sensor["name"]
                    )
                    await mqtt_service.update_progress(plugin.id, sensor["id"], 0, "")

            # Set up number inputs for plugin configuration
            for number_id, number in entities.get("numbers", {}).items():
                await mqtt_service.setup_mqtt_number(
                    plugin.id, 
                    number["id"], 
                    number["name"],
                    number["value"]
                )
                
                # Store initial value in persistent configuration
                if plugin.id not in plugin_configs:
                    plugin_configs[plugin.id] = {}
                plugin_configs[plugin.id][f"_{number_id}"] = number["value"]
                logger.info(f"Stored initial number config for {plugin.id}: _{number_id}={number['value']}")

            # Set up text inputs for plugin configuration
            for text_id, text in entities.get("texts", {}).items():
                await mqtt_service.setup_mqtt_text(
                    plugin.id, 
                    text["id"], 
                    text["name"],
                    text["text"]
                )
                
                # Store initial value in persistent configuration
                if plugin.id not in plugin_configs:
                    plugin_configs[plugin.id] = {}
                plugin_configs[plugin.id][f"_{text_id}"] = text["text"]
                logger.info(f"Stored initial text config for {plugin.id}: _{text_id}={text['text']}")
                
            # Set up buttons for plugin interaction
            for button_id, button in entities.get("buttons", {}).items():
                await mqtt_service.setup_mqtt_button(
                    plugin.id,
                    button["id"],
                    button["name"]
                )
                logger.info(f"Registered MQTT button: {button['name']}")
                
            logger.info(f"Set up MQTT entities for plugin: {plugin.id}")
        except Exception as e:
            logger.error(f"Error setting up MQTT entities for plugin {plugin_id}: {str(e)}")

    # Set up overall service status indicator
    await mqtt_service.setup_mqtt_service_status("mealiemate", "status", "MealieMate Status")
    await mqtt_service.success("mealiemate", "MQTT entity setup complete")

async def update_switch_state(plugin_id: str, state: str) -> None:
    """
    Update the state of a plugin's switch in Home Assistant.
    
    Args:
        plugin_id: ID of the plugin
        state: New state ("ON" or "OFF")
    """
    try:
        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{plugin_id}/state"
            await client.publish(topic, payload=state, retain=True)
            logger.debug(f"Updated switch state for {plugin_id} to {state}")
    except Exception as e:
        logger.error(f"Failed to update switch state for {plugin_id}: {str(e)}")

async def execute_plugin(plugin_id: str, registry: PluginRegistry, container: Container) -> None:
    """
    Execute a plugin and handle its lifecycle.
    
    Args:
        plugin_id: ID of the plugin to execute
        registry: The plugin registry containing all discovered plugins
        container: The dependency injection container
    """
    mqtt_service = container.resolve(MqttService)
    if not mqtt_service:
        logger.error("MQTT service not found in container")
        return
        
    await mqtt_service.info(plugin_id, "Starting plugin", category="start")
    await update_switch_state(plugin_id, "ON")

    # Get the plugin class from the registry
    plugin_cls = registry.get_plugin(plugin_id)
    if not plugin_cls:
        logger.error(f"Plugin {plugin_id} not found in registry")
        await mqtt_service.error(plugin_id, f"Plugin {plugin_id} not found")
        return
        
    # Create plugin instance with dependencies injected
    try:
        plugin = container.inject(plugin_cls)
        
        # Apply any stored configuration values to the plugin
        if plugin_id in plugin_configs:
            logger.info(f"Applying stored configuration for {plugin_id}: {plugin_configs[plugin_id]}")
            for attr_name, value in plugin_configs[plugin_id].items():
                if hasattr(plugin, attr_name):
                    setattr(plugin, attr_name, value)
                    logger.info(f"Applied stored config {attr_name}={value} to {plugin_id}")
                else:
                    logger.warning(f"Plugin {plugin_id} has no attribute {attr_name}")
    except Exception as e:
        logger.error(f"Error creating plugin instance for {plugin_id}: {str(e)}")
        await mqtt_service.error(plugin_id, f"Error creating plugin instance: {str(e)}")
        return

    # Create task for the plugin
    task = asyncio.create_task(plugin.execute())
    running_tasks[plugin_id] = task

    try:
        # Wait for the plugin to complete
        await task
        await mqtt_service.success(plugin_id, "Plugin completed successfully")
    except asyncio.CancelledError:
        await mqtt_service.info(plugin_id, "Plugin stopped manually", category="stop")
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
            await mqtt_service.error(plugin_id, f"Error at {file_name}:{line_no} → {e}")
        else:
            await mqtt_service.error(plugin_id, f"Error: {str(e)}")
    finally:
        # Clean up
        running_tasks.pop(plugin_id, None)
        await update_switch_state(plugin_id, "OFF")

async def mqtt_listener() -> None:
    """
    Listen for MQTT messages and add them to the processing queue.
    
    This function sets up an MQTT client with a Last Will and Testament message
    to indicate when the service goes offline, then subscribes to relevant topics
    and forwards messages to the processing queue.
    """
    # Set up Last Will and Testament message for service status
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/mealiemate_status/state"
    will_msg = aiomqtt.Will(topic=state_topic, payload="OFF", qos=1, retain=True)

    try:
        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT, will=will_msg, timeout=5) as client:
            # Publish initial online status
            await client.publish(state_topic, payload="ON", retain=True)
            logger.info("MQTT listener started, service status set to ON")

            # Subscribe to control topics
            await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/switch/+/set")
            await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/number/+/set")
            await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/text/+/set")
            await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/button/+/command")
            logger.info("Subscribed to MQTT control topics")

            # Process incoming messages
            async for message in client.messages:
                topic = str(message.topic)
                payload = message.payload.decode()
                logger.debug(f"Received MQTT message: {topic} = {payload}")
                await mqtt_message_queue.put((topic, payload))
    except Exception as e:
        logger.error(f"MQTT listener error: {str(e)}")
        # Re-raise to allow proper shutdown
        raise

async def process_message(topic: str, payload: str, registry: PluginRegistry, container: Container) -> None:
    """
    Process an MQTT message and take appropriate action.
    
    Args:
        topic: MQTT topic of the message
        payload: Decoded payload of the message
        registry: The plugin registry containing all discovered plugins
        container: The dependency injection container
    """
    mqtt_service = container.resolve(MqttService)
    if not mqtt_service:
        logger.error("MQTT service not found in container")
        return
        
    # Extract entity ID from topic
    raw_id = topic.split("/")[-2]  # e.g. "shopping_list_generator_mealplan_length"

    # If topic includes "mealiemate_" as a prefix, remove it
    if raw_id.startswith("mealiemate_"):
        raw_id = raw_id.removeprefix("mealiemate_")

    plugin_id = None
    entity_id = None

    # Find which plugin this message is for
    for candidate_id in registry.get_all_plugins().keys():
        if raw_id.startswith(candidate_id):
            plugin_id = candidate_id
            # Extract the entity ID (part after the plugin ID)
            entity_id = raw_id[len(candidate_id + "_"):]  # e.g. "mealplan_length"
            break

    # Validate plugin ID
    if not plugin_id or plugin_id not in registry.get_all_plugins():
        await mqtt_service.warning("mealiemate", f"Unknown plugin ID in MQTT message: {raw_id}")
        return
    
    # Get the plugin class from the registry
    plugin_cls = registry.get_plugin(plugin_id)
    if not plugin_cls:
        logger.error(f"Plugin {plugin_id} not found in registry")
        await mqtt_service.error("mealiemate", f"Plugin {plugin_id} not found")
        return
        
    # Create plugin instance with dependencies injected
    try:
        plugin = container.inject(plugin_cls)
    except Exception as e:
        logger.error(f"Error creating plugin instance for {plugin_id}: {str(e)}")
        await mqtt_service.error("mealiemate", f"Error creating plugin instance: {str(e)}")
        return
    
    # Handle number updates
    if "number" in topic:
        try:
            # Update the plugin's configuration
            value = int(payload)
            
            # Update the plugin's instance variable based on entity_id
            # This assumes the plugin has instance variables named _entity_id
            attr_name = f"_{entity_id}"
            if hasattr(plugin, attr_name):
                # Update the instance variable
                setattr(plugin, attr_name, value)
                
                # Store in persistent configuration
                if plugin_id not in plugin_configs:
                    plugin_configs[plugin_id] = {}
                plugin_configs[plugin_id][attr_name] = value
                
                await mqtt_service.info(plugin_id, f"Updated number {entity_id} to {value}", category="data")
            else:
                logger.warning(f"Plugin {plugin_id} has no attribute {attr_name}")
                await mqtt_service.warning(plugin_id, f"Unknown number entity: {entity_id}")
        except ValueError:
            await mqtt_service.error(plugin_id, f"Invalid number value received: {payload}")
        except KeyError:
            logger.error(f"Unknown number entity: {entity_id} for plugin {plugin_id}")
        return

    # Handle text updates
    if "text" in topic:
        try:
            # Update the plugin's configuration
            text = str(payload)
            
            # Update the plugin's instance variable based on entity_id
            # This assumes the plugin has instance variables named _entity_id
            attr_name = f"_{entity_id}"
            if hasattr(plugin, attr_name):
                # Update the instance variable
                setattr(plugin, attr_name, text)
                
                # Store in persistent configuration
                if plugin_id not in plugin_configs:
                    plugin_configs[plugin_id] = {}
                plugin_configs[plugin_id][attr_name] = text
                
                await mqtt_service.info(plugin_id, f"Updated text {entity_id} to: {text[:30]}...", category="data")
            else:
                logger.warning(f"Plugin {plugin_id} has no attribute {attr_name}")
                await mqtt_service.warning(plugin_id, f"Unknown text entity: {entity_id}")
        except ValueError:
            await mqtt_service.error(plugin_id, f"Invalid string value received: {payload}")
        except KeyError:
            logger.error(f"Unknown text entity: {entity_id} for plugin {plugin_id}")
        return

    # Handle button commands
    if "button" in topic and payload == "PRESS":
        logger.info(f"Button press received for {plugin_id}_{entity_id}")
        await mqtt_service.info(plugin_id, f"Button {entity_id} pressed", category="data")
        return
        
    # Handle switch commands (ON/OFF)
    if payload == "ON":
        if plugin_id in running_tasks:
            await mqtt_service.info(plugin_id, "Plugin is already running", category="skip")
            return
        await mqtt_service.info(plugin_id, "Starting plugin", category="start")
        asyncio.create_task(execute_plugin(plugin_id, registry, container))
    elif payload == "OFF":
        if plugin_id not in running_tasks:
            await mqtt_service.info(plugin_id, "Plugin is not running", category="skip")
            return
        await mqtt_service.info(plugin_id, "Stopping plugin", category="stop")
        task = running_tasks.pop(plugin_id)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            await mqtt_service.info(plugin_id, "Plugin cancelled or timed out during shutdown", category="stop")
            pass
        
        # Reset progress sensor to 0 with "Stopped" activity when manually stopped
        # Check if this plugin has a progress sensor by looking at its MQTT entities
        plugin_cls = registry.get_plugin(plugin_id)
        if plugin_cls:
            plugin = container.inject(plugin_cls)
            entities = plugin.get_mqtt_entities()
            if "sensors" in entities and "progress" in entities["sensors"]:
                await mqtt_service.update_progress(plugin_id, "progress", 0, "Stopped")
    else:
        await mqtt_service.warning(plugin_id, f"Unknown command: {payload}")

async def mqtt_message_processor(registry: PluginRegistry, container: Container) -> None:
    """
    Process messages from the MQTT message queue.
    
    This function runs in a loop, taking messages from the queue and
    processing them, with error handling and backoff.
    
    Args:
        registry: The plugin registry containing all discovered plugins
        container: The dependency injection container
    """
    mqtt_service = container.resolve(MqttService)
    if not mqtt_service:
        logger.error("MQTT service not found in container")
        return
        
    await mqtt_service.info("mealiemate", "MQTT message processor started", category="start")
    
    while True:
        try:
            # Get a message from the queue with timeout
            topic, payload = await asyncio.wait_for(mqtt_message_queue.get(), timeout=5)
            await process_message(topic, payload, registry, container)
            mqtt_message_queue.task_done()
        except asyncio.TimeoutError:
            # No message received within timeout, just continue
            continue
        except Exception as e:
            # Log any processing errors and continue after a short delay
            logger.error(f"Error processing MQTT message: {str(e)}", exc_info=True)
            await mqtt_service.error("mealiemate", f"Processing error: {str(e)}")
            await asyncio.sleep(1)

async def reset_special_sensors(registry: PluginRegistry, container: Container) -> None:
    """
    Reset all special sensors (feedback, dough_recipe, mealplan) for all plugins.
    
    Args:
        registry: The plugin registry containing all discovered plugins
        container: The dependency injection container
    """
    mqtt_service = container.resolve(MqttService)
    if not mqtt_service:
        logger.error("MQTT service not found in container")
        return
    
    # Special sensor IDs that should be reset
    special_sensor_ids = ["feedback", "dough_recipe", "current_suggestion"]  # Excluding "mealplan" as requested
    
    # Iterate through all plugins
    for plugin_id, plugin_cls in registry.get_all_plugins().items():
        try:
            # Create plugin instance with dependencies injected
            plugin = container.inject(plugin_cls)
            
            # Get MQTT entity configuration from the plugin
            entities = plugin.get_mqtt_entities()
            
            # Check if the plugin has any special sensors
            for sensor_id in special_sensor_ids:
                if "sensors" in entities and sensor_id in entities["sensors"]:
                    logger.info(f"Resetting {sensor_id} sensor for plugin {plugin_id}")
                    await mqtt_service.reset_sensor(plugin_id, sensor_id)
        except Exception as e:
            logger.error(f"Error resetting sensors for plugin {plugin_id}: {str(e)}")

async def check_midnight_reset(registry: PluginRegistry, container: Container) -> None:
    """
    Periodically check if it's midnight and reset special sensors if it is.
    
    Args:
        registry: The plugin registry containing all discovered plugins
        container: The dependency injection container
    """
    mqtt_service = container.resolve(MqttService)
    if not mqtt_service:
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
                await mqtt_service.info("mealiemate", "Midnight detected, resetting special sensors", category="time")
                
                # Reset all special sensors
                await reset_special_sensors(registry, container)
                
                # Update the last reset day
                last_reset_day = now.day
            
            # Check every minute
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in midnight reset check: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

async def send_status_heartbeat() -> None:
    """
    Periodically send a status heartbeat to Home Assistant to keep the device shown as available.
    
    Home Assistant has a timeout for MQTT devices, and if it doesn't receive updates
    periodically, it will mark the device as unavailable. This function sends a status
    update every hour to prevent that from happening.
    """
    state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/mealiemate_status/state"
    
    while True:
        try:
            # Send a heartbeat every hour
            async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
                await client.publish(state_topic, payload="ON", retain=True)
                logger.debug("Sent status heartbeat to Home Assistant")
            
            # Wait for an hour before sending the next heartbeat
            await asyncio.sleep(3600)  # 3600 seconds = 1 hour
        except Exception as e:
            logger.error(f"Error sending status heartbeat: {str(e)}")
            # If there was an error, wait a bit and try again
            await asyncio.sleep(60)  # Wait 1 minute before retrying

async def main() -> None:
    """
    Main entry point for the MealieMate service.
    
    This function:
    1. Sets up the dependency injection container
    2. Discovers and loads plugins
    3. Sets up signal handlers for graceful shutdown
    4. Initializes MQTT entities
    5. Starts the MQTT listener and message processor
    6. Starts the status heartbeat task
    7. Waits for shutdown signal
    8. Performs graceful shutdown
    """
    # Set up dependency injection container
    container = Container()
    container.register(MqttService, MqttServiceImpl())
    container.register(MealieApiService, MealieApiServiceImpl())
    container.register(GptService, GptServiceImpl())
    
    # Set up plugin registry and discover plugins
    registry = PluginRegistry()
    registry.discover_plugins("plugins")
    
    # Get MQTT service for logging
    mqtt_service = container.resolve(MqttService)
    if not mqtt_service:
        logger.error("MQTT service not found in container")
        return
        
    await mqtt_service.info("mealiemate", "MealieMate service starting", category="start")

    # Set up graceful shutdown
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler():
        logger.info("Received shutdown signal")
        # Use asyncio.create_task to run the async function in the signal handler
        asyncio.create_task(mqtt_service.info("mealiemate", "Received shutdown signal"))
        shutdown_event.set()

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        # Set up MQTT entities
        await setup_mqtt_entities(registry, container)

        # Reset all special sensors on startup
        logger.info("Resetting special sensors on service startup")
        await mqtt_service.info("mealiemate", "Resetting special sensors on service startup", category="config")
        await reset_special_sensors(registry, container)
        
        # Start MQTT listener and message processor
        listener_task = asyncio.create_task(mqtt_listener())
        processor_task = asyncio.create_task(mqtt_message_processor(registry, container))
        
        # Start the status heartbeat task
        heartbeat_task = asyncio.create_task(send_status_heartbeat())
        
        # Start the midnight reset task
        midnight_task = asyncio.create_task(check_midnight_reset(registry, container))
        
        await mqtt_service.success("mealiemate", "MealieMate service started successfully")

        # Wait for shutdown signal
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                # Just a timeout, continue waiting
                pass

        # Begin graceful shutdown
        await mqtt_service.info("mealiemate", "Starting graceful shutdown", category="stop")
        
        # Cancel any running plugins
        for plugin_id, task in list(running_tasks.items()):
            await mqtt_service.info(plugin_id, "Cancelling running plugin", category="stop")
            task.cancel()
        
        if running_tasks:
            # Wait for all running plugins to finish (with timeout)
            await asyncio.wait(list(running_tasks.values()), timeout=5)
        
        # Set service status to OFF
        try:
            async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
                state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/mealiemate_status/state"
                await client.publish(state_topic, payload="OFF", retain=True)
                await mqtt_service.info("mealiemate", "Published offline status to MQTT", category="network")
        except Exception as e:
            logger.error(f"Error publishing offline status: {str(e)}")

        # Cancel and wait for background tasks
        for t in (listener_task, processor_task, heartbeat_task, midnight_task):
            t.cancel()
        
        await asyncio.gather(listener_task, processor_task, heartbeat_task, midnight_task, return_exceptions=True)
        
        await mqtt_service.success("mealiemate", "MealieMate service shutdown complete")
        
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}", exc_info=True)
        await mqtt_service.critical("mealiemate", f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
