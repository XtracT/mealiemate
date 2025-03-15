# MealieMate Architecture

## 1. Project Overview

MealieMate is a Home Assistant integration that enhances meal planning and grocery shopping by interacting with [Mealie](https://mealie.io/), a self-hosted recipe management system, and optionally with a Large Language Model (LLM) like GPT for intelligent assistance. It provides features such as:

*   Fetching upcoming meal plans from Mealie.
*   Generating consolidated and categorized shopping lists.
*   Using GPT to refine and optimize shopping lists.
*   Creating new shopping lists in Mealie.
*   Suggesting meal plans based on user preferences and available ingredients.
*   Automatically tagging recipes.
*   Merging similar ingredients in recipes.

## 2. Architecture Overview

MealieMate is built using a plugin-based architecture with clear separation of concerns. This allows for easy extension and customization of functionality. The core of the application consists of several key components:

*   **Application (core/app.py):** The main application class that initializes all components, sets up signal handlers, manages background tasks, and handles graceful shutdown.

*   **Dependency Injection (core/container.py):** A simple dependency injection container manages dependencies between different components, promoting loose coupling.

*   **Plugin Registry (core/plugin_registry.py):** Discovers and registers plugins located in the `plugins/` directory.

*   **Plugin Manager (core/plugin_manager.py):** Manages plugin lifecycle (starting, stopping), tracks running plugin instances, and handles plugin configurations.

*   **Message Handler (core/message_handler.py):** Processes MQTT messages and dispatches them to the appropriate handlers.

*   **System Service (core/system_service.py):** Handles system-level tasks such as setting up MQTT entities, resetting sensors, and sending status heartbeats.

*   **Service Abstraction (core/services.py):** Abstract base classes define interfaces for core services (e.g., `MqttService`, `MealieApiService`, `GptService`), allowing for different implementations if needed.

The application flow is generally as follows:

1.  The `main.py` script initializes the MealieMateApp, which sets up the dependency injection container, registers services, and discovers plugins.
2.  The SystemService sets up MQTT entities (switches, sensors, numbers, text inputs, buttons) for each plugin in Home Assistant via MQTT discovery.
3.  The MealieMateApp starts an MQTT listener that continuously listens for incoming messages from Home Assistant (e.g., user input, switch toggles).
4.  Incoming messages are processed by the MqttMessageHandler, which dispatches them to the appropriate handlers.
5.  When a plugin is enabled via its switch in Home Assistant, the PluginManager starts the plugin's `execute` method in a separate task.
6.  Plugins interact with external services (Mealie, GPT) through the provided service interfaces.
7.  Plugins update Home Assistant entities (e.g., sensors) to display information or provide feedback to the user.

## 3. Directory Structure

```
mealiemate/
├── core/               # Core application logic
│   ├── __init__.py
│   ├── app.py          # Main application class
│   ├── container.py    # Dependency injection container
│   ├── message_handler.py # MQTT message handling logic
│   ├── plugin.py       # Abstract base class for plugins
│   ├── plugin_manager.py # Plugin lifecycle management
│   ├── plugin_registry.py # Plugin discovery and registration
│   ├── services.py     # Abstract base classes for services
│   └── system_service.py # System-level tasks
├── plugins/            # Individual plugins
│   ├── __init__.py
│   ├── ingredient_merger.py
│   ├── meal_planner.py
│   ├── mealplan_fetcher.py
│   ├── neapolitan_pizza.py
│   ├── recipe_tagger.py
│   └── shopping_list_generator.py
├── services/           # Concrete service implementations
│   ├── __init__.py
│   ├── gpt_service.py
│   ├── mealie_api_service.py
│   └── mqtt_service.py
├── utils/              # Utility functions
│   ├── gpt_utils.py
│   ├── ha_mqtt.py      # MQTT helper functions for Home Assistant integration
│   └── mealie_api.py
├── fonts/              # (Optional) Custom fonts
├── main.py             # Main entry point
├── requirements.txt    # Project dependencies
├── Dockerfile          # Docker configuration
├── .env                # Environment variables (API keys, etc.)
├── README.md           # Project README
└── LICENSE
└── home_assistant_cards.md # Example Home Assistant card configurations
└── shopping_list_generator_card.md # Example Home Assistant card configuration
└── architecture.md     # This file
```

*   **`core/`**: Contains the core application logic, including the application class, dependency injection container, plugin base class, plugin registry, plugin manager, message handler, system service, and service interfaces.
*   **`plugins/`**:  Holds individual plugins, each implementing the `Plugin` interface.
*   **`services/`**: Contains concrete implementations of the service interfaces defined in `core/services.py`.
*   **`utils/`**: Provides utility functions, including helpers for MQTT communication and interaction with Mealie and GPT.
*   **`main.py`**: The main entry point of the application. It initializes the MealieMateApp, which sets up the system and starts the application.

## 4. Development Workflow

### 4.1. Component Responsibilities

The MealieMate architecture is designed around clear separation of concerns. Each component has a specific responsibility:

*   **MealieMateApp (core/app.py):** Initializes and coordinates all components. It's responsible for starting and stopping the application, setting up signal handlers, and managing background tasks.

*   **PluginRegistry (core/plugin_registry.py):** Discovers and registers plugins. It scans the `plugins/` directory for classes that implement the `Plugin` interface and makes them available to the rest of the system.

*   **PluginManager (core/plugin_manager.py):** Manages plugin lifecycle. It's responsible for starting and stopping plugins, tracking running plugin instances, and managing plugin configurations.

*   **MqttMessageHandler (core/message_handler.py):** Processes MQTT messages. It parses incoming messages, identifies which plugin they're for, and dispatches them to the appropriate handlers.

*   **SystemService (core/system_service.py):** Handles system-level tasks. It's responsible for setting up MQTT entities, resetting sensors, sending status heartbeats, and checking for midnight to reset sensors.

*   **Container (core/container.py):** Manages dependencies. It's responsible for registering service implementations and injecting them into components that need them.

*   **Services (core/services.py):** Define service interfaces. These abstract base classes define the contract that service implementations must adhere to.

### 4.2. Development Process

When developing for MealieMate, follow these steps:

1. **Understand the Architecture:** Familiarize yourself with the components and their responsibilities. This will help you understand where your changes should go.

2. **Identify the Component to Modify:** Based on the feature or bug you're working on, identify which component(s) need to be modified. If you're adding a new feature, it might be a new plugin or an enhancement to an existing one.

3. **Make Targeted Changes:** Make changes only to the components that need to be modified. Avoid making changes that cross component boundaries unless absolutely necessary.

4. **Follow the SOLID Principles:** Ensure your changes adhere to the SOLID principles (see section 5.1).

5. **Test Your Changes:** Test your changes thoroughly to ensure they work as expected and don't break existing functionality.

6. **Update Documentation:** Update this architecture document if your changes affect the overall architecture or add new components.

### 4.3. Common Development Tasks

#### Adding a New Plugin

See section 6 for detailed instructions on adding a new plugin.

#### Modifying an Existing Plugin

1. Identify the plugin you want to modify.
2. Make changes to the plugin's code, ensuring you follow the plugin guidelines in section 5.2.
3. Test your changes by running the application and interacting with the plugin through Home Assistant.

#### Adding a New Service

1. Define the service interface in `core/services.py` as an abstract base class.
2. Implement the service in a new file in the `services/` directory.
3. Register the service implementation in the `initialize` method of `core/app.py`.

#### Modifying an Existing Service

1. Identify the service you want to modify.
2. Make changes to the service implementation, ensuring you follow the service guidelines in section 5.3.
3. If you're changing the service interface, ensure all implementations are updated to match.

#### Adding a New System Feature

1. Identify which component should handle the feature.
2. If it's a system-level feature, add it to `core/system_service.py`.
3. If it's related to plugin management, add it to `core/plugin_manager.py`.
4. If it's related to message handling, add it to `core/message_handler.py`.
5. If it doesn't fit into any existing component, consider creating a new component.

## 5. Coding Guidelines

### 5.1. General Principles

*   **SOLID:** Adhere to the SOLID principles of object-oriented design:
    * **Single Responsibility:** Each class should have only one reason to change.
    * **Open/Closed:** Classes should be open for extension but closed for modification.
    * **Liskov Substitution:** Subtypes must be substitutable for their base types.
    * **Interface Segregation:** Clients should not be forced to depend on methods they do not use.
    * **Dependency Inversion:** Depend on abstractions, not concretions.

*   **KISS:** Keep It Simple, Stupid. Favor simple, straightforward solutions over complex ones.

*   **YAGNI:** You Ain't Gonna Need It. Avoid adding functionality until it's actually needed.

*   **DRY:** Don't Repeat Yourself. Avoid code duplication; extract common logic into reusable functions or classes.

### 5.2. Plugins

*   **Inheritance:** All plugins **must** inherit from the `core.plugin.Plugin` abstract base class.

*   **Interface Implementation:** Plugins **must** implement all abstract methods defined in the `Plugin` base class (`id`, `get_plugin_id`, `name`, `description`, `execute`, `get_mqtt_entities`).
*   **Sensor Reset:** Plugins can optionally define a `reset_sensors` attribute, which is a list of sensor IDs that should be reset when the plugin is initialized and every midnight.

*   **Single Responsibility:** Each plugin should have a single, well-defined responsibility. Avoid creating plugins that do too many things.

*   **Service Interaction:** Plugins should interact with external services (Mealie, GPT, MQTT) through the provided service interfaces defined in `core/services.py`. Do **not** directly interact with external APIs or libraries.

*   **MQTT Communication:**
    *   Plugins define their MQTT entities (switches, sensors, etc.) in the `get_mqtt_entities` method.
    *   Use the provided `MqttService` methods (e.g., `log`, `info`, `warning`, `error`, `success`, `gpt_decision`, `progress`, `update_progress`, `set_switch_state`, `reset_sensor`) for all MQTT communication.

*   **No `aiomqtt` Import:** Plugins **must not** directly import or use the `aiomqtt` library. All MQTT communication must be done through the `MqttService`. This ensures consistent MQTT handling and simplifies testing.

*   **Logging:** Use the provided logging functions in `MqttService` (e.g., `info`, `warning`, `error`) for consistent logging with appropriate prefixes and categories.

*   **Configuration:** Plugin configuration should be handled through instance variables, which can be updated via MQTT messages (using number, text, or switch entities). The PluginManager will automatically store and apply these configurations.

*   **Error Handling:** Plugins should handle expected errors gracefully (e.g., network errors when fetching data from Mealie). Use `try...except` blocks and log errors using the provided logging functions.

### 5.3. Services

*   **Abstract Base Classes:** Services should be defined as abstract base classes in `core/services.py`, defining the interface for interacting with the service.

*   **Concrete Implementations:** Concrete implementations of services should be placed in the `services/` directory.

*   **Independence:** Services should be designed to be independent and reusable. They should not depend on specific plugins.

*   **Consistency:** Service implementations should provide consistent behavior. For example, all logging methods in `MqttService` should follow the same pattern.

*   **Error Handling:** Service implementations should handle errors gracefully and provide meaningful error messages.

## 6. Adding New Plugins

To add a new plugin:

1.  **Create a new Python file:** Create a new `.py` file in the `plugins/` directory. The filename should be descriptive of the plugin's functionality (e.g., `my_new_plugin.py`).

2.  **Implement the `Plugin` interface:** Create a class that inherits from `core.plugin.Plugin` and implements all abstract methods:
    *   `id`: A unique string identifier for the plugin.
    *   `get_plugin_id`: A class method that returns the same unique identifier.
    *   `name`: A human-readable name for the plugin.
    *   `description`: A brief description of the plugin's functionality.
    *   `execute`: The main logic of the plugin. This method will be called when the plugin is enabled.
    *   `get_mqtt_entities`: Returns a dictionary defining the MQTT entities (switches, sensors, etc.) for the plugin.

3.  **Register Dependencies:** If the plugin uses any of the core services (e.g., `MqttService`, `MealieApiService`, `GptService`), inject them through the constructor using type hints. The dependency injection container will automatically provide the correct implementations.

4.  **Implement Plugin Logic:** Write the code for the plugin's functionality within the `execute` method. Use the provided services to interact with external systems.

5.  **Add MQTT Entities:** Define the MQTT entities for the plugin in the `get_mqtt_entities` method. This will automatically register the entities with Home Assistant.

6.  **Restart MealieMate:** Restart the MealieMate service for the new plugin to be discovered and loaded.

### 6.1. Plugin Template

Here's a template for a new plugin:

```python
"""
Module: my_new_plugin
--------------------
Description of what this plugin does.
"""

import logging
from typing import Dict, Any

from core.plugin import Plugin
from core.services import MqttService, MealieApiService, GptService

# Configure logging
logger = logging.getLogger(__name__)

class MyNewPlugin(Plugin):
    """Plugin for [description of functionality]."""
    
    def __init__(self, mqtt_service: MqttService, mealie_service: MealieApiService, gpt_service: GptService):
        """
        Initialize the plugin.
        
        Args:
            mqtt_service: Service for MQTT communication
            mealie_service: Service for Mealie API interaction
            gpt_service: Service for GPT interaction
        """
        self._mqtt = mqtt_service
        self._mealie = mealie_service
        self._gpt = gpt_service
        
        # Configuration
        self._some_config = 10  # Default value
    
    @property
    def id(self) -> str:
        """Unique identifier for the plugin."""
        return self.get_plugin_id()
    
    @classmethod
    def get_plugin_id(cls) -> str:
        """
        Get the unique identifier for this plugin class.
        
        Returns:
            The unique identifier for this plugin
        """
        return "my_new_plugin"
    
    @property
    def name(self) -> str:
        """Human-readable name for the plugin."""
        return "My New Plugin"
    
    @property
    def description(self) -> str:
        """Description of what the plugin does."""
        return "Description of what this plugin does."
    
    def get_mqtt_entities(self) -> Dict[str, Any]:
        """
        Get MQTT entities configuration for Home Assistant.
        
        Returns:
            A dictionary containing the MQTT entity configuration for this plugin.
        """
        return {
            "switch": True,  # Main switch for enabling/disabling the plugin
            "sensors": {
                "feedback": {"id": "feedback", "name": "Feedback"},
                "progress": {"id": "progress", "name": "Progress"},
            },
            "numbers": {
                "some_config": {
                    "id": "some_config",
                    "name": "Some Configuration",
                    "value": self._some_config,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                }
            }
        }
    
    async def execute(self) -> None:
        """Execute the plugin's main functionality."""
        try:
            # Log information
            await self._mqtt.info(self.id, f"Starting with configuration: {self._some_config}", category="start")
            
            # Initialize progress - no need to call setup_mqtt_progress, the SystemService handles this
            await self._mqtt.update_progress(self.id, "progress", 0, "Starting")
            
            # Implement your plugin logic here
            # ...
            
            # Update progress
            await self._mqtt.update_progress(self.id, "progress", 50, "Processing")
            
            # More plugin logic
            # ...
            
            # Complete
            await self._mqtt.success(self.id, "Plugin completed successfully")
            await self._mqtt.update_progress(self.id, "progress", 100, "Finished")
            
        except Exception as e:
            # Log any errors
            logger.error(f"Error in plugin: {str(e)}", exc_info=True)
            await self._mqtt.error(self.id, f"Error: {str(e)}")
            await self._mqtt.update_progress(self.id, "progress", 100, "Error")
```

### 6.2. Important Notes for Plugin Development

1. **Progress Sensor Setup**: Do not call `setup_mqtt_progress` in your plugin's `execute` method. The SystemService now handles setting up all MQTT entities, including progress sensors.

2. **Button Event Handling**: The MqttMessageHandler uses a generic approach for handling button events. If your plugin needs to handle button events, use the `_user_decision_received` event pattern as shown in the ingredient_merger.py and shopping_list_generator.py plugins.

3. **No Setup Method Needed**: Plugins no longer need a `setup` method to register MQTT entities. The SystemService handles this automatically.

## 7. Testing

(Currently, there is no specific testing framework set up. This is an area for future improvement.)

## 8. Conclusion

The MealieMate architecture is designed to be modular, extensible, and maintainable. By following the guidelines in this document, you can ensure that your contributions to the project maintain these qualities.

Key takeaways:

*   **Separation of Concerns:** Each component has a specific responsibility.
*   **Dependency Injection:** Dependencies are injected rather than created directly.
*   **Plugin-Based Architecture:** New functionality can be added by creating new plugins.
*   **Service Abstraction:** External services are accessed through abstract interfaces.

By adhering to these principles, MealieMate can continue to evolve while maintaining a clean and maintainable codebase.
