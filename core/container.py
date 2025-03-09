"""
Module: container
---------------
Provides a simple dependency injection container for managing service instances.

This module implements a Container class that can register service implementations
for interfaces and inject them into classes that require them.
"""

import inspect
import logging
from typing import Dict, Any, Type, Optional, get_type_hints

# Configure logging
logger = logging.getLogger(__name__)

class Container:
    """Simple dependency injection container."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
    
    def register(self, interface: Type, implementation: Any) -> None:
        """
        Register a service implementation for an interface.
        
        Args:
            interface: The interface class
            implementation: The implementation instance
        """
        interface_name = interface.__name__
        self._services[interface_name] = implementation
        logger.debug(f"Registered service: {interface_name}")
    
    def resolve(self, interface: Type) -> Optional[Any]:
        """
        Resolve a service implementation for an interface.
        
        Args:
            interface: The interface class
            
        Returns:
            The implementation instance if registered, None otherwise
        """
        interface_name = interface.__name__
        service = self._services.get(interface_name)
        
        if service is None:
            logger.warning(f"No implementation registered for interface: {interface_name}")
            
        return service
    
    def inject(self, cls: Type) -> Any:
        """
        Create an instance of a class with dependencies injected.
        
        This method inspects the class's __init__ method and injects
        registered services for each parameter with a type annotation.
        
        Args:
            cls: The class to instantiate
            
        Returns:
            An instance of the class with dependencies injected
            
        Raises:
            ValueError: If a required dependency is not registered
        """
        if not hasattr(cls, '__init__'):
            return cls()
        
        # Get the signature of the __init__ method
        init_signature = inspect.signature(cls.__init__)
        
        # Prepare arguments for instantiation
        args = {}
        
        # Process each parameter
        for param_name, param in init_signature.parameters.items():
            if param_name == 'self':
                continue
            
            # If the parameter has a type annotation, try to resolve it
            if param.annotation != inspect.Parameter.empty:
                service = self.resolve(param.annotation)
                
                if service:
                    args[param_name] = service
                elif param.default == inspect.Parameter.empty:
                    # If the parameter is required and no service is registered, raise an error
                    raise ValueError(f"No implementation registered for required dependency: {param.annotation.__name__}")
            
        # Create and return the instance
        instance = cls(**args)
        logger.debug(f"Created instance of {cls.__name__} with injected dependencies")
        return instance
