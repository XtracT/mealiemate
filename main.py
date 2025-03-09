"""
Module: main
------------
Main entry point for the MealieMate application.

This module:
1. Loads all script modules
2. Sets up MQTT entities for Home Assistant integration
3. Handles MQTT message processing for script control
4. Provides graceful shutdown to ensure proper cleanup

Each script is registered with Home Assistant via MQTT discovery and can be
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

import utils.ha_mqtt as ha_mqtt

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

# Track running tasks and message queue
running_tasks: Dict[str, asyncio.Task] = {}
mqtt_message_queue: asyncio.Queue = asyncio.Queue()

# List of script modules to load
SCRIPTS = [
    "recipe_tagger", 
    "meal_planner", 
    "mealplan_fetcher", 
    "shopping_list_generator", 
    "neapolitan_pizza"
]

# Load all script modules
SCRIPT_MAP: Dict[str, Dict[str, Any]] = {}
for script_name in SCRIPTS:
    try:
        module = importlib.import_module(script_name)
        SCRIPT_MAP[module.SCRIPT_CONFIG["id"]] = module.SCRIPT_CONFIG
        logger.info(f"Loaded script module: {script_name}")
    except ImportError as e:
        logger.error(f"Failed to import script module {script_name}: {str(e)}")
    except Exception as e:
        logger.error(f"Error loading script {script_name}: {str(e)}")

async def setup_mqtt_entities() -> None:
    """
    Set up all MQTT entities for Home Assistant discovery.
    
    This registers all switches, sensors, numbers, and text inputs for each script,
    plus a service status indicator for the overall application.
    """
    await ha_mqtt.info("mealiemate", "Setting up MQTT entities for Home Assistant discovery", category="config")
    
    for script_id, script in SCRIPT_MAP.items():
        # Set up switch for enabling/disabling the script
        if script["switch"]:
            await ha_mqtt.setup_mqtt_switch(script_id, SCRIPT_MAP[script_id]["name"])

        # Set up sensors for script output
        for sensor in script["sensors"]:
            await ha_mqtt.setup_mqtt_sensor(
                script_id, 
                script["sensors"][sensor]["id"], 
                script["sensors"][sensor]["name"]
            )

        # Set up number inputs for script configuration
        for number in script.get("numbers", []):
            await ha_mqtt.setup_mqtt_number(
                script_id, 
                script["numbers"][number]["id"], 
                script["numbers"][number]["name"],
                script["numbers"][number]["value"]
            )

        # Set up text inputs for script configuration
        for text in script.get("texts", []):
            await ha_mqtt.setup_mqtt_text(
                script_id, 
                script["texts"][text]["id"], 
                script["texts"][text]["name"],
                script["texts"][text]["text"]
            )

    # Set up overall service status indicator
    await ha_mqtt.setup_mqtt_service_status("mealiemate", "status", "MealieMate Status")
    await ha_mqtt.success("mealiemate", "MQTT entity setup complete")

async def update_switch_state(script_id: str, state: str) -> None:
    """
    Update the state of a script's switch in Home Assistant.
    
    Args:
        script_id: ID of the script
        state: New state ("ON" or "OFF")
    """
    try:
        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            topic = f"{MQTT_DISCOVERY_PREFIX}/switch/{script_id}/state"
            await client.publish(topic, payload=state, retain=True)
            await ha_mqtt.debug(script_id, f"Updated switch state to {state}")
    except Exception as e:
        logger.error(f"Failed to update switch state for {script_id}: {str(e)}")

async def execute_script(script_id: str, script_func: Callable) -> None:
    """
    Execute a script and handle its lifecycle.
    
    Args:
        script_id: ID of the script to execute
        script_func: Function to execute (not used, script is executed from SCRIPT_MAP)
    """
    await ha_mqtt.info(script_id, "Starting script", category="start")
    await update_switch_state(script_id, "ON")

    # Create task for the script
    task = asyncio.create_task(SCRIPT_MAP[script_id]["execute_function"]())
    running_tasks[script_id] = task

    try:
        # Wait for the script to complete
        await task
        await ha_mqtt.success(script_id, "Script completed successfully")
    except asyncio.CancelledError:
        await ha_mqtt.info(script_id, "Script stopped manually", category="stop")
    except Exception as e:
        # Log detailed error information
        logger.error(f"Error in script {script_id}: {str(e)}", exc_info=True)
        
        # Print a detailed traceback to the console
        traceback.print_exc()
        
        # Get file name and line number for quick reference
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_tb:
            file_name = exc_tb.tb_frame.f_code.co_filename
            line_no = exc_tb.tb_lineno
            await ha_mqtt.error(script_id, f"Error at {file_name}:{line_no} → {e}")
        else:
            await ha_mqtt.error(script_id, f"Error: {str(e)}")
    finally:
        # Clean up
        running_tasks.pop(script_id, None)
        await update_switch_state(script_id, "OFF")

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
            await ha_mqtt.info("mealiemate", "MQTT listener started, service status set to ON", category="network")

            # Subscribe to control topics
            await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/switch/+/set")
            await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/number/+/set")
            await client.subscribe(f"{MQTT_DISCOVERY_PREFIX}/text/+/set")
            await ha_mqtt.info("mealiemate", "Subscribed to MQTT control topics", category="network")

            # Process incoming messages
            async for message in client.messages:
                topic = str(message.topic)
                payload = message.payload.decode()
                await ha_mqtt.debug("mealiemate", f"Received MQTT message: {topic} = {payload}", category="network")
                await mqtt_message_queue.put((topic, payload))
    except Exception as e:
        logger.error(f"MQTT listener error: {str(e)}")
        # Re-raise to allow proper shutdown
        raise

async def process_message(topic: str, payload: str) -> None:
    """
    Process an MQTT message and take appropriate action.
    
    Args:
        topic: MQTT topic of the message
        payload: Decoded payload of the message
    """
    # Extract entity ID from topic
    raw_id = topic.split("/")[-2]  # e.g. "shopping_list_generator_mealplan_length"

    # If topic includes "mealiemate_" as a prefix, remove it
    if raw_id.startswith("mealiemate_"):
        raw_id = raw_id.removeprefix("mealiemate_")

    script_id = None
    entity_id = None

    # Find which script this message is for
    for candidate_id in SCRIPT_MAP:
        if raw_id.startswith(candidate_id):
            script_id = candidate_id
            # Extract the entity ID (part after the script ID)
            entity_id = raw_id[len(candidate_id + "_"):]  # e.g. "mealplan_length"
            break

    # Validate script ID
    if not script_id or script_id not in SCRIPT_MAP:
        await ha_mqtt.warning("mealiemate", f"Unknown script ID in MQTT message: {raw_id}")
        return
    
    # Handle number updates
    if "number" in topic:
        try:
            value = int(payload)
            SCRIPT_MAP[script_id]["numbers"][entity_id]["value"] = value
            await ha_mqtt.info(script_id, f"Updated number {entity_id} to {value}", category="data")
        except ValueError:
            await ha_mqtt.error(script_id, f"Invalid number value received: {payload}")
        except KeyError:
            logger.error(f"Unknown number entity: {entity_id} for script {script_id}")
        return

    # Handle text updates
    if "text" in topic:
        try:
            text = str(payload)
            SCRIPT_MAP[script_id]["texts"][entity_id]["text"] = text
            await ha_mqtt.info(script_id, f"Updated text {entity_id} to: {text[:30]}...", category="data")
        except ValueError:
            await ha_mqtt.error(script_id, f"Invalid string value received: {payload}")
        except KeyError:
            logger.error(f"Unknown text entity: {entity_id} for script {script_id}")
        return

    # Handle switch commands (ON/OFF)
    if payload == "ON":
        if script_id in running_tasks:
            await ha_mqtt.info(script_id, "Script is already running", category="skip")
            return
        await ha_mqtt.info(script_id, "Starting script", category="start")
        asyncio.create_task(execute_script(script_id, SCRIPT_MAP[script_id]))
    elif payload == "OFF":
        if script_id not in running_tasks:
            await ha_mqtt.info(script_id, "Script is not running", category="skip")
            return
        await ha_mqtt.info(script_id, "Stopping script", category="stop")
        task = running_tasks.pop(script_id)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            await ha_mqtt.info(script_id, "Script cancelled or timed out during shutdown", category="stop")
            pass
    else:
        await ha_mqtt.warning(script_id, f"Unknown switch command: {payload}")

async def mqtt_message_processor() -> None:
    """
    Process messages from the MQTT message queue.
    
    This function runs in a loop, taking messages from the queue and
    processing them, with error handling and backoff.
    """
    await ha_mqtt.info("mealiemate", "MQTT message processor started", category="start")
    
    while True:
        try:
            # Get a message from the queue with timeout
            topic, payload = await asyncio.wait_for(mqtt_message_queue.get(), timeout=5)
            await process_message(topic, payload)
            mqtt_message_queue.task_done()
        except asyncio.TimeoutError:
            # No message received within timeout, just continue
            continue
        except Exception as e:
            # Log any processing errors and continue after a short delay
            logger.error(f"Error processing MQTT message: {str(e)}", exc_info=True)
            await ha_mqtt.error("mealiemate", f"Processing error: {str(e)}")
            await asyncio.sleep(1)

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
    1. Sets up signal handlers for graceful shutdown
    2. Initializes MQTT entities
    3. Starts the MQTT listener and message processor
    4. Starts the status heartbeat task
    5. Waits for shutdown signal
    6. Performs graceful shutdown
    """
    await ha_mqtt.info("mealiemate", "MealieMate service starting", category="start")

    # Set up graceful shutdown
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler():
        logger.info("Received shutdown signal")
        # Use asyncio.create_task to run the async function in the signal handler
        asyncio.create_task(ha_mqtt.info("mealiemate", "Received shutdown signal"))
        shutdown_event.set()

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        # Set up MQTT entities
        await setup_mqtt_entities()

        # Start MQTT listener and message processor
        listener_task = asyncio.create_task(mqtt_listener())
        processor_task = asyncio.create_task(mqtt_message_processor())
        
        # Start the status heartbeat task
        heartbeat_task = asyncio.create_task(send_status_heartbeat())
        
        await ha_mqtt.success("mealiemate", "MealieMate service started successfully")

        # Wait for shutdown signal
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                # Just a timeout, continue waiting
                pass

        # Begin graceful shutdown
        await ha_mqtt.info("mealiemate", "Starting graceful shutdown", category="stop")
        
        # Cancel any running scripts
        for script_id, task in list(running_tasks.items()):
            await ha_mqtt.info(script_id, "Cancelling running script", category="stop")
            task.cancel()
        
        if running_tasks:
            # Wait for all running scripts to finish (with timeout)
            await asyncio.wait(list(running_tasks.values()), timeout=5)
        
        # Set service status to OFF
        try:
            async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
                state_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/mealiemate_status/state"
                await client.publish(state_topic, payload="OFF", retain=True)
                await ha_mqtt.info("mealiemate", "Published offline status to MQTT", category="network")
        except Exception as e:
            logger.error(f"Error publishing offline status: {str(e)}")

        # Cancel and wait for background tasks
        for t in (listener_task, processor_task, heartbeat_task):
            t.cancel()
        
        await asyncio.gather(listener_task, processor_task, heartbeat_task, return_exceptions=True)
        
        await ha_mqtt.success("mealiemate", "MealieMate service shutdown complete")
        
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}", exc_info=True)
        await ha_mqtt.critical("mealiemate", f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
