"""
Module: shopping_list_generator
-------------------------------
Generates a consolidated shopping list from the user's upcoming Mealie meal plan,
cleans it up via GPT, and (optionally) updates Mealie with the final list.

This module:
1. Fetches the upcoming meal plan from Mealie
2. Extracts all ingredients from the recipes in the meal plan
3. Uses GPT to consolidate and organize the ingredients into a clean shopping list
4. Creates a new shopping list in Mealie with the consolidated items

The GPT processing helps by:
- Combining similar ingredients (e.g., "2 onions" + "1 onion" = "3 onions")
- Organizing items by category for easier shopping
- Standardizing quantities and units
- Providing feedback on any issues with ingredient specifications
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set

from core.plugin import Plugin
from core.services import MqttService, MealieApiService, GptService

# Configure logging
logger = logging.getLogger(__name__)

class ShoppingListGeneratorPlugin(Plugin):
    """Plugin for generating shopping lists from meal plans."""
    
    def __init__(self, mqtt_service: MqttService, mealie_service: MealieApiService, gpt_service: GptService):
        """
        Initialize the ShoppingListGeneratorPlugin.
        
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
        
        # Plugin configuration
        self._list_length = 8
    
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
        return "shopping_list_generator"
    
    @property
    def name(self) -> str:
        """Human-readable name for the plugin."""
        return "Shopping List Generator"
    
    @property
    def description(self) -> str:
        """Description of what the plugin does."""
        return "Generates a consolidated shopping list from the upcoming meal plan."
    
    def get_mqtt_entities(self) -> Dict[str, Any]:
        """
        Get MQTT entities configuration for Home Assistant.
        
        Returns:
            A dictionary containing the MQTT entity configuration for this plugin.
        """
        return {
            "switch": True,
            "sensors": {
                "status": {"id": "status", "name": "Shopping List Progress"},
                "feedback": {"id": "feedback", "name": "Shopping List Feedback"}
            },
            "numbers": {
                "list_length": {"id": "list_length", "name": "Shopping List Days Required", "value": self._list_length}
            }
        }
    
    async def get_recipe_ingredients(self, recipe_id: str) -> List[Dict[str, Any]]:
        """
        Fetch and extract ingredients from a recipe.
        
        Args:
            recipe_id: The recipe ID to fetch ingredients for
            
        Returns:
            List of ingredient dictionaries with name, quantity, and unit
        """
        recipe_details = await self._mealie.get_recipe_details(recipe_id)
        if not recipe_details:
            logger.warning(f"Could not fetch recipe {recipe_id}")
            await self._mqtt.warning(self.id, f"Could not fetch recipe {recipe_id}")
            return []

        # Extract and normalize ingredient data
        ingredients = []
        for ing in recipe_details.get("recipeIngredient", []):
            if ing.get("food") and ing["food"].get("name"):
                # Normalize whitespace in strings
                name = " ".join(ing["food"]["name"].split())
                unit = " ".join(ing["unit"]["name"].split()) if ing.get("unit") and ing["unit"].get("name") else ""
                
                ingredients.append({
                    "name": name,
                    "quantity": ing.get("quantity", ""),
                    "unit": unit
                })
        
        logger.debug(f"Extracted {len(ingredients)} ingredients from recipe {recipe_id}")
        return ingredients

    async def consolidate_ingredients(self, meal_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Collect all ingredients from all recipes in the meal plan.
        
        Args:
            meal_plan: List of meal plan entries with recipeId
            
        Returns:
            Combined list of all ingredients
        """
        ingredient_list = []
        recipe_count = 0
        
        for meal in meal_plan:
            recipe_id = meal.get("recipeId")
            if not recipe_id:
                continue
                
            recipe_ingredients = await self.get_recipe_ingredients(recipe_id)
            if recipe_ingredients:
                ingredient_list.extend(recipe_ingredients)
                recipe_count += 1
        
        logger.info(f"Collected {len(ingredient_list)} ingredients from {recipe_count} recipes")
        await self._mqtt.success(self.id, f"Collected {len(ingredient_list)} total ingredients from {recipe_count} recipes.")
        return ingredient_list

    async def clean_up_shopping_list(self, ingredients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Use GPT to clean up and organize the shopping list.
        
        This function:
        1. Sorts ingredients by name
        2. Sends them to GPT for consolidation and categorization
        3. Processes the results and logs details
        
        Args:
            ingredients: Raw list of ingredients from recipes
            
        Returns:
            Cleaned and organized shopping list
        """
        await self._mqtt.gpt_decision(self.id, "Using GPT to clean up the shopping list...")
        logger.info(f"Cleaning up shopping list with {len(ingredients)} ingredients")

        # Sort ingredients for more consistent GPT processing
        ingredients_sorted = sorted(ingredients, key=lambda x: x["name"].lower())
        
        # Prepare prompt for GPT
        prompt_content = {
            "ingredients": ingredients_sorted,
            "instructions": {
                "role": "system",
                "content": (
                "You are a grocery shopping assistant. Given the list of ingredients below, "
                "combine similar items and adjust the quantities to realistic package sizes. "
                "Ensure items are grouped logically by category for easier shopping. Categories include:\n\n"
                "- **Dairy** (Milk, Cheese, Butter, Yogurt)\n"
                "- **Meats** (Chicken, Beef, Pork, etc.)\n"
                "- **Fish** (Cod, Daurade, Salmon, etc.)\n"
                "- **Spices** (Salt, Pepper, Garlic Powder, etc.)\n"
                "- **Condiments** (Vinegar, Soy Sauce, etc.)\n"
                "- **Nuts** (Nuts, peanuts, etc.)\n"
                "- **Vegetables** (Onions, Tomatoes, Garlic, Mushrooms, etc.)\n"
                "- **Fruits** (Oranges, Apples, Bananas, etc.)\n"
                "- **Grains & Baking** (Flour, Rice, Pasta, Bread, Yeast)\n"
                "- **Canned & Packaged Goods** (Canned Beans, Sun-dried Tomatoes, etc.)\n"
                "- **Oils & Liquids** (Olive Oil, Vinegar, Beer, etc)\n\n"
                "Rules:\n"
                "1. Maintain consistent categories across runs.\n"
                "2. Use standard package sizes (e.g., 1L milk, 500g flour, 12 eggs).\n"
                "3. Retain at least one item per unique ingredient.\n"
                "4. If an ingredient is missing a quantity or unit, flag it in the `feedback` field.\n"
                "5. If an item does not fit into any category, add it under 'Other' and note it in `feedback`.\n"
                "6. Include a `feedback` field explaining any issues or strange merges.\n"
                "7. DO NOT REMOVE any ingredients unless absolutely necessary.\n\n"
                "**Example JSON Response:**\n"
                "{\n"
                '  "shopping_list": [\n'
                '    { "name": "Salt", "quantity": "500", "unit": "g", "category": "Spices", "merged_items": ["5 tsp salt", "1 tsp salt"] },\n'
                '    { "name": "Eggs", "quantity": "12", "unit": "", "category": "Dairy", "merged_items": ["1 egg", "2 eggs", "9 eggs"] },\n'
                '    { "name": "Onions", "quantity": "3", "unit": "", "category": "Vegetables", "merged_items": ["1 onion", "2 onions"] }\n'
                "  ],\n"
                '  "feedback": [\n'
                '    "⚠️ Item `unknown ingredient` did not fit into any category and was placed under `Other`.",\n'
                '    "⚠️ The ingredient `2 handfuls of flour` had a non-standard quantity and was interpreted as 200g." \n'
                "  ]\n"
                "}"
                )
            }
        }

        # Call GPT
        messages = [{"role": "user", "content": json.dumps(prompt_content)}]
        result = await self._gpt.gpt_json_chat(messages, model=self._model_name, temperature=0)
        
        # Process results
        cleaned_list = result.get("shopping_list", [])
        feedback = result.get("feedback", [])

        # Log results
        await self._mqtt.success(self.id, f"Shopping list consolidated from {len(ingredients)} to {len(cleaned_list)} items.")
        logger.info(f"Shopping list consolidated from {len(ingredients)} to {len(cleaned_list)} items")
        
        # Log item merging details
        await self._mqtt.info(self.id, "\nItem Merging Details:", category="data")
        for item in cleaned_list:
            merged_str = ", ".join(item.get("merged_items", []))
            item_desc = f"{item['quantity']} {item['unit']} {item['name']} ({item['category']})"
            if merged_str:
                item_desc += f"  <-  {merged_str}"
            await self._mqtt.info(self.id, item_desc, category="data")

        # Log any feedback from GPT
        if feedback:
            await self._mqtt.warning(self.id, "\nGPT Feedback:")
            for issue in feedback:
                await self._mqtt.warning(self.id, issue)
                await self._mqtt.log(self.id, "feedback", issue)
                logger.info(f"GPT Feedback: {issue}")

        return cleaned_list

    async def create_mealie_shopping_list(
        self,
        list_name: str, 
        cleaned_list: List[Dict[str, Any]]
    ) -> bool:
        """
        Create a new shopping list in Mealie and add all items.
        
        Args:
            list_name: Name for the new shopping list
            cleaned_list: List of cleaned and organized shopping items
            
        Returns:
            True if successful, False otherwise
        """
        # Create the shopping list
        shopping_list_id = await self._mealie.create_shopping_list(list_name)
        if not shopping_list_id:
            logger.error(f"Failed to create shopping list: {list_name}")
            await self._mqtt.error(self.id, f"Failed to create shopping list: {list_name}")
            return False
            
        logger.info(f"Created shopping list: {list_name} (ID: {shopping_list_id})")
        
        # Add items to the shopping list
        if not cleaned_list:
            logger.warning("No items to add to shopping list")
            await self._mqtt.warning(self.id, "No items to add to shopping list")
            return True
            
        await self._mqtt.info(self.id, "Adding items to Mealie shopping list...", category="update")
        
        success_count = 0
        error_count = 0
        
        for item in cleaned_list:
            # Format the item note
            formatted_note = f"{item['quantity']} {item['unit']} {item['name']}".strip()
            
            # Add to Mealie
            ok = await self._mealie.add_item_to_shopping_list(shopping_list_id, formatted_note)
            if ok:
                success_count += 1
            else:
                error_count += 1
                logger.error(f"Failed to add item to shopping list: {formatted_note}")
                await self._mqtt.error(self.id, f"Failed to add {formatted_note}")
        
        # Log summary
        summary = f"Added {success_count} items to shopping list"
        if error_count > 0:
            summary += f" ({error_count} errors)"
        
        logger.info(summary)
        return True

    async def execute(self) -> None:
        """Execute the shopping list generator plugin."""
        try:
            # Get configuration
            num_days = self._list_length
            list_name = f"Mealplan {datetime.today().strftime('%d %b')}"
            
            await self._mqtt.info(self.id, f"Working on your new shopping list: {list_name}", category="start")
            logger.info(f"Generating shopping list: {list_name} for {num_days} days")

            # Define date range for meal plan
            start_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = (datetime.today() + timedelta(days=num_days)).strftime("%Y-%m-%d")
            
            # Fetch meal plan
            meal_plan = await self._mealie.get_meal_plan(start_date, end_date)
            if not meal_plan:
                logger.warning("No meal plan data available")
                await self._mqtt.warning(self.id, "No meal plan data available.")
                return

            # Extract meal plan entries with recipes
            meal_plan_entries = [
                {"date": item["date"], "recipeId": item["recipeId"]}
                for item in meal_plan if item.get("recipeId")
            ]
            
            if not meal_plan_entries:
                logger.warning("No recipes found in meal plan")
                await self._mqtt.warning(self.id, "No recipes found in meal plan.")
                return
                
            await self._mqtt.info(self.id, f"Found {len(meal_plan_entries)} meal plan entries.", category="data")
            logger.info(f"Found {len(meal_plan_entries)} meal plan entries")

            # Process ingredients
            raw_ingredients = await self.consolidate_ingredients(meal_plan_entries)
            if not raw_ingredients:
                logger.warning("No ingredients found in recipes")
                await self._mqtt.warning(self.id, "No ingredients found in recipes.")
                return
                
            # Clean up shopping list
            cleaned_list = await self.clean_up_shopping_list(raw_ingredients)

            # Handle dry run mode
            if self._dry_run:
                logger.info(f"[DRY-RUN] Would create shopping list: {list_name} with {len(cleaned_list)} items")
                await self._mqtt.info(self.id, f"[DRY-RUN] Would create shopping list: {list_name} with {len(cleaned_list)} items", category="skip")
                return

            # Create shopping list in Mealie
            success = await self.create_mealie_shopping_list(list_name, cleaned_list)
            if success:
                await self._mqtt.success(self.id, "Done! Your Mealie shopping list is updated.")
                logger.info("Shopping list created successfully")
            
        except Exception as e:
            error_msg = f"Error generating shopping list: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._mqtt.error(self.id, error_msg)
