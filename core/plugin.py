"""
Module: plugin
-------------
Defines the base Plugin interface that all plugins must implement.

This module provides the foundation for the plugin architecture, defining
the contract that plugins must adhere to for proper integration with the system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Awaitable, ClassVar

class Plugin(ABC):
    """Base interface for all plugins."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for the plugin."""
        pass
    
    @classmethod
    @abstractmethod
    def get_plugin_id(cls) -> str:
        """
        Get the unique identifier for this plugin class.
        
        This class method is used by the PluginRegistry to identify plugins
        without having to instantiate them.
        
        Returns:
            The unique identifier for this plugin
        """
        pass
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for the plugin."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the plugin does."""
        pass
    
    @abstractmethod
    async def execute(self) -> None:
        """Execute the plugin's main functionality."""
        pass
    
    @abstractmethod
    def get_mqtt_entities(self) -> Dict[str, Any]:
        """
        Get MQTT entities configuration for Home Assistant.
        
        Returns:
            A dictionary containing the MQTT entity configuration for this plugin,
            including switches, sensors, numbers, and text inputs.
        """
        pass
