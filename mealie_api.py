"""
Module: mealie_api
------------------
Contains shared functions for interacting with the Mealie API:
 - Generic fetch/post/patch requests
 - Common domain methods (e.g., get_all_recipes, create_tag, etc.)

Logic remains consistent; only refactored for DRY usage by other scripts.
"""

import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()

MEALIE_URL = os.getenv("MEALIE_URL") or "http://192.168.1.61:9925"
MEALIE_API_KEY = os.getenv("MEALIE_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {MEALIE_API_KEY}",
    "Content-Type": "application/json"
}

async def fetch_data(endpoint: str) -> dict or None:
    """
    Perform a GET request to the Mealie API and return the parsed JSON response or None on error.
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{MEALIE_URL}{endpoint}", headers=HEADERS) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None

async def post_data(endpoint: str, payload: dict) -> (dict or None, int):
    """
    Perform a POST request to the Mealie API.
    Returns (response_json_or_None, status_code).
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{MEALIE_URL}{endpoint}", headers=HEADERS, json=payload) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                data = None
            return data, response.status

async def patch_data(endpoint: str, payload: dict) -> (dict or None, int):
    """
    Perform a PATCH request to the Mealie API.
    Returns (response_json_or_None, status_code).
    """
    async with aiohttp.ClientSession() as session:
        async with session.patch(f"{MEALIE_URL}{endpoint}", headers=HEADERS, json=payload) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                data = None
            return data, response.status

# ------------------------------
# Convenience Domain Functions
# ------------------------------

async def get_all_recipes() -> list:
    """Fetch all recipes from Mealie (basic data)."""
    data = await fetch_data("/api/recipes")
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def get_recipe_details(recipe_slug: str) -> dict or None:
    """Fetch detailed recipe info by slug."""
    return await fetch_data(f"/api/recipes/{recipe_slug}")

async def get_tags() -> list:
    """Return existing tags from Mealie."""
    data = await fetch_data("/api/organizers/tags")
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def get_categories() -> list:
    """Return existing categories from Mealie."""
    data = await fetch_data("/api/organizers/categories")
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def create_tag(tag_name: str) -> dict or None:
    """Create a new tag in Mealie."""
    payload = {"name": tag_name}
    data, status = await post_data("/api/organizers/tags", payload)
    return data if status == 201 else None

async def create_category(category_name: str) -> dict or None:
    """Create a new category in Mealie."""
    payload = {"name": category_name}
    data, status = await post_data("/api/organizers/categories", payload)
    return data if status == 201 else None

async def get_meal_plan(start_date: str, end_date: str) -> list:
    """Fetch the meal plan from Mealie within the given date range."""
    endpoint = f"/api/households/mealplans?start_date={start_date}&end_date={end_date}"
    data = await fetch_data(endpoint)
    if not data or not isinstance(data, dict):
        return []
    return data.get("items", [])

async def create_mealplan_entry(payload: dict) -> bool:
    """Create a single meal plan entry in Mealie."""
    _, status = await post_data("/api/households/mealplans", payload)
    return (status == 201)

async def create_shopping_list(list_name: str) -> (str or None):
    """Create a new shopping list in Mealie. Returns the ID if successful, else None."""
    payload = {"name": list_name}
    data, status = await post_data("/api/households/shopping/lists", payload)
    if status == 201 and data:
        return data["id"]
    return None

async def add_item_to_shopping_list(shopping_list_id: str, note: str) -> bool:
    """Add an item (note) to a Mealie shopping list by ID."""
    payload = {
        "shoppingListId": shopping_list_id,
        "note": note,
        "isFood": False,
        "disableAmount": True
    }
    _, status = await post_data("/api/households/shopping/items", payload)
    return (status == 201)

async def update_recipe_tags_categories(recipe_slug: str, payload: dict) -> bool:
    """PATCH a recipe to update tags/categories."""
    _, status = await patch_data(f"/api/recipes/{recipe_slug}", payload)
    return (status == 200)
