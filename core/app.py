"""
Module: app
----------
Main application class for MealieMate.

This module implements the MealieMateApp class, which is responsible for:
1. Initializing all components
2. Setting up signal handlers
3. Starting and managing background tasks
4. Handling graceful shutdown
"""

import asyncio
import logging
import signal
import os
from typing import Dict, Any, List, Optional, Set

from core.plugin_registry import PluginRegistry
from core.container import Container
from core.services import MqttService, MealieApiService, GptService
from core.message_handler import MqttMessageHandler
from core.plugin_manager import PluginManager
from core.system_service import SystemService
from services.mqtt_service import MqttServiceImpl
from services.mealie_api_service import MealieApiServiceImpl
from services.gpt_service import GptServiceImpl

# Configure logging
logger = logging.getLogger(__name__)

class MealieMateApp:
    """Main application class for MealieMate."""
    
    def __init__(self):
        """Initialize the MealieMate application."""
        self._container = None
        self._registry = None
        self._plugin_manager = None
        self._system_service = None
        self._message_handler = None
        self._background_tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._mqtt_message_queue = asyncio.Queue()
    
    async def initialize(self) -> None:
        """Initialize all components."""
        # Set up dependency injection container
        self._container = Container()
        self._container.register(MqttService, MqttServiceImpl())
        self._container.register(MealieApiService, MealieApiServiceImpl())
        self._container.register(GptService, GptServiceImpl())
        
        # Set up plugin registry and discover plugins
        self._registry = PluginRegistry()
        self._registry.discover_plugins("plugins")
        
        # Get MQTT service for logging
        mqtt_service = self._container.resolve(MqttService)
        if not mqtt_service:
            logger.error("MQTT service not found in container")
            return
            
        await mqtt_service.info("mealiemate", "MealieMate service initializing", category="start")
        
        # Create plugin manager
        self._plugin_manager = PluginManager(self._registry, self._container, mqtt_service)
        
        # Create system service
        self._system_service = SystemService(self._registry, self._container)
        
        # Create message handler
        self._message_handler = MqttMessageHandler(self._registry, self._container, self._plugin_manager)
        self._container.register(MqttMessageHandler, self._message_handler)
        
        # Set up signal handlers
        self._setup_signal_handlers()
        
        await mqtt_service.info("mealiemate", "MealieMate service initialized", category="start")
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        
        def _signal_handler():
            logger.info("Received shutdown signal")
            # Use asyncio.create_task to run the async function in the signal handler
            mqtt_service = self._container.resolve(MqttService)
            if mqtt_service:
                asyncio.create_task(mqtt_service.info("mealiemate", "Received shutdown signal"))
            self._shutdown_event.set()
        
        # Register signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    
    async def start(self) -> None:
        """Start the application."""
        mqtt_service = self._container.resolve(MqttService)
        if not mqtt_service:
            logger.error("MQTT service not found in container")
            return
            
        try:
            # Set up MQTT entities
            await self._system_service.setup_mqtt_entities()
            
            # Reset all special sensors on startup
            logger.debug("Resetting special sensors on service startup")
            await mqtt_service.info("mealiemate", "Resetting special sensors on service startup", category="config")
            await self._system_service.reset_special_sensors()
            
            # Start MQTT listener and message processor
            listener_task = asyncio.create_task(self._mqtt_listener())
            self._background_tasks.append(listener_task)
            
            processor_task = asyncio.create_task(self._mqtt_message_processor())
            self._background_tasks.append(processor_task)
            
            # Start the status heartbeat task
            heartbeat_task = await self._system_service.start_heartbeat_task()
            self._background_tasks.append(heartbeat_task)
            
            # Start the midnight reset task
            midnight_task = await self._system_service.start_midnight_reset_task()
            self._background_tasks.append(midnight_task)
            
            await mqtt_service.success("mealiemate", "MealieMate service started successfully")
            
            # Wait for shutdown signal
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=10)
                except asyncio.TimeoutError:
                    # Just a timeout, continue waiting
                    pass
            
            # Begin graceful shutdown
            await self.shutdown()
            
        except Exception as e:
            logger.critical(f"Fatal error in application: {str(e)}", exc_info=True)
            if mqtt_service:
                await mqtt_service.critical("mealiemate", f"Fatal error: {str(e)}")
    
    async def shutdown(self) -> None:
        """Perform graceful shutdown."""
        mqtt_service = self._container.resolve(MqttService)
        if mqtt_service:
            await mqtt_service.info("mealiemate", "Starting graceful shutdown", category="stop")
        
        # Get list of running plugins
        running_plugins = self._plugin_manager.get_running_plugins()
        
        # Stop all running plugins
        for plugin_id in running_plugins:
            if mqtt_service:
                await mqtt_service.info(plugin_id, "Cancelling running plugin", category="stop")
            await self._plugin_manager.stop_plugin(plugin_id)
        
        # Set service status to OFF
        if mqtt_service:
            await mqtt_service.set_switch_state("mealiemate_status", "OFF")
            await mqtt_service.info("mealiemate", "Published offline status to MQTT", category="network")
        
        # Stop system service tasks
        await self._system_service.stop_all_tasks()
        
        # Cancel and wait for background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        self._background_tasks.clear()
        
        if mqtt_service:
            await mqtt_service.success("mealiemate", "MealieMate service shutdown complete")
    
    async def _mqtt_listener(self) -> None:
        """
        Listen for MQTT messages and add them to the processing queue.
        
        This function sets up an MQTT client with a Last Will and Testament message
        to indicate when the service goes offline, then subscribes to relevant topics
        and forwards messages to the processing queue.
        """
        mqtt_service = self._container.resolve(MqttService)
        if not mqtt_service:
            logger.error("MQTT service not found in container")
            return
        
        # Get MQTT broker and port from environment variables
        mqtt_broker = os.getenv("MQTT_BROKER")
        mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        mqtt_discovery_prefix = "homeassistant"
        
        if not mqtt_broker:
            logger.error("MQTT_BROKER not found in environment variables")
            return
        
        # Set up Last Will and Testament message for service status
        state_topic = f"{mqtt_discovery_prefix}/binary_sensor/mealiemate_status/state"
        
        try:
            import aiomqtt
            will_msg = aiomqtt.Will(topic=state_topic, payload="OFF", qos=1, retain=True)
            
            async with aiomqtt.Client(mqtt_broker, mqtt_port, will=will_msg, timeout=5) as client:
                # Publish initial online status
                await client.publish(state_topic, payload="ON", retain=True)
                logger.info("MQTT service online")
                
                # Subscribe to control topics
                await client.subscribe(f"{mqtt_discovery_prefix}/switch/+/set")
                await client.subscribe(f"{mqtt_discovery_prefix}/number/+/set")
                await client.subscribe(f"{mqtt_discovery_prefix}/text/+/set")
                await client.subscribe(f"{mqtt_discovery_prefix}/button/+/command")
                logger.debug("Subscribed to MQTT control topics")
                
                # Process incoming messages
                async for message in client.messages:
                    topic = str(message.topic)
                    payload = message.payload.decode()
                    logger.debug(f"Received MQTT message: {topic} = {payload}")
                    await self._mqtt_message_queue.put((topic, payload))
        except asyncio.CancelledError:
            logger.info("MQTT listener task cancelled")
        except Exception as e:
            logger.error(f"MQTT listener error: {str(e)}")
    
    async def _mqtt_message_processor(self) -> None:
        """
        Process messages from the MQTT message queue.
        
        This function runs in a loop, taking messages from the queue and
        processing them, with error handling and backoff.
        """
        mqtt_service = self._container.resolve(MqttService)
        if not mqtt_service:
            logger.error("MQTT service not found in container")
            return
            
        await mqtt_service.info("mealiemate", "MQTT message processor started", category="start")
        
        while True:
            try:
                # Get a message from the queue with timeout
                topic, payload = await asyncio.wait_for(self._mqtt_message_queue.get(), timeout=5)
                await self._message_handler.process_message(topic, payload)
                self._mqtt_message_queue.task_done()
            except asyncio.CancelledError:
                logger.info("MQTT message processor task cancelled")
                break
            except asyncio.TimeoutError:
                # No message received within timeout, just continue
                continue
            except Exception as e:
                # Log any processing errors and continue after a short delay
                logger.error(f"Error processing MQTT message: {str(e)}", exc_info=True)
                if mqtt_service:
                    await mqtt_service.error("mealiemate", f"Processing error: {str(e)}")
                await asyncio.sleep(1)