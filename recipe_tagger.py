"""
Module: recipe_tagger
---------------------
Classifies recipes in Mealie by assigning tags and categories using GPT, then updates them
in the Mealie database.

This module:
1. Fetches all recipes from Mealie
2. For each recipe, extracts ingredients
3. Uses GPT to classify the recipe based on ingredients and name
4. Updates the recipe in Mealie with appropriate tags and categories

The classification uses predefined tag categories and valid values to ensure consistency
across the recipe database.
"""

import asyncio
import os
import json
import logging
from typing import Dict, List, Tuple, Optional, Set, Any
from dotenv import load_dotenv

import utils.ha_mqtt as ha_mqtt
import utils.mealie_api as mealie_api
import utils.gpt_utils as gpt_utils

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DRY_RUN = False  # Set to True to skip updating Mealie
MODEL_NAME = "gpt-4o"
TEMPERATURE = 0.1

# Script configuration for Home Assistant integration
SCRIPT_CONFIG = {
    "id": "recipe_tagger",
    "name": "Recipe Tagger",
    "type": "automation",
    "switch": True,
    "sensors": {
        "status": {"id": "status", "name": "Tagging Progress"},
        "feedback": {"id": "feedback", "name": "Tagging Feedback"}
    },
    "execute_function": None  # Will be assigned the main() function
}

# Available tags and categories for classification
AVAILABLE_TAGS = {
    "Main Ingredient Category": [
        "Red Meat", "Poultry", "Fish", "Seafood", "Eggs", "Dairy",
        "Legumes", "Grains", "Vegetables", "Fruits", "Mushrooms"
    ],
    "Nutritional Profile and Dietary Preferences": [
        "Normal", "Vegetarian", "Vegan", "High Protein", "Low Carb",
        "High Fiber", "Low-Calorie", "High Fat", "Iron-Rich", "Calcium-Rich",
        "Vitamin-Packed"
    ],
    "Time & Effort": ["Quick", "30 min", "Long-Cooking", "Meal Prep-Friendly"]
}

AVAILABLE_CATEGORIES = [
    "Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Appetizer",
    "Side Dish", "Soup", "Salad", "Smoothie", "Sauce/Dressing", "Baked Goods"
]

# Create sets of all valid tags and categories for faster validation
ALL_VALID_TAGS: Set[str] = set()
for category in AVAILABLE_TAGS.values():
    ALL_VALID_TAGS.update(category)

VALID_CATEGORIES: Set[str] = set(AVAILABLE_CATEGORIES)

async def classify_recipe_with_gpt(
    name: str, 
    ingredients: List[str]
) -> Tuple[List[str], Optional[str]]:
    """
    Use GPT to classify a recipe based on its name and ingredients.
    
    Args:
        name: Recipe name
        ingredients: List of ingredient names
        
    Returns:
        Tuple of (valid_tags, valid_category)
    """
    # Clean and validate ingredients
    clean_ingredients = [i.strip() for i in ingredients if i and i.strip()]
    if not clean_ingredients:
        logger.warning(f"Recipe '{name}' has no valid ingredients, skipping classification")
        await ha_mqtt.warning(SCRIPT_CONFIG["id"], f"Recipe '{name}' has no valid ingredients, skipping classification.")
        return [], None

    # Construct prompt for GPT
    prompt = (
        "You are a recipe classification assistant. "
        "Classify the following recipe strictly using predefined tags and categories. "
        "DO NOT invent new tags or categories.\n\n"
        f"Recipe Name: '{name}'\n"
        f"Ingredients: {', '.join(clean_ingredients)}\n\n"
        f"Allowed Tags:\n"
        f"- Main Ingredients: {', '.join(AVAILABLE_TAGS['Main Ingredient Category'])}\n"
        f"- Nutritional Profile: {', '.join(AVAILABLE_TAGS['Nutritional Profile and Dietary Preferences'])}\n"
        f"- Time & Effort: {', '.join(AVAILABLE_TAGS['Time & Effort'])}\n\n"
        f"Allowed Categories:\n"
        f"- {', '.join(AVAILABLE_CATEGORIES)}\n\n"
        "Return JSON in the following format:\n"
        '{"tags": ["tag1", "tag2"], "category": "chosen_category"}'
    )

    # Call GPT
    messages = [{"role": "user", "content": prompt}]
    logger.info(f"Classifying recipe: {name}")
    result = await gpt_utils.gpt_json_chat(messages, model=MODEL_NAME, temperature=TEMPERATURE)

    # Extract and validate tags
    raw_tags = result.get("tags", [])
    category = result.get("category", None)

    # Filter out invalid tags
    filtered_tags = [t for t in raw_tags if t in ALL_VALID_TAGS]
    invalid_tags = [t for t in raw_tags if t not in ALL_VALID_TAGS]

    if invalid_tags:
        logger.warning(f"GPT returned invalid tags for '{name}': {invalid_tags}")
        await ha_mqtt.warning(SCRIPT_CONFIG["id"], f"GPT returned invalid tags {invalid_tags}. Ignoring these.")
        await ha_mqtt.log(SCRIPT_CONFIG["id"], "feedback", f"GPT returned invalid tags {invalid_tags}. Ignoring these.")

    # Validate category
    if category and category not in VALID_CATEGORIES:
        logger.warning(f"GPT returned invalid category for '{name}': {category}")
        await ha_mqtt.warning(SCRIPT_CONFIG["id"], f"Invalid category '{category}' received from GPT. Ignoring.")
        await ha_mqtt.log(SCRIPT_CONFIG["id"], "feedback", f"Invalid category '{category}' received from GPT. Ignoring.")
        category = None

    logger.info(f"Classification for '{name}': Tags={filtered_tags}, Category={category}")
    return filtered_tags, category

