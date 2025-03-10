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
import re
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
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

async def put_data(endpoint: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
    """
    Perform a PUT request to the Mealie API.
    
    Args:
        endpoint: API endpoint path (starting with /)
        payload: JSON data to send in the request body
        
    Returns:
        Tuple of (response_data, status_code) where response_data may be None
    """
    url = f"{MEALIE_URL}{endpoint}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.put(url, headers=HEADERS, json=payload) as response:
                try:
                    data = await response.json()
                except aiohttp.ContentTypeError:
                    data = None
                return data, response.status
        except Exception as e:
            logger.error(f"Error during PUT to {url}: {str(e)}")
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

async def create_food(food_name: str) -> Optional[Dict[str, Any]]:
    """
    Create a new food in Mealie.
    
    Args:
        food_name: Name of the food to create
        
    Returns:
        Created food dictionary or None if creation failed
    """
    payload = {"name": food_name}
    data, status = await post_data("/api/foods", payload)
    if status == 201:
        logger.info(f"Created food: {food_name}")
        return data
    logger.warning(f"Failed to create food '{food_name}', status: {status}")
    return None

async def get_all_foods() -> List[Dict[str, Any]]:
    """
    Fetch all foods from Mealie.
    
    Returns:
        List of food dictionaries or empty list if request failed
    """
    data = await fetch_data("/api/foods")
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def get_food_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Find a food by name in the Mealie database.
    
    Args:
        name: The name of the food to find
        
    Returns:
        Food dictionary or None if not found
    """
    foods = await get_all_foods()
    
    # Log all available foods for debugging
    food_names = [food.get("name", "unknown") for food in foods]
    logger.debug(f"Available foods in database: {food_names}")
    
    # First try exact match
    for food in foods:
        if food.get("name") == name:
            logger.debug(f"Found exact match for '{name}': {food}")
            return food
    
    # Try case-insensitive match
    name_lower = name.lower()
    for food in foods:
        food_name = food.get("name", "")
        if food_name.lower() == name_lower:
            logger.debug(f"Found case-insensitive match for '{name}': {food}")
            return food
    
    # Try partial match (if the food name contains our search term or vice versa)
    for food in foods:
        food_name = food.get("name", "")
        if name_lower in food_name.lower() or food_name.lower() in name_lower:
            logger.debug(f"Found partial match for '{name}': {food}")
            return food
    
    logger.warning(f"Could not find any food matching '{name}' in database")
    return None


async def merge_foods(from_food: str, to_food: str) -> bool:
    """
    Merge two foods using the Mealie API's dedicated merge endpoint.
    
    Args:
        from_food: The ID or name of the food to merge from (will be replaced)
        to_food: The ID or name of the food to merge to (will be kept)
        
    Returns:
        True if merge was successful, False otherwise
    """
    try:
        # Check if the inputs are UUIDs or names
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        from_food_is_uuid = bool(re.match(uuid_pattern, from_food, re.IGNORECASE))
        to_food_is_uuid = bool(re.match(uuid_pattern, to_food, re.IGNORECASE))
        
        # Get the food UUIDs if names were provided
        from_food_id = from_food
        to_food_id = to_food
        from_food_name = from_food
        to_food_name = to_food
        
        if not from_food_is_uuid:
            # It's a name, look up the UUID
            from_food_obj = await get_food_by_name(from_food)
            if not from_food_obj:
                logger.warning(f"Could not find food with name: {from_food}")
                return False
            from_food_id = from_food_obj.get("id")
            if not from_food_id:
                logger.warning(f"Missing ID for food: {from_food}")
                return False
        
        if not to_food_is_uuid:
            # It's a name, look up the UUID
            to_food_obj = await get_food_by_name(to_food)
            if not to_food_obj:
                logger.warning(f"Could not find food with name: {to_food}")
                return False
            to_food_id = to_food_obj.get("id")
            if not to_food_id:
                logger.warning(f"Missing ID for food: {to_food}")
                return False
        
        # Create payload with UUIDs
        payload = {
            "fromFood": from_food_id,
            "toFood": to_food_id
        }
        
        logger.debug(f"Merging food '{from_food_name}' (ID: {from_food_id}) into '{to_food_name}' (ID: {to_food_id})")
        logger.debug(f"Merge payload: {payload}")
        
        # Use PUT request as specified in the API documentation
        response_data, status = await put_data("/api/foods/merge", payload)
        
        logger.debug(f"Merge response status: {status}")
        if response_data:
            logger.debug(f"Merge response data: {response_data}")
        
        if status == 200:
            logger.info(f"Successfully merged food '{from_food_name}' into '{to_food_name}'")
            return True
        else:
            logger.warning(f"Failed to merge foods, status: {status}, response: {response_data}")
            return False
            
    except Exception as e:
        logger.error(f"Error merging foods: {str(e)}", exc_info=True)
        return False


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

async def update_recipe_ingredient(recipe_slug: str, old_ingredient: str, new_ingredient: str) -> bool:
    """
    Update an ingredient name in a recipe.
    
    Args:
        recipe_slug: The recipe slug identifier
        old_ingredient: The old ingredient name to replace
        new_ingredient: The new ingredient name to use
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        # Get the full recipe details
        logger.debug(f"Fetching recipe details for: {recipe_slug}")
        recipe_details = await fetch_data(f"/api/recipes/{recipe_slug}")
        if not recipe_details:
            logger.warning(f"Could not fetch details for recipe: {recipe_slug}")
            return False
        
        # Debug: Log recipe ID and structure
        recipe_id = recipe_details.get("id")
        logger.debug(f"Recipe ID: {recipe_id}, Recipe slug: {recipe_slug}")
        logger.debug(f"Recipe structure keys: {list(recipe_details.keys())}")
        
        # Find and update the ingredient
        updated = False
        for i, ing in enumerate(recipe_details.get("recipeIngredient", [])):
            if ing.get("food") and ing["food"].get("name") == old_ingredient:
                logger.debug(f"Found ingredient to update: {ing}")
                ing["food"]["name"] = new_ingredient
                updated = True
                logger.debug(f"Updated ingredient: {ing}")
        
        if not updated:
            logger.warning(f"Could not find ingredient '{old_ingredient}' in recipe: {recipe_slug}")
            return False
        
        # Debug: Create a minimal payload with only necessary fields
        minimal_payload = {
            "recipeIngredient": recipe_details.get("recipeIngredient", [])
        }
        
        logger.debug(f"Sending PATCH with minimal payload: {minimal_payload}")
        
        # Update the recipe in Mealie with minimal payload
        response_data, status = await patch_data(f"/api/recipes/{recipe_slug}", minimal_payload)
        
        # Debug: Log the response
        logger.debug(f"PATCH response status: {status}")
        if response_data:
            logger.debug(f"PATCH response data: {response_data}")
        
        if status == 200:
            logger.info(f"Updated recipe '{recipe_slug}': replaced '{old_ingredient}' with '{new_ingredient}'")
            return True
        else:
            logger.warning(f"Failed to update recipe '{recipe_slug}', status: {status}, response: {response_data}")
            
            # Try with full payload as fallback
            logger.debug("Trying with full recipe payload as fallback")
            full_response_data, full_status = await patch_data(f"/api/recipes/{recipe_slug}", recipe_details)
            
            logger.debug(f"Full payload PATCH response status: {full_status}")
            if full_response_data:
                logger.debug(f"Full payload PATCH response data: {full_response_data}")
            
            if full_status == 200:
                logger.info(f"Updated recipe '{recipe_slug}' with full payload: replaced '{old_ingredient}' with '{new_ingredient}'")
                return True
            else:
                logger.warning(f"Failed to update recipe '{recipe_slug}' with full payload, status: {full_status}, response: {full_response_data}")
                return False
            
    except Exception as e:
        logger.error(f"Error updating recipe '{recipe_slug}': {str(e)}", exc_info=True)
        return False
