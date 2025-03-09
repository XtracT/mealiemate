"""
Module: plugin_registry
----------------------
Provides functionality for discovering, registering, and managing plugins.

This module implements the PluginRegistry class, which is responsible for:
1. Discovering plugins in the plugins directory
2. Registering plugins with the system
3. Providing access to registered plugins
"""

import importlib
import inspect
import logging
import os
import pkgutil
import sys
from typing import Dict, Type, List, Optional, Any

from core.plugin import Plugin

# Configure logging
logger = logging.getLogger(__name__)

class PluginRegistry:
    """Registry for discovering and loading plugins."""
    
    def __init__(self):
        self._plugins: Dict[str, Type[Plugin]] = {}
    
    def register(self, plugin_cls: Type[Plugin]) -> None:
        """
        Register a plugin class.
        
        Args:
            plugin_cls: The plugin class to register
        """
        # Get the plugin ID from the class method
        plugin_id = plugin_cls.get_plugin_id()
        
        if plugin_id in self._plugins:
            logger.warning(f"Plugin with ID '{plugin_id}' is already registered. Overwriting.")
            
        self._plugins[plugin_id] = plugin_cls
        logger.info(f"Registered plugin: {plugin_id} ({plugin_cls.__name__})")
    
    def get_plugin(self, plugin_id: str) -> Optional[Type[Plugin]]:
        """
        Get a plugin by ID.
        
        Args:
            plugin_id: The ID of the plugin to retrieve
            
        Returns:
            The plugin class if found, None otherwise
        """
        return self._plugins.get(plugin_id)
    
    def get_all_plugins(self) -> Dict[str, Type[Plugin]]:
        """
        Get all registered plugins.
        
        Returns:
            A dictionary mapping plugin IDs to plugin classes
        """
        return self._plugins
    
    def discover_plugins(self, package_name: str = "plugins") -> None:
        """
        Discover plugins in the specified package.
        
        This method scans the specified package for modules and looks for
        classes that implement the Plugin interface.
        
        Args:
            package_name: The name of the package to scan for plugins
        """
        logger.info(f"Discovering plugins in package: {package_name}")
        
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.error(f"Could not import package: {package_name}")
            return
        
        # Ensure the package directory is in sys.path
        if package.__path__[0] not in sys.path:
            sys.path.append(package.__path__[0])
        
        # Discover all modules in the package
        for _, name, is_pkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(name)
                
                # Find all classes in the module that implement Plugin
                for item_name, item in inspect.getmembers(module, inspect.isclass):
                    if issubclass(item, Plugin) and item != Plugin:
                        self.register(item)
                        
            except ImportError as e:
                logger.error(f"Error importing module {name}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing module {name}: {str(e)}")
        
        logger.info(f"Discovered {len(self._plugins)} plugins")
