"""
Module: mealie_api_service
-----------------------
Provides an implementation of the MealieApiService interface using the mealie_api module.

This module wraps the existing mealie_api functionality in a class that implements
the MealieApiService interface, making it compatible with the dependency injection system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from core.services import MealieApiService
import utils.mealie_api as mealie_api

# Configure logging
logger = logging.getLogger(__name__)

class MealieApiServiceImpl(MealieApiService):
    """Implementation of the MealieApiService interface using mealie_api."""
    
    async def fetch_data(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Perform a GET request to the Mealie API and return the parsed JSON response or None on error.
        
        Args:
            endpoint: API endpoint path (starting with /)
            
        Returns:
            Parsed JSON response as dictionary or None if request failed
        """
        return await mealie_api.fetch_data(endpoint)
    
    async def post_data(self, endpoint: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Perform a POST request to the Mealie API.
        
        Args:
            endpoint: API endpoint path (starting with /)
            payload: JSON data to send in the request body
            
        Returns:
            Tuple of (response_data, status_code) where response_data may be None
        """
        return await mealie_api.post_data(endpoint, payload)
    
    async def patch_data(self, endpoint: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Perform a PATCH request to the Mealie API.
        
        Args:
            endpoint: API endpoint path (starting with /)
            payload: JSON data to send in the request body
            
        Returns:
            Tuple of (response_data, status_code) where response_data may be None
        """
        return await mealie_api.patch_data(endpoint, payload)
    
    async def get_all_recipes(self) -> List[Dict[str, Any]]:
        """
        Fetch all recipes from Mealie (basic data).
        
        Returns:
            List of recipe dictionaries or empty list if request failed
        """
        return await mealie_api.get_all_recipes()
    
    async def get_recipe_details(self, recipe_slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed recipe info by slug.
        
        Args:
            recipe_slug: The recipe slug identifier
            
        Returns:
            Recipe details dictionary or None if not found
        """
        return await mealie_api.get_recipe_details(recipe_slug)
    
    async def get_tags(self) -> List[Dict[str, Any]]:
        """
        Return existing tags from Mealie.
        
        Returns:
            List of tag dictionaries or empty list if request failed
        """
        return await mealie_api.get_tags()
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """
        Return existing categories from Mealie.
        
        Returns:
            List of category dictionaries or empty list if request failed
        """
        return await mealie_api.get_categories()
    
    async def create_tag(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        Create a new tag in Mealie.
        
        Args:
            tag_name: Name of the tag to create
            
        Returns:
            Created tag dictionary or None if creation failed
        """
        return await mealie_api.create_tag(tag_name)
    
    async def create_category(self, category_name: str) -> Optional[Dict[str, Any]]:
        """
        Create a new category in Mealie.
        
        Args:
            category_name: Name of the category to create
            
        Returns:
            Created category dictionary or None if creation failed
        """
        return await mealie_api.create_category(category_name)
    
    async def get_meal_plan(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Fetch the meal plan from Mealie within the given date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of meal plan entries or empty list if request failed
        """
        return await mealie_api.get_meal_plan(start_date, end_date)
    
    async def create_mealplan_entry(self, payload: Dict[str, Any]) -> bool:
        """
        Create a single meal plan entry in Mealie.
        
        Args:
            payload: Meal plan entry data
            
        Returns:
            True if creation was successful, False otherwise
        """
        return await mealie_api.create_mealplan_entry(payload)
    
    async def create_shopping_list(self, list_name: str) -> Optional[str]:
        """
        Create a new shopping list in Mealie.
        
        Args:
            list_name: Name of the shopping list to create
            
        Returns:
            ID of the created shopping list or None if creation failed
        """
        return await mealie_api.create_shopping_list(list_name)
    
    async def add_item_to_shopping_list(self, shopping_list_id: str, note: str) -> bool:
        """
        Add an item (note) to a Mealie shopping list by ID.
        
        Args:
            shopping_list_id: ID of the shopping list
            note: Text content of the shopping list item
            
        Returns:
            True if item was added successfully, False otherwise
        """
        return await mealie_api.add_item_to_shopping_list(shopping_list_id, note)
    
    async def update_recipe_tags_categories(self, recipe_slug: str, payload: Dict[str, Any]) -> bool:
        """
        PATCH a recipe to update tags/categories.
        
        Args:
            recipe_slug: The recipe slug identifier
            payload: Update data containing tags and/or categories
            
        Returns:
            True if update was successful, False otherwise
        """
        return await mealie_api.update_recipe_tags_categories(recipe_slug, payload)