async def update_recipe(
    recipe_slug: str, 
    details: Dict[str, Any], 
    new_tags: List[str], 
    new_category: Optional[str], 
    tag_mapping: Dict[str, Dict[str, Any]], 
    category_mapping: Dict[str, Dict[str, Any]]
) -> bool:
    """
    Update a recipe in Mealie with new tags and category.
    
    Args:
        recipe_slug: Recipe slug identifier
        details: Recipe details from Mealie
        new_tags: List of tag names to apply
        new_category: Category name to apply (or None)
        tag_mapping: Mapping of tag names to tag objects
        category_mapping: Mapping of category names to category objects
        
    Returns:
        True if update was successful, False otherwise
    """
    # Prepare update payload
    existing_recipe_cats = details.get("recipeCategory", [])
    payload = {
        "tags": [],
        "recipeCategory": existing_recipe_cats
    }

    # Build tag objects
    tag_objs = []
    for t in new_tags:
        t_lower = t.lower()
        if t_lower in tag_mapping:
            # Use existing tag
            tag_objs.append(tag_mapping[t_lower])
            logger.debug(f"Using existing tag: {t}")
        else:
            # Create new tag
            logger.info(f"Creating new tag: {t}")
            new_tag = await mealie_api.create_tag(t)
            if new_tag:
                tag_objs.append(new_tag)
                # Update mapping for future use
                tag_mapping[t_lower] = new_tag
            else:
                logger.warning(f"Failed to create tag: {t}")
    
    payload["tags"] = tag_objs

    # Handle category update
    if new_category:
        cat_lower = new_category.lower()
        if cat_lower in category_mapping:
            # Use existing category
            payload["recipeCategory"] = [category_mapping[cat_lower]]
            logger.debug(f"Using existing category: {new_category}")
        else:
            # Create new category
            logger.info(f"Creating new category: {new_category}")
            new_cat = await mealie_api.create_category(new_category)
            if new_cat:
                payload["recipeCategory"] = [new_cat]
                # Update mapping for future use
                category_mapping[cat_lower] = new_cat
            else:
                logger.warning(f"Failed to create category: {new_category}")

    # Log update details
    await ha_mqtt.info(
        SCRIPT_CONFIG["id"],
        f"Updating '{recipe_slug}' with tags: {', '.join(new_tags)} | Category: {new_category}",
        category="update"
    )

    # Handle dry run mode
    if DRY_RUN:
        logger.info(f"[DRY-RUN] Would update {recipe_slug} with tags: {new_tags}, category: {new_category}")
        await ha_mqtt.info(SCRIPT_CONFIG["id"],
                  f"[DRY-RUN] Would update {recipe_slug} with PATCH", category="skip")
        return True

    # Perform the update
    ok = await mealie_api.update_recipe_tags_categories(recipe_slug, payload)
    if ok:
        logger.info(f"Successfully updated {recipe_slug}")
        await ha_mqtt.success(SCRIPT_CONFIG["id"],
                  f"Successfully updated {recipe_slug} with tags: {', '.join(new_tags)} | Category: {new_category}")
        return True
    else:
        logger.error(f"Failed to update {recipe_slug}")
        await ha_mqtt.error(SCRIPT_CONFIG["id"],
                  f"Error updating {recipe_slug}")
        return False

