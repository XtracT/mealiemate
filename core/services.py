"""
Module: services
--------------
Defines service interfaces for external dependencies.

This module provides abstract base classes for services that plugins may use,
enabling dependency injection and making it easier to test plugins in isolation.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Union

class MqttService(ABC):
    """Interface for MQTT service."""
    
    @abstractmethod
    async def setup_mqtt_switch(self, plugin_id: str, name: str) -> bool:
        """
        Register an MQTT switch in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            name: Human-readable name for the switch
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def setup_mqtt_sensor(self, plugin_id: str, sensor_id: str, name: str) -> bool:
        """
        Register an MQTT sensor in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific sensor
            name: Human-readable name for the sensor
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def setup_mqtt_number(
        self, 
        plugin_id: str, 
        number_id: str, 
        name: str, 
        default_value: int, 
        min_value: int = 1, 
        max_value: int = 1000, 
        step: int = 1, 
        unit: str = ""
    ) -> bool:
        """
        Register an MQTT Number entity in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            number_id: Unique identifier for this specific number input
            name: Human-readable name for the number input
            default_value: Initial value for the number
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            step: Step size for incrementing/decrementing
            unit: Unit of measurement (optional)
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def setup_mqtt_text(
        self, 
        plugin_id: str, 
        text_id: str, 
        name: str, 
        default_value: str = "", 
        max_length: int = 255
    ) -> bool:
        """
        Register an MQTT Text entity in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            text_id: Unique identifier for this specific text input
            name: Human-readable name for the text input
            default_value: Initial value for the text field
            max_length: Maximum allowed length for the text
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def setup_mqtt_button(self, plugin_id: str, button_id: str, name: str) -> bool:
        """
        Register an MQTT button in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            button_id: Unique identifier for this specific button
            name: Human-readable name for the button
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def setup_mqtt_binary_sensor(self, plugin_id: str, sensor_id: str, name: str) -> bool:
        """
        Register an MQTT binary sensor in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific binary sensor
            name: Human-readable name for the binary sensor
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def setup_mqtt_image(self, plugin_id: str, image_id: str, name: str, image_topic: str) -> bool:
        """
        Register an MQTT image entity in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            image_id: Unique identifier for this specific image entity
            name: Human-readable name for the image entity
            image_topic: The topic where the image bytes will be published
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def log(
        self, 
        plugin_id: str, 
        sensor_id: str, 
        message: str, 
        reset: bool = False, 
        level: int = 20,  # INFO
        category: Optional[str] = None,
        log_to_ha: bool = True,
        extra_attributes: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Enhanced log function that handles both console and Home Assistant logging.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for the sensor to log to
            message: Message text to log
            reset: If True, clear the existing log buffer before adding this message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            category: Optional category for emoji selection
            log_to_ha: Whether to log to Home Assistant (set to False for debug messages)
            extra_attributes: Optional dictionary of additional attributes to include
            
        Returns:
            True if logging was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def debug(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log a debug message (not sent to Home Assistant)."""
        pass
    
    @abstractmethod
    async def info(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log an info message."""
        pass
    
    @abstractmethod
    async def warning(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log a warning message (sent to Home Assistant)."""
        pass
    
    @abstractmethod
    async def error(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log an error message (sent to Home Assistant)."""
        pass
    
    @abstractmethod
    async def critical(self, plugin_id: str, message: str, sensor_id: Optional[str] = None, category: Optional[str] = None) -> bool:
        """Log a critical message (sent to Home Assistant)."""
        pass
    
    @abstractmethod
    async def gpt_decision(self, plugin_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
        """Log a GPT decision (always sent to Home Assistant)."""
        pass
    
    @abstractmethod
    async def progress(self, plugin_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
        """Log a progress update."""
        pass
    
    @abstractmethod
    async def success(self, plugin_id: str, message: str, sensor_id: Optional[str] = None) -> bool:
        """Log a success message (sent to Home Assistant)."""
        pass
        
    @abstractmethod
    async def setup_mqtt_progress(self, plugin_id: str, sensor_id: str, name: str) -> bool:
        """
        Register an MQTT progress sensor in Home Assistant.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific sensor
            name: Human-readable name for the sensor
            
        Returns:
            True if registration was successful, False otherwise
        """
        pass

    @abstractmethod
    async def reset_sensor(self, plugin_id: str, sensor_id: str) -> bool:
        """
        Reset a sensor by writing an empty string to it.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for the sensor to reset
            
        Returns:
            True if reset was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_progress(self, plugin_id: str, sensor_id: str, percentage: int, activity: str) -> bool:
        """
        Update the progress sensor with current percentage and activity.
        
        Args:
            plugin_id: Unique identifier for the plugin
            sensor_id: Unique identifier for this specific sensor
            percentage: Progress percentage (0-100)
            activity: Current activity description
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
        
    @abstractmethod
    async def set_switch_state(self, switch_id: str, state: str) -> bool:
        """
        Set the state of a switch in Home Assistant.
        
        Args:
            switch_id: ID of the switch (e.g. plugin_id_switch_id)
            state: New state ("ON" or "OFF")
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def set_binary_sensor_state(self, sensor_id: str, state: str) -> bool:
        """
        Set the state of a binary sensor in Home Assistant.
        
        Args:
            sensor_id: ID of the binary sensor (e.g. script_id_sensor_id)
            state: New state ("ON" or "OFF")
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
        
    @abstractmethod
    async def publish_mqtt_image(self, topic: str, payload: bytes, retain: bool = False, qos: int = 0) -> bool:
        """
        Publish image bytes to a specific MQTT topic.
        
        Args:
            topic: The MQTT topic to publish to
            payload: The raw image bytes to publish
            retain: Whether the message should be retained
            qos: Quality of Service level
            
        Returns:
            True if publishing was successful, False otherwise
        """
        pass


class MealieApiService(ABC):
    """Interface for Mealie API service."""
    
    @abstractmethod
    async def fetch_data(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Perform a GET request to the Mealie API and return the parsed JSON response or None on error.
        
        Args:
            endpoint: API endpoint path (starting with /)
            
        Returns:
            Parsed JSON response as dictionary or None if request failed
        """
        pass
    
    @abstractmethod
    async def post_data(self, endpoint: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Perform a POST request to the Mealie API.
        
        Args:
            endpoint: API endpoint path (starting with /)
            payload: JSON data to send in the request body
            
        Returns:
            Tuple of (response_data, status_code) where response_data may be None
        """
        pass
    
    @abstractmethod
    async def patch_data(self, endpoint: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Perform a PATCH request to the Mealie API.
        
        Args:
            endpoint: API endpoint path (starting with /)
            payload: JSON data to send in the request body
            
        Returns:
            Tuple of (response_data, status_code) where response_data may be None
        """
        pass
    
    @abstractmethod
    async def get_all_recipes(self) -> List[Dict[str, Any]]:
        """
        Fetch all recipes from Mealie (basic data).
        
        Returns:
            List of recipe dictionaries or empty list if request failed
        """
        pass
    
    @abstractmethod
    async def get_recipe_details(self, recipe_slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed recipe info by slug.
        
        Args:
            recipe_slug: The recipe slug identifier
            
        Returns:
            Recipe details dictionary or None if not found
        """
        pass
    
    @abstractmethod
    async def get_tags(self) -> List[Dict[str, Any]]:
        """
        Return existing tags from Mealie.
        
        Returns:
            List of tag dictionaries or empty list if request failed
        """
        pass
    
    @abstractmethod
    async def get_categories(self) -> List[Dict[str, Any]]:
        """
        Return existing categories from Mealie.
        
        Returns:
            List of category dictionaries or empty list if request failed
        """
        pass
    
    @abstractmethod
    async def create_tag(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        Create a new tag in Mealie.
        
        Args:
            tag_name: Name of the tag to create
            
        Returns:
            Created tag dictionary or None if creation failed
        """
        pass
    
    @abstractmethod
    async def create_category(self, category_name: str) -> Optional[Dict[str, Any]]:
        """
        Create a new category in Mealie.
        
        Args:
            category_name: Name of the category to create
            
        Returns:
            Created category dictionary or None if creation failed
        """
        pass
    
    @abstractmethod
    async def get_meal_plan(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Fetch the meal plan from Mealie within the given date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of meal plan entries or empty list if request failed
        """
        pass
    
    @abstractmethod
    async def create_mealplan_entry(self, payload: Dict[str, Any]) -> bool:
        """
        Create a single meal plan entry in Mealie.
        
        Args:
            payload: Meal plan entry data
            
        Returns:
            True if creation was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def create_shopping_list(self, list_name: str) -> Optional[str]:
        """
        Create a new shopping list in Mealie.
        
        Args:
            list_name: Name of the shopping list to create
            
        Returns:
            ID of the created shopping list or None if creation failed
        """
        pass
    
    @abstractmethod
    async def add_item_to_shopping_list(self, shopping_list_id: str, note: str) -> bool:
        """
        Add an item (note) to a Mealie shopping list by ID.
        
        Args:
            shopping_list_id: ID of the shopping list
            note: Text content of the shopping list item
            
        Returns:
            True if item was added successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_recipe_tags_categories(self, recipe_slug: str, payload: Dict[str, Any]) -> bool:
        """
        PATCH a recipe to update tags/categories.
        
        Args:
            recipe_slug: The recipe slug identifier
            payload: Update data containing tags and/or categories
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_recipe_ingredient(self, recipe_slug: str, old_ingredient: str, new_ingredient: str) -> bool:
        """
        Update an ingredient name in a recipe.
        
        Args:
            recipe_slug: The recipe slug identifier
            old_ingredient: The old ingredient name to replace
            new_ingredient: The new ingredient name to use
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def merge_foods(self, from_food_name: str, to_food_name: str) -> bool:
        """
        Merge two foods using the Mealie API's dedicated merge endpoint.
        
        Args:
            from_food_name: The name of the food to merge from (will be replaced)
            to_food_name: The name of the food to merge to (will be kept)
            
        Returns:
            True if merge was successful, False otherwise
        """
        pass


class GptService(ABC):
    """Interface for GPT service."""
    
    @abstractmethod
    async def gpt_json_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "gpt-4o", 
        temperature: float = 0.1,
        max_retries: int = 2,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Sends a series of messages to OpenAI Chat Completion with JSON output and
        returns a Python dict if JSON can be parsed, or an empty dict on failure.

        Args:
            messages: A list of {"role": "...", "content": "..."} chat messages
            model: Which model to use (e.g. "gpt-4o")
            temperature: The temperature for the completion (0.0 to 2.0)
            max_retries: Maximum number of retry attempts on transient errors
            retry_delay: Delay between retries in seconds
            
        Returns:
            Parsed JSON response as dictionary or empty dict on failure
        """
        pass
