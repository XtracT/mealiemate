# Plugin Update Implementation Plan

## Original Task

Refactor the `reset_special_sensors` function in `system_service.py` so that each plugin defines which sensors should be reset.

## Completed Steps

1.  **Gathered Information:**
    *   Read `README.md` and `architecture.md` to understand the project's overall design.
    *   Read `core/system_service.py` to understand the current implementation of `reset_special_sensors`.
    *   Read `core/plugin_manager.py` to understand how plugins are initialized.
    *   Read `core/app.py` to understand how the application is initialized.
    *   Read `core/plugin.py` to understand the Plugin class.
2.  **Revised Plan:**
    *   Revised the plan based on user feedback to make the `reset_sensors` attribute optional.
3.  **Update Plugin Manager (core/plugin_manager.py):**
    *   Modified the `start_plugin` method to call a new helper method `reset_plugin_sensors` after the plugin instance is created and before the plugin's `execute` method is called.
    *   Created the `reset_plugin_sensors` helper method. This method checks if the plugin instance has a `reset_sensors` attribute and uses it to reset the sensors if it exists.
4.  **Modify System Service (core/system_service.py):**
    *   Modified the `reset_special_sensors` method to iterate through all plugins in the `PluginRegistry` and call the `reset_plugin_sensors` helper method for each plugin.
    *   Removed the hardcoded list of `special_sensor_ids` from the `reset_special_sensors` method.
5.  **Update Application Initialization (core/app.py):**
    *   Modified the `start` method to call the `reset_special_sensors` method on the `SystemService` after the MQTT entities are set up and before the MQTT listener and message processor are started.
6.  **Update Architecture Documentation (architecture.md):**
    *   Updated the `architecture.md` file to reflect the changes to the plugin architecture and the new `reset_sensors` attribute.
7.  **Added `reset_sensors` attribute to plugins:**
    *   plugins/neapolitan_pizza.py
    *   plugins/mealplan_fetcher.py
    *   plugins/recipe_tagger.py
    *   plugins/shopping_list_generator.py

## Steps in Progress (Before Interruption)

1.  **Modify Plugin `execute` Methods:**
    *   Iterate through each plugin file.
    *   Modify the `execute` method of each plugin to reset the sensors defined in the `reset_sensors` attribute at the beginning of the method.
        *   I was in the middle of modifying `plugins/ingredient_merger.py` when the task was interrupted.

## Remaining Steps

1.  **Modify Plugin `execute` Methods:**
    *   Iterate through each plugin file.
    *   Modify the `execute` method of each plugin to reset the sensors defined in the `reset_sensors` attribute at the beginning of the method.
        *   plugins/ingredient_merger.py
2.  **Testing:**
    *   Run the application and verify that the sensors are reset correctly on plugin initialization and application initialization.
3.  **Clean up plugin for previous sensor resetting:**
    *   Remove any code in the plugins that was previously used to reset sensors, as this is now handled by the `reset_special_sensors` method in `core/system_service.py` and the `reset_plugin_sensors` method in `core/plugin_manager.py`.