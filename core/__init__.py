"""
Core package for MealieMate.

This package provides the foundation for the plugin architecture, including:
- Plugin interface
- Plugin registry
- Service interfaces
- Dependency injection container
"""

from core.plugin import Plugin
from core.plugin_registry import PluginRegistry
from core.container import Container
from core.services import MqttService, MealieApiService, GptService

__all__ = [
    'Plugin',
    'PluginRegistry',
    'Container',
    'MqttService',
    'MealieApiService',
    'GptService',
]