def extract_ingredients(recipe_details: Dict[str, Any]) -> List[str]:
    """
    Extract ingredient names from recipe details.
    
    Args:
        recipe_details: Recipe details from Mealie API
        
    Returns:
        List of ingredient names
    """
    ingredients = []
    
    for ing in recipe_details.get("recipeIngredient", []):
        # Extract food name if available
        if ing.get("food") and "name" in ing["food"]:
            ingredients.append(ing["food"]["name"])
    
    return ingredients


async def main() -> None:
    """
    Main function that processes all recipes in Mealie.
    
    This function:
    1. Fetches all recipes from Mealie
    2. Preloads existing tags and categories
    3. Processes each recipe to classify and update it
    """
    try:
        # Initialize statistics
        stats = {
            "total_recipes": 0,
            "processed": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }
        
        # 1. Fetch all recipes
        await ha_mqtt.info(SCRIPT_CONFIG["id"], "Fetching recipes from Mealie...", category="start")
        recipes = await mealie_api.get_all_recipes()
        if not recipes:
            logger.warning("No recipes found in Mealie")
            await ha_mqtt.warning(SCRIPT_CONFIG["id"], "No recipes found.")
            return

        stats["total_recipes"] = len(recipes)
        await ha_mqtt.success(SCRIPT_CONFIG["id"], f"Fetched {len(recipes)} recipes.")
        logger.info(f"Fetched {len(recipes)} recipes from Mealie")

        # 2. Preload tags and categories
        await ha_mqtt.info(SCRIPT_CONFIG["id"], "Preloading Mealie tags & categories...", category="data")
        all_tags = await mealie_api.get_tags()
        all_categories = await mealie_api.get_categories()

        # Create mappings for faster lookups
        tag_mapping = {t["name"].lower(): t for t in all_tags}
        category_mapping = {c["name"].lower(): c for c in all_categories}
        
        logger.info(f"Preloaded {len(all_tags)} tags and {len(all_categories)} categories")

        # 3. Process each recipe
        for index, recipe in enumerate(recipes):
            try:
                slug = recipe["slug"]
                logger.info(f"Processing recipe {index+1}/{len(recipes)}: {slug}")
                
                # Get detailed recipe information
                details = await mealie_api.get_recipe_details(slug)
                if not details:
                    logger.warning(f"Could not fetch details for recipe: {slug}")
                    stats["errors"] += 1
                    continue

                # Extract ingredients
                ingredients = extract_ingredients(details)
                if not ingredients:
                    logger.warning(f"Recipe '{recipe['name']}' has no valid ingredients")
                    await ha_mqtt.warning(
                        SCRIPT_CONFIG["id"],
                        f"Recipe '{recipe['name']}' has no valid ingredients. Skipping classification."
                    )
                    stats["skipped"] += 1
                    continue

                # Classify recipe using GPT
                new_tags, new_category = await classify_recipe_with_gpt(recipe["name"], ingredients)
                
                # Update recipe if we have tags or category
                if new_tags or new_category:
                    success = await update_recipe(
                        slug, details, new_tags, new_category, tag_mapping, category_mapping
                    )
                    if success:
                        stats["updated"] += 1
                else:
                    logger.info(f"No tags or category assigned for {slug}, skipping update")
                    stats["skipped"] += 1
                
                stats["processed"] += 1
                
                # Update progress
                if index % 5 == 0 or index == len(recipes) - 1:
                    progress = f"Progress: {index+1}/{len(recipes)} recipes processed"
                    await ha_mqtt.progress(SCRIPT_CONFIG["id"], progress)
                
            except Exception as e:
                logger.error(f"Error processing recipe {recipe.get('slug', 'unknown')}: {str(e)}", exc_info=True)
                await ha_mqtt.error(SCRIPT_CONFIG["id"], f"Error processing recipe: {str(e)}")
                stats["errors"] += 1

        # 4. Log completion
        summary = (
            f"Processing complete! "
            f"Processed {stats['processed']}/{stats['total_recipes']} recipes, "
            f"Updated {stats['updated']}, "
            f"Skipped {stats['skipped']}, "
            f"Errors {stats['errors']}"
        )
        await ha_mqtt.success(SCRIPT_CONFIG["id"], summary)
        logger.info(summary)
        
    except Exception as e:
        error_msg = f"Error in recipe tagger: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await ha_mqtt.error(SCRIPT_CONFIG["id"], error_msg)

# Assign main function to execute_function
SCRIPT_CONFIG["execute_function"] = main

if __name__ == "__main__":
    asyncio.run(main())
