"""
Module: mealie_api
------------------
Contains shared functions for interacting with the Mealie API:
 - Generic fetch/post/patch requests
 - Common domain methods (e.g., get_all_recipes, create_tag, etc.)

This module provides a clean interface for all Mealie API operations used throughout
the MealieMate application.
"""

import os
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

MEALIE_URL = os.getenv("MEALIE_URL") or "http://192.168.1.61:9925"
MEALIE_API_KEY = os.getenv("MEALIE_TOKEN")

if not MEALIE_API_KEY:
    logger.warning("MEALIE_TOKEN not found in environment variables")

HEADERS = {
    "Authorization": f"Bearer {MEALIE_API_KEY}",
    "Content-Type": "application/json"
}

async def fetch_data(endpoint: str) -> Optional[Dict[str, Any]]:
    """
    Perform a GET request to the Mealie API and return the parsed JSON response or None on error.
    
    Args:
        endpoint: API endpoint path (starting with /)
        
    Returns:
        Parsed JSON response as dictionary or None if request failed
    """
    url = f"{MEALIE_URL}{endpoint}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(f"GET request to {url} failed with status {response.status}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Connection error during GET to {url}: {str(e)}")
            return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout during GET to {url}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during GET to {url}: {str(e)}")
            return None

async def post_data(endpoint: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
    """
    Perform a POST request to the Mealie API.
    
    Args:
        endpoint: API endpoint path (starting with /)
        payload: JSON data to send in the request body
        
    Returns:
        Tuple of (response_data, status_code) where response_data may be None
    """
    url = f"{MEALIE_URL}{endpoint}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=HEADERS, json=payload) as response:
                try:
                    data = await response.json()
                except aiohttp.ContentTypeError:
                    data = None
                return data, response.status
        except Exception as e:
            logger.error(f"Error during POST to {url}: {str(e)}")
            return None, 500

async def patch_data(endpoint: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
    """
    Perform a PATCH request to the Mealie API.
    
    Args:
        endpoint: API endpoint path (starting with /)
        payload: JSON data to send in the request body
        
    Returns:
        Tuple of (response_data, status_code) where response_data may be None
    """
    url = f"{MEALIE_URL}{endpoint}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, headers=HEADERS, json=payload) as response:
                try:
                    data = await response.json()
                except aiohttp.ContentTypeError:
                    data = None
                return data, response.status
        except Exception as e:
            logger.error(f"Error during PATCH to {url}: {str(e)}")
            return None, 500

# ------------------------------
# Convenience Domain Functions
# ------------------------------

async def get_all_recipes() -> List[Dict[str, Any]]:
    """
    Fetch all recipes from Mealie (basic data).
    
    Returns:
        List of recipe dictionaries or empty list if request failed
    """
    data = await fetch_data("/api/recipes")
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def get_recipe_details(recipe_slug: str) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed recipe info by slug.
    
    Args:
        recipe_slug: The recipe slug identifier
        
    Returns:
        Recipe details dictionary or None if not found
    """
    return await fetch_data(f"/api/recipes/{recipe_slug}")

async def get_tags() -> List[Dict[str, Any]]:
    """
    Return existing tags from Mealie.
    
    Returns:
        List of tag dictionaries or empty list if request failed
    """
    data = await fetch_data("/api/organizers/tags")
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def get_categories() -> List[Dict[str, Any]]:
    """
    Return existing categories from Mealie.
    
    Returns:
        List of category dictionaries or empty list if request failed
    """
    data = await fetch_data("/api/organizers/categories")
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def create_tag(tag_name: str) -> Optional[Dict[str, Any]]:
    """
    Create a new tag in Mealie.
    
    Args:
        tag_name: Name of the tag to create
        
    Returns:
        Created tag dictionary or None if creation failed
    """
    payload = {"name": tag_name}
    data, status = await post_data("/api/organizers/tags", payload)
    if status == 201:
        logger.info(f"Created tag: {tag_name}")
        return data
    logger.warning(f"Failed to create tag '{tag_name}', status: {status}")
    return None

async def create_category(category_name: str) -> Optional[Dict[str, Any]]:
    """
    Create a new category in Mealie.
    
    Args:
        category_name: Name of the category to create
        
    Returns:
        Created category dictionary or None if creation failed
    """
    payload = {"name": category_name}
    data, status = await post_data("/api/organizers/categories", payload)
    if status == 201:
        logger.info(f"Created category: {category_name}")
        return data
    logger.warning(f"Failed to create category '{category_name}', status: {status}")
    return None

async def get_meal_plan(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Fetch the meal plan from Mealie within the given date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of meal plan entries or empty list if request failed
    """
    endpoint = f"/api/households/mealplans?start_date={start_date}&end_date={end_date}"
    data = await fetch_data(endpoint)
    if not data or not isinstance(data, dict):
        logger.warning(f"Failed to fetch meal plan for {start_date} to {end_date}")
        return []
    return data.get("items", [])

async def create_mealplan_entry(payload: Dict[str, Any]) -> bool:
    """
    Create a single meal plan entry in Mealie.
    
    Args:
        payload: Meal plan entry data
        
    Returns:
        True if creation was successful, False otherwise
    """
    _, status = await post_data("/api/households/mealplans", payload)
    success = status == 201
    if success:
        logger.info(f"Created meal plan entry for {payload.get('date', 'unknown date')}")
    else:
        logger.warning(f"Failed to create meal plan entry, status: {status}")
    return success

async def create_shopping_list(list_name: str) -> Optional[str]:
    """
    Create a new shopping list in Mealie.
    
    Args:
        list_name: Name of the shopping list to create
        
    Returns:
        ID of the created shopping list or None if creation failed
    """
    payload = {"name": list_name}
    data, status = await post_data("/api/households/shopping/lists", payload)
    if status == 201 and data:
        logger.info(f"Created shopping list: {list_name}")
        return data["id"]
    logger.warning(f"Failed to create shopping list '{list_name}', status: {status}")
    return None

async def add_item_to_shopping_list(shopping_list_id: str, note: str) -> bool:
    """
    Add an item (note) to a Mealie shopping list by ID.
    
    Args:
        shopping_list_id: ID of the shopping list
        note: Text content of the shopping list item
        
    Returns:
        True if item was added successfully, False otherwise
    """
    payload = {
        "shoppingListId": shopping_list_id,
        "note": note,
        "isFood": False,
        "disableAmount": True
    }
    _, status = await post_data("/api/households/shopping/items", payload)
    success = status == 201
    if not success:
        logger.warning(f"Failed to add item to shopping list, status: {status}")
    return success

async def update_recipe_tags_categories(recipe_slug: str, payload: Dict[str, Any]) -> bool:
    """
    PATCH a recipe to update tags/categories.
    
    Args:
        recipe_slug: The recipe slug identifier
        payload: Update data containing tags and/or categories
        
    Returns:
        True if update was successful, False otherwise
    """
    _, status = await patch_data(f"/api/recipes/{recipe_slug}", payload)
    success = status == 200
    if success:
        logger.info(f"Updated recipe tags/categories for: {recipe_slug}")
    else:
        logger.warning(f"Failed to update recipe '{recipe_slug}', status: {status}")
    return success
