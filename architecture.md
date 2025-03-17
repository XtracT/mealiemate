# MealieMate Architecture

## 1. Project Overview

MealieMate is a Home Assistant integration that enhances meal planning and grocery shopping by interacting with [Mealie](https://mealie.io/), a self-hosted recipe management system, and optionally with a Large Language Model (LLM) like GPT for intelligent assistance. It provides features such as:

* Fetching upcoming meal plans from Mealie
* Generating consolidated and categorized shopping lists
* Using GPT to refine and optimize shopping lists
* Creating new shopping lists in Mealie
* Suggesting meal plans based on user preferences
* Automatically tagging recipes
* Merging similar ingredients in recipes

## 2. Architecture Overview

MealieMate uses a plugin-based architecture with clear separation of concerns, allowing for easy extension and customization. The core components are:

* **Application (core/app.py):** Initializes components, manages background tasks, and handles shutdown
* **Dependency Injection (core/container.py):** Manages dependencies between components
* **Plugin Registry (core/plugin_registry.py):** Discovers and registers plugins
* **Plugin Manager (core/plugin_manager.py):** Manages plugin lifecycle and configurations, maintains centralized plugin instances
* **Message Handler (core/message_handler.py):** Processes MQTT messages and dispatches them
* **System Service (core/system_service.py):** Handles system-level tasks like MQTT entity setup
* **Service Interfaces (core/services.py):** Define contracts for core services

### Application Flow

1. `main.py` initializes MealieMateApp, which sets up the container, registers services, and discovers plugins
2. The app processes retained MQTT messages to load user configurations
3. SystemService sets up MQTT entities for each plugin in Home Assistant
4. MealieMateApp starts an MQTT listener for incoming messages
5. When a plugin is enabled, PluginManager starts the plugin's execution
6. Plugins interact with external services and update Home Assistant entities

## 3. Directory Structure

```
mealiemate/
├── core/               # Core application logic
│   ├── app.py          # Main application class
│   ├── container.py    # Dependency injection container
│   ├── message_handler.py # MQTT message handling
│   ├── plugin.py       # Plugin base class
│   ├── plugin_manager.py # Plugin lifecycle management
│   ├── plugin_registry.py # Plugin discovery
│   ├── services.py     # Service interfaces
│   └── system_service.py # System-level tasks
├── plugins/            # Individual plugins
├── services/           # Service implementations
├── utils/              # Utility functions
├── main.py             # Entry point
└── [other files]       # Configuration, documentation, etc.
```

## 4. Key Components

### 4.1. Plugin Management

The PluginManager is responsible for:

* **Plugin Lifecycle:** Starting and stopping plugins
* **Instance Management:** Maintaining a centralized registry of plugin instances
* **Configuration:** Storing and applying plugin configurations

The centralized plugin instance management ensures that:

* Only one instance of each plugin exists at any time
* All instances have the latest configuration values
* Configuration changes are consistently applied across the system

When a plugin configuration is updated via MQTT:
1. The message handler processes the message
2. The plugin manager stores the configuration
3. The configuration is applied to the plugin instance
4. Any component that uses the plugin instance gets the updated configuration

### 4.2. Plugin Development

Plugins must inherit from the `Plugin` base class and implement:

* `id`: Unique identifier
* `get_plugin_id`: Class method returning the same identifier
* `name`: Human-readable name
* `description`: Brief description
* `execute`: Main plugin logic
* `get_mqtt_entities`: MQTT entity definitions

Plugins receive dependencies through constructor injection:

```python
def __init__(self, mqtt_service: MqttService, mealie_service: MealieApiService, gpt_service: GptService):
    self._mqtt = mqtt_service
    self._mealie = mealie_service
    self._gpt = gpt_service
    
    # Configuration attributes (updated via MQTT)
    self._some_config = 10  # Default value
```

### 4.3. MQTT Integration

MealieMate integrates with Home Assistant through MQTT:

* **Entity Discovery:** Automatically registers entities in Home Assistant
* **Configuration:** Receives configuration updates from Home Assistant
* **Status Updates:** Publishes status information to Home Assistant
* **User Interaction:** Processes user input from Home Assistant

## 5. Coding Guidelines

### 5.1. General Principles

* **SOLID:** Single responsibility, Open/closed, Liskov substitution, Interface segregation, Dependency inversion
* **KISS:** Keep It Simple, Stupid
* **YAGNI:** You Ain't Gonna Need It
* **DRY:** Don't Repeat Yourself

### 5.2. Plugin Guidelines

* Inherit from `Plugin` base class
* Implement all required methods
* Use injected services for external interactions
* Handle errors gracefully
* Use the provided logging methods
* Store configuration in instance variables

### 5.3. Service Guidelines

* Define interfaces as abstract base classes
* Implement services independently
* Provide consistent behavior
* Handle errors gracefully

## 6. Adding New Plugins

1. Create a new `.py` file in the `plugins/` directory
2. Implement the `Plugin` interface
3. Inject required services through the constructor
4. Implement plugin logic in the `execute` method
5. Define MQTT entities in `get_mqtt_entities`
6. Restart MealieMate to discover the new plugin

## 7. Conclusion

MealieMate's architecture emphasizes:

* **Modularity:** Components with clear responsibilities
* **Extensibility:** Easy to add new plugins and features
* **Maintainability:** Clean separation of concerns
* **Consistency:** Centralized management of plugin instances and configurations

By following these architectural principles, MealieMate can continue to evolve while maintaining a clean and maintainable codebase.
