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

from core.plugin import Plugin
from core.services import MqttService, MealieApiService, GptService

# Configure logging
logger = logging.getLogger(__name__)

class RecipeTaggerPlugin(Plugin):
    """Plugin for tagging recipes in Mealie using GPT."""
    
    def __init__(self, mqtt_service: MqttService, mealie_service: MealieApiService, gpt_service: GptService):
        """
        Initialize the RecipeTaggerPlugin.
        
        Args:
            mqtt_service: Service for MQTT communication
            mealie_service: Service for Mealie API interaction
            gpt_service: Service for GPT interaction
        """
        self._mqtt = mqtt_service
        self._mealie = mealie_service
        self._gpt = gpt_service
        
        # Configuration
        self._dry_run = False  # Set to True to skip updating Mealie
        self._model_name = "gpt-4o"
        self._temperature = 0.1
        
        # Available tags and categories for classification
        self._available_tags = {
            "Main Ingredient Category": [
                "Red Meat", "Poultry", "Fish", "Seafood", "Eggs", "Dairy",
                "Legumes", "Grains", "Vegetables", "Fruits", "Mushrooms", "Nuts"
            ],
            "Nutritional Profile and Dietary Preferences": [
                "Normal", "Vegetarian", "Vegan", "High Protein", "Low Carb",
                "High Fiber", "Low-Calorie", "High Fat", "Iron-Rich", "Calcium-Rich",
                "Vitamin-Packed"
            ],
            "Time & Effort": ["Quick", "30 min", "Long-Cooking", "Meal Prep-Friendly"]
        }

        self._available_categories = [
            "Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Appetizer",
            "Side Dish", "Soup", "Salad", "Smoothie", "Sauce/Dressing", "Baked Goods"
        ]

        # Create sets of all valid tags and categories for faster validation
        self._all_valid_tags: Set[str] = set()
        for category in self._available_tags.values():
            self._all_valid_tags.update(category)

        self._valid_categories: Set[str] = set(self._available_categories)
    
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
        return "recipe_tagger"
    
    @property
    def name(self) -> str:
        """Human-readable name for the plugin."""
        return "Recipe Tagger"
    
    @property
    def description(self) -> str:
        """Description of what the plugin does."""
        return "Classifies recipes in Mealie by assigning tags and categories using GPT."
    
    @property
    def reset_sensors(self):
        """Sensors that need to be reset"""
        return ["feedback"]
    
    def get_mqtt_entities(self) -> Dict[str, Any]:
        """
        Get MQTT entities configuration for Home Assistant.
        
        Returns:
            A dictionary containing the MQTT entity configuration for this plugin.
        """
        return {
            "switch": True,
            "sensors": {
                "feedback": {"id": "feedback", "name": "Tagging Feedback"},
                "progress": {"id": "progress", "name": "Tagging Progress"}
            }
        }
    
    async def classify_recipe_with_gpt(
        self,
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
            await self._mqtt.warning(self.id, f"Recipe '{name}' has no valid ingredients, skipping classification.")
            return [], None

        # Construct prompt for GPT
        prompt = (
            "You are a recipe classification assistant. "
            "Classify the following recipe strictly using predefined tags and categories. "
            "DO NOT invent new tags or categories.\n\n"
            f"Recipe Name: '{name}'\n"
            f"Ingredients: {', '.join(clean_ingredients)}\n\n"
            f"Allowed Tags:\n"
            f"- Main Ingredients: {', '.join(self._available_tags['Main Ingredient Category'])}\n"
            f"- Nutritional Profile: {', '.join(self._available_tags['Nutritional Profile and Dietary Preferences'])}\n"
            f"- Time & Effort: {', '.join(self._available_tags['Time & Effort'])}\n\n"
            f"Allowed Categories:\n"
            f"- {', '.join(self._available_categories)}\n\n"
            "Return JSON in the following format:\n"
            '{"tags": ["tag1", "tag2"], "category": "chosen_category"}'
        )

        # Call GPT
        messages = [{"role": "user", "content": prompt}]
        logger.debug(f"Classifying recipe: {name}")
        result = await self._gpt.gpt_json_chat(messages, temperature=self._temperature)

        # Extract and validate tags
        raw_tags = result.get("tags", [])
        category = result.get("category", None)

        # Filter out invalid tags
        filtered_tags = [t for t in raw_tags if t in self._all_valid_tags]
        invalid_tags = [t for t in raw_tags if t not in self._all_valid_tags]

        if invalid_tags:
            logger.warning(f"GPT returned invalid tags for '{name}': {invalid_tags}")
            await self._mqtt.warning(self.id, f"GPT returned invalid tags {invalid_tags}. Ignoring these.")
            await self._mqtt.log(self.id, "feedback", f"GPT returned invalid tags {invalid_tags}. Ignoring these.")

        # Validate category
        if category and category not in self._valid_categories:
            logger.warning(f"GPT returned invalid category for '{name}': {category}")
            await self._mqtt.warning(self.id, f"Invalid category '{category}' received from GPT. Ignoring.")
            await self._mqtt.log(self.id, "feedback", f"Invalid category '{category}' received from GPT. Ignoring.")
            category = None

        logger.info(f"Classification for '{name}': Tags={filtered_tags}, Category={category}")
        return filtered_tags, category

    async def update_recipe(
        self,
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
                new_tag = await self._mealie.create_tag(t)
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
                new_cat = await self._mealie.create_category(new_category)
                if new_cat:
                    payload["recipeCategory"] = [new_cat]
                    # Update mapping for future use
                    category_mapping[cat_lower] = new_cat
                else:
                    logger.warning(f"Failed to create category: {new_category}")

        # Log update details
        await self._mqtt.info(
            self.id,
            f"Updating '{recipe_slug}' with tags: {', '.join(new_tags)} | Category: {new_category}",
            category="update"
        )

        # Handle dry run mode
        if self._dry_run:
            logger.info(f"[DRY-RUN] Would update {recipe_slug} with tags: {new_tags}, category: {new_category}")
            await self._mqtt.info(self.id,
                      f"[DRY-RUN] Would update {recipe_slug} with PATCH", category="skip")
            return True

        # Perform the update
        ok = await self._mealie.update_recipe_tags_categories(recipe_slug, payload)
        if ok:
            logger.info(f"Successfully updated {recipe_slug}")
            await self._mqtt.success(self.id,
                      f"Successfully updated {recipe_slug} with tags: {', '.join(new_tags)} | Category: {new_category}")
            return True
        else:
            logger.error(f"Failed to update {recipe_slug}")
            await self._mqtt.error(self.id,
                      f"Error updating {recipe_slug}")
            return False

    def extract_ingredients(self, recipe_details: Dict[str, Any]) -> List[str]:
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

    async def execute(self) -> None:
        # Reset sensors
        for sensor_id in self.reset_sensors:
            await self._mqtt.reset_sensor(self.id, sensor_id)

        """Execute the recipe tagger plugin."""
        try:
            # Update progress
            await self._mqtt.update_progress(self.id, "progress", 0, "Starting recipe tagging")
            
            # Initialize statistics
            stats = {
                "total_recipes": 0,
                "processed": 0,
                "updated": 0,
                "skipped": 0,
                "errors": 0
            }
            
            # 1. Fetch all recipes
            await self._mqtt.info(self.id, "Fetching recipes from Mealie...", category="start")
            await self._mqtt.update_progress(self.id, "progress", 5, "Fetching recipes from Mealie")
            recipes = await self._mealie.get_all_recipes()
            if not recipes:
                logger.warning("No recipes found in Mealie")
                await self._mqtt.warning(self.id, "No recipes found.")
                await self._mqtt.update_progress(self.id, "progress", 100, "Completed - No recipes found")
                return

            stats["total_recipes"] = len(recipes)
            await self._mqtt.success(self.id, f"Fetched {len(recipes)} recipes.")
            await self._mqtt.update_progress(self.id, "progress", 10, f"Fetched {len(recipes)} recipes")
            logger.debug(f"Fetched {len(recipes)} recipes from Mealie")

            # 2. Preload tags and categories
            await self._mqtt.info(self.id, "Preloading Mealie tags & categories...", category="data")
            await self._mqtt.update_progress(self.id, "progress", 15, "Preloading tags and categories")
            all_tags = await self._mealie.get_tags()
            all_categories = await self._mealie.get_categories()

            # Create mappings for faster lookups
            tag_mapping = {t["name"].lower(): t for t in all_tags}
            category_mapping = {c["name"].lower(): c for c in all_categories}
            
            await self._mqtt.update_progress(self.id, "progress", 20, f"Preloaded {len(all_tags)} tags and {len(all_categories)} categories")
            logger.debug(f"Preloaded {len(all_tags)} tags and {len(all_categories)} categories")

            # 3. Process each recipe
            for index, recipe in enumerate(recipes):
                try:
                    # Calculate percentage (leave 10% for final processing)
                    percentage = 20 + int(70 * (index / len(recipes)))
                    await self._mqtt.update_progress(self.id, "progress", percentage, f"Processing recipe {index+1}/{len(recipes)}")
                    
                    slug = recipe["slug"]
                    logger.debug(f"Processing recipe {index+1}/{len(recipes)}: {slug}")
                    
                    # Get detailed recipe information
                    details = await self._mealie.get_recipe_details(slug)
                    if not details:
                        logger.warning(f"Could not fetch details for recipe: {slug}")
                        stats["errors"] += 1
                        continue

                    # Extract ingredients
                    ingredients = self.extract_ingredients(details)
                    if not ingredients:
                        logger.warning(f"Recipe '{recipe['name']}' has no valid ingredients")
                        await self._mqtt.warning(
                            self.id,
                            f"Recipe '{recipe['name']}' has no valid ingredients. Skipping classification."
                        )
                        stats["skipped"] += 1
                        continue

                    # Classify recipe using GPT
                    new_tags, new_category = await self.classify_recipe_with_gpt(recipe["name"], ingredients)
                    
                    # Update recipe if we have tags or category
                    if new_tags or new_category:
                        success = await self.update_recipe(
                            slug, details, new_tags, new_category, tag_mapping, category_mapping
                        )
                        if success:
                            stats["updated"] += 1
                    else:
                        logger.info(f"No tags or category assigned for {slug}, skipping update")
                        stats["skipped"] += 1
                    
                    stats["processed"] += 1
                    
                    # Update progress text
                    if index % 5 == 0 or index == len(recipes) - 1:
                        progress = f"Progress: {index+1}/{len(recipes)} recipes processed"
                        await self._mqtt.progress(self.id, progress)
                    
                except Exception as e:
                    logger.error(f"Error processing recipe {recipe.get('slug', 'unknown')}: {str(e)}", exc_info=True)
                    await self._mqtt.error(self.id, f"Error processing recipe: {str(e)}")
                    stats["errors"] += 1

            # 4. Log completion
            summary = (
                f"Processing complete! "
                f"Processed {stats['processed']}/{stats['total_recipes']} recipes, "
                f"Updated {stats['updated']}, "
                f"Skipped {stats['skipped']}, "
                f"Errors {stats['errors']}"
            )
            await self._mqtt.success(self.id, summary)
            await self._mqtt.update_progress(self.id, "progress", 100, "Finished")
            logger.info(summary)
            
        except Exception as e:
            error_msg = f"Error in recipe tagger: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._mqtt.error(self.id, error_msg)

