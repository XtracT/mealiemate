"""
Module: ingredient_merger
------------------------
Identifies ingredients across recipes that are different but should be the same,
using GPT to analyze and suggest merges.

This module:
1. Fetches all recipes from Mealie
2. Extracts all unique ingredients across recipes
3. Uses GPT to identify ingredients that should be merged
4. Prompts the user to accept or reject each merge suggestion via Home Assistant
5. Updates recipes in Mealie if the user accepts the suggestion
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Set, Any, Tuple, Optional

from core.plugin import Plugin
from core.services import MqttService, MealieApiService, GptService

# Configure logging
logger = logging.getLogger(__name__)

class IngredientMergerPlugin(Plugin):
    """Plugin for identifying ingredients that should be merged across recipes."""
    
    def __init__(self, mqtt_service: MqttService, mealie_service: MealieApiService, gpt_service: GptService):
        """
        Initialize the IngredientMergerPlugin.
        
        Args:
            mqtt_service: Service for MQTT communication
            mealie_service: Service for Mealie API interaction
            gpt_service: Service for GPT interaction
        """
        self._mqtt = mqtt_service
        self._mealie = mealie_service
        self._gpt = gpt_service
        
        # Configuration
        self._model_name = "gpt-4o"
        self._temperature = 0.1
        self._batch_size = 50  # Number of ingredients to analyze in one GPT call
        
        # State for user interaction
        self._current_suggestion_index = 0
        self._merge_suggestions = []
        self._waiting_for_user_input = False
        self._user_decision_received = asyncio.Event()
        self._user_accepted = False
    
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
        return "ingredient_merger"
    
    @property
    def name(self) -> str:
        """Human-readable name for the plugin."""
        return "Ingredient Merger"
    
    @property
    def description(self) -> str:
        """Description of what the plugin does."""
        return "Identifies ingredients across recipes that should be merged."
    
    def get_mqtt_entities(self) -> Dict[str, Any]:
        """
        Get MQTT entities configuration for Home Assistant.
        
        Returns:
            A dictionary containing the MQTT entity configuration for this plugin.
        """
        return {
            "switch": True,
            "sensors": {
                "feedback": {"id": "feedback", "name": "Merger Feedback"},
                "current_suggestion": {"id": "current_suggestion", "name": "Current Merge Suggestion"},
                "progress": {"id": "progress", "name": "Merger Progress"}
            },
            "buttons": {
                "accept_button": {"id": "accept_button", "name": "Accept Merge"},
                "reject_button": {"id": "reject_button", "name": "Reject Merge"}
            }
        }
    
    def extract_ingredients(self, recipe_details: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract ingredient names and IDs from recipe details.
        
        Args:
            recipe_details: Recipe details from Mealie API
            
        Returns:
            List of dictionaries with ingredient names and IDs
        """
        ingredients = []
        
        for ing in recipe_details.get("recipeIngredient", []):
            # Extract food name and ID if available
            if ing.get("food") and "name" in ing["food"] and "id" in ing["food"]:
                ingredients.append({
                    "name": ing["food"]["name"],
                    "id": ing["food"]["id"]
                })
        
        return ingredients
    
    async def analyze_ingredients_with_gpt(
        self,
        ingredients_by_recipe: Dict[str, List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """
        Use GPT to identify ingredients that should be merged.
        
        Args:
            ingredients_by_recipe: Dictionary mapping recipe slugs to their ingredients
            
        Returns:
            Dictionary with merge suggestions
        """
        # Create a flat list of all unique ingredient names
        all_ingredient_names: Set[str] = set()
        # Also create a mapping from ingredient names to their IDs
        ingredient_ids_by_name: Dict[str, str] = {}
        
        for ingredients in ingredients_by_recipe.values():
            for ingredient in ingredients:
                name = ingredient["name"]
                all_ingredient_names.add(name)
                ingredient_ids_by_name[name] = ingredient["id"]
        
        unique_ingredient_names = list(all_ingredient_names)
        logger.info(f"Found {len(unique_ingredient_names)} unique ingredients across all recipes")
        await self._mqtt.info(self.id, f"Found {len(unique_ingredient_names)} unique ingredients across all recipes")
        
        # Process ingredients in batches to avoid token limits
        results = []
        total_batches = (len(unique_ingredient_names) + self._batch_size - 1) // self._batch_size
        
        for i in range(0, len(unique_ingredient_names), self._batch_size):
            batch = unique_ingredient_names[i:i+self._batch_size]
            batch_num = i // self._batch_size + 1
            
            await self._mqtt.info(
                self.id, 
                f"Processing batch {batch_num}/{total_batches} ({len(batch)} ingredients)"
            )
            
            # Construct prompt for GPT
            prompt = (
                "You are a culinary expert analyzing recipe ingredients. "
                "Your task is to identify ingredients that are EXACT DUPLICATES but have different names. "
                "We are STRICTLY looking for the same ingredient with different naming conventions, "
                "NOT organizing ingredients into categories.\n\n"
                "Examples of ingredients that should be merged (EXACT DUPLICATES with different names):\n"
                "- 'heavy cream' and 'cream 15% fat' (same exact ingredient, different naming)\n"
                "- 'parmesan' and 'parmeggiano' (same cheese, different spelling/language)\n"
                "- 'scallion' and 'green onion' (same exact ingredient, different regional names)\n\n"
                "Examples of ingredients that should NOT be merged (NOT exact duplicates):\n"
                "- 'garlic cloves' and 'garlic powder' (different forms)\n"
                "- 'fresh tomatoes' and 'sun-dried tomatoes' (different preparation)\n"
                "- 'lemon juice' and 'lemon zest' (different parts)\n"
                "- 'red bell pepper' and 'green bell pepper' (different varieties)\n"
                "- 'white wine' and 'red wine' (different varieties)\n"
                "- 'onion' and 'yellow onion' (one is specific, one is general)\n\n"
                "- 'different cheeses or ingredients that might be used interchangeably but are still not the same"
                "STRICT rules for merging:\n"
                "1. ONLY merge ingredients that are EXACTLY the same thing with different names\n"
                "2. DO NOT merge ingredients that are in different forms (fresh vs. dried, whole vs. powder)\n"
                "3. DO NOT merge ingredients that have different preparation methods\n"
                "4. DO NOT merge ingredients that come from different parts of the same source\n"
                "5. DO NOT merge different varieties of an ingredient\n"
                "6. DO NOT merge general ingredients with specific varieties\n\n"
                "Here is a list of ingredients from various recipes:\n"
                f"{', '.join(batch)}\n\n"
                "Analyze this list and identify sets of ingredients that should be merged. "
                "For each set, provide:\n"
                "1. The ingredients that should be merged\n"
                "2. A recommended standardized name - Preferring the american english name. IMPORTANT: You must choose one of the existing ingredient names from the list, do not create a new name\n"
                "3. A brief explanation of why they should be merged\n\n"
                "Return your analysis in the following JSON format:\n"
                "{\n"
                '  "merge_suggestions": [\n'
                "    {\n"
                '      "ingredients": ["ingredient1", "ingredient2", ...],\n'
                '      "recommended_name": "one of the existing ingredient names",\n'
                '      "reason": "brief explanation"\n'
                "    },\n"
                "    ...\n"
                "  ]\n"
                "}\n\n"
                "If you don't find any ingredients that should be merged in this batch, return an empty array for merge_suggestions."
            )
            
            # Call GPT
            messages = [{"role": "user", "content": prompt}]
            logger.debug(f"Sending batch {batch_num} to GPT")
            result = await self._gpt.gpt_json_chat(messages, temperature=self._temperature)
            
            # Extract merge suggestions
            merge_suggestions = result.get("merge_suggestions", [])
            if merge_suggestions:
                results.extend(merge_suggestions)
                await self._mqtt.success(
                    self.id,
                    f"Found {len(merge_suggestions)} merge suggestions in batch {batch_num}"
                )
            else:
                await self._mqtt.info(
                    self.id,
                    f"No merge suggestions found in batch {batch_num}"
                )
        
        # Now find which recipes contain each ingredient that should be merged
        # and add the ingredient IDs to the merge suggestions
        final_results = []
        
        for suggestion in results:
            ingredients_to_merge = suggestion.get("ingredients", [])
            if not ingredients_to_merge:
                continue
                
            # Add ingredient IDs to the suggestion
            suggestion["ingredient_ids"] = {
                name: ingredient_ids_by_name.get(name) 
                for name in ingredients_to_merge 
                if name in ingredient_ids_by_name
            }
            
            # Find recipes containing these ingredients
            recipes_with_ingredients = {}
            for recipe_slug, recipe_ingredients in ingredients_by_recipe.items():
                # Extract just the names from the recipe ingredients
                recipe_ingredient_names = [ing["name"] for ing in recipe_ingredients]
                
                # Check if any of the ingredients to merge are in this recipe
                matching_ingredients = [ing for ing in ingredients_to_merge if ing in recipe_ingredient_names]
                if matching_ingredients:
                    recipes_with_ingredients[recipe_slug] = matching_ingredients
            
            # Add recipes to the suggestion
            suggestion["recipes"] = recipes_with_ingredients
            final_results.append(suggestion)
        
        return {"merge_suggestions": final_results}
    
    async def present_suggestion_to_user(self, suggestion: Dict[str, Any], index: int, total: int) -> bool:
        """
        Present a merge suggestion to the user and wait for their decision.
        
        Args:
            suggestion: The merge suggestion to present
            index: The current suggestion index (1-based)
            total: The total number of suggestions
            
        Returns:
            True if the user accepted the suggestion, False otherwise
        """
        # Reset the event and user decision
        self._user_decision_received.clear()
        self._user_accepted = False
        
        # Extract suggestion details
        ingredients = suggestion.get("ingredients", [])
        recommended = suggestion.get("recommended_name", "")
        reason = suggestion.get("reason", "")
        recipes = suggestion.get("recipes", {})
        
        # Create a markdown-formatted message for the current suggestion
        markdown = [f"## Merge Suggestion {index}/{total}", ""]
        markdown.append(f"**Merge these ingredients:** {', '.join(ingredients)}")
        markdown.append(f"**Into standardized name:** {recommended}")
        markdown.append(f"**Reason:** {reason}")
        
        # Add recipe information
        if recipes:
            markdown.append("")
            markdown.append(f"**Found in {len(recipes)} recipes:**")
            recipe_list = []
            for recipe_slug, matching_ingredients in recipes.items():
                recipe_name = recipe_slug.replace("-", " ").title()
                ingredients_used = ", ".join(matching_ingredients)
                recipe_list.append(f"- {recipe_name} (uses: {ingredients_used})")
            markdown.append("\n".join(recipe_list))
        
        markdown.append("")
        markdown.append("**Do you want to merge these ingredients?**")
        markdown.append("Use the Accept or Reject buttons below.")
        
        # Log the suggestion to the current_suggestion sensor
        await self._mqtt.log(self.id, "current_suggestion", "\n".join(markdown), reset=True)
        
        # Wait for user decision with a timeout
        try:
            # Wait for the user decision or timeout
            # The main application will handle the button presses and set the event
            await asyncio.wait_for(self._user_decision_received.wait(), timeout=3600)  # 1 hour timeout
            
            return self._user_accepted
        except asyncio.TimeoutError:
            await self._mqtt.warning(self.id, "User decision timeout. Skipping this suggestion.")
            return False
    
    async def update_recipe_ingredients(self, recipe_slug: str, old_ingredient: str, new_ingredient: str) -> bool:
        """
        Update a recipe's ingredients in Mealie.
        
        Args:
            recipe_slug: The recipe slug
            old_ingredient: The old ingredient name to replace
            new_ingredient: The new ingredient name to use
            
        Returns:
            True if the update was successful, False otherwise
        """
        try:
            # Use the MealieApiService to update the recipe ingredient
            success = await self._mealie.update_recipe_ingredient(recipe_slug, old_ingredient, new_ingredient)
            
            if success:
                logger.info(f"Updated recipe '{recipe_slug}': replaced '{old_ingredient}' with '{new_ingredient}'")
            else:
                logger.warning(f"Failed to update recipe '{recipe_slug}'")
                
            return success
                
        except Exception as e:
            logger.error(f"Error updating recipe '{recipe_slug}': {str(e)}", exc_info=True)
            return False
    
    async def setup(self) -> None:
        """Set up the plugin's MQTT entities."""
        # Skip entity registration - entities are already registered at startup in main.py
        # This prevents the switch from being reset to OFF after it's turned ON
        pass
    
    async def execute(self) -> None:
        """Execute the ingredient merger plugin."""
        try:
            # Initialize
            await self.setup()
            await self._mqtt.info(self.id, "Starting ingredient merger analysis...")
            
            # Update progress sensor
            await self._mqtt.update_progress(self.id, "progress", 0, "Starting ingredient merger")
            
            # 1. Fetch all recipes
            await self._mqtt.info(self.id, "Fetching recipes from Mealie...")
            await self._mqtt.update_progress(self.id, "progress", 5, "Fetching recipes")
            recipes = await self._mealie.get_all_recipes()
            if not recipes:
                logger.warning("No recipes found in Mealie")
                await self._mqtt.warning(self.id, "No recipes found.")
                return

            await self._mqtt.success(self.id, f"Fetched {len(recipes)} recipes.")
            logger.debug(f"Fetched {len(recipes)} recipes from Mealie")
            await self._mqtt.update_progress(self.id, "progress", 10, "Extracting ingredients")
            
            # 2. Extract ingredients from each recipe
            ingredients_by_recipe = {}
            
            for index, recipe in enumerate(recipes):
                try:
                    slug = recipe["slug"]
                    
                    # Get detailed recipe information
                    details = await self._mealie.get_recipe_details(slug)
                    if not details:
                        logger.warning(f"Could not fetch details for recipe: {slug}")
                        continue

                    # Extract ingredients
                    ingredients = self.extract_ingredients(details)
                    if ingredients:
                        ingredients_by_recipe[slug] = ingredients
                    
                    # Update progress
                    if index % 10 == 0 or index == len(recipes) - 1:
                        progress = f"Progress: {index+1}/{len(recipes)} recipes processed"
                        await self._mqtt.progress(self.id, progress)
                        progress_percentage = 10 + int(20 * (index / len(recipes)))
                        await self._mqtt.update_progress(self.id, "progress", progress_percentage, f"Extracting ingredients ({index+1}/{len(recipes)})")
                    
                except Exception as e:
                    logger.error(f"Error processing recipe {recipe.get('slug', 'unknown')}: {str(e)}", exc_info=True)
                    await self._mqtt.error(self.id, f"Error processing recipe: {str(e)}")
            
            # 3. Analyze ingredients with GPT
            await self._mqtt.info(self.id, "Analyzing ingredients with GPT...")
            await self._mqtt.update_progress(self.id, "progress", 30, "Analyzing ingredients with GPT")
            results = await self.analyze_ingredients_with_gpt(ingredients_by_recipe)
            
            # 4. Process results
            self._merge_suggestions = results.get("merge_suggestions", [])
            if not self._merge_suggestions:
                await self._mqtt.info(self.id, "No ingredients found that should be merged.")
                await self._mqtt.update_progress(self.id, "progress", 100, "Finished - No merge suggestions found")
                return
                
            summary = f"Found {len(self._merge_suggestions)} sets of ingredients that should be merged"
            await self._mqtt.success(self.id, summary)
            await self._mqtt.update_progress(self.id, "progress", 40, f"Found {len(self._merge_suggestions)} merge suggestions")
            
            # Create a concise, markdown-formatted summary for Home Assistant
            markdown_summary = ["## Ingredient Merger Results", ""]
            markdown_summary.append(f"Found **{len(self._merge_suggestions)}** sets of ingredients that should be merged.")
            markdown_summary.append("")
            markdown_summary.append("Each suggestion will be presented for your approval.")
            markdown_summary.append("")
            
            # Log the markdown summary to the feedback sensor
            await self._mqtt.log(self.id, "feedback", "\n".join(markdown_summary), reset=True)
            
            # 5. Present each suggestion to the user and process their decisions
            accepted_count = 0
            rejected_count = 0
            
            # The remaining 60% of progress will be distributed across user interactions
            remaining_progress = 60
            progress_per_suggestion = remaining_progress / len(self._merge_suggestions)
            
            for i, suggestion in enumerate(self._merge_suggestions):
                # Present the suggestion to the user
                current_progress = 40 + int(progress_per_suggestion * i)
                await self._mqtt.update_progress(self.id, "progress", current_progress, f"Processing suggestion {i+1}/{len(self._merge_suggestions)}")
                
                user_accepted = await self.present_suggestion_to_user(
                    suggestion, i+1, len(self._merge_suggestions)
                )
                
                if user_accepted:
                    accepted_count += 1
                    await self._mqtt.success(
                        self.id, 
                        f"Accepted suggestion {i+1}/{len(self._merge_suggestions)}"
                    )
                    
                    # Get the ingredients to merge and the recommended name
                    ingredients = suggestion.get("ingredients", [])
                    recommended = suggestion.get("recommended_name", "")
                    ingredient_ids = suggestion.get("ingredient_ids", {})
                    
                    # Use the Mealie API's dedicated merge endpoint
                    merge_success_count = 0
                    merge_fail_count = 0
                    
                    # Get the ID of the recommended ingredient
                    recommended_id = ingredient_ids.get(recommended)
                    if not recommended_id:
                        logger.warning(f"Could not find ID for recommended ingredient: {recommended}")
                        await self._mqtt.warning(
                            self.id,
                            f"Could not find ID for recommended ingredient: {recommended}"
                        )
                        continue
                    
                    for ingredient in ingredients:
                        if ingredient != recommended:  # Skip if it's already the recommended name
                            # Get the ID of the ingredient to merge
                            ingredient_id = ingredient_ids.get(ingredient)
                            
                            # If exact match not found, try case-insensitive match
                            if not ingredient_id:
                                ingredient_lower = ingredient.lower()
                                for name, id in ingredient_ids.items():
                                    if name.lower() == ingredient_lower:
                                        ingredient_id = id
                                        logger.debug(f"Found case-insensitive match for '{ingredient}': {name} (ID: {id})")
                                        break
                            
                            # If still not found, try partial match
                            if not ingredient_id:
                                ingredient_lower = ingredient.lower()
                                for name, id in ingredient_ids.items():
                                    if ingredient_lower in name.lower() or name.lower() in ingredient_lower:
                                        ingredient_id = id
                                        logger.debug(f"Found partial match for '{ingredient}': {name} (ID: {id})")
                                        break
                            
                            if not ingredient_id:
                                logger.warning(f"Could not find ID for ingredient: {ingredient}")
                                await self._mqtt.warning(
                                    self.id,
                                    f"Could not find ID for ingredient: {ingredient}"
                                )
                                merge_fail_count += 1
                                continue
                            
                            logger.debug(f"Merging '{ingredient}' (ID: {ingredient_id}) into '{recommended}' (ID: {recommended_id})")
                            await self._mqtt.info(
                                self.id,
                                f"Merging '{ingredient}' into '{recommended}'..."
                            )
                            
                            # Use the IDs for the merge operation
                            success = await self._mealie.merge_foods(ingredient_id, recommended_id)
                            
                            if success:
                                merge_success_count += 1
                                logger.info(f"Successfully merged '{ingredient}' into '{recommended}'")
                                await self._mqtt.success(
                                    self.id,
                                    f"Successfully merged '{ingredient}' into '{recommended}'"
                                )
                            else:
                                merge_fail_count += 1
                                logger.warning(f"Failed to merge '{ingredient}' into '{recommended}'")
                                await self._mqtt.warning(
                                    self.id,
                                    f"Failed to merge '{ingredient}' into '{recommended}'"
                                )
                    
                    # Log the merge results
                    if merge_success_count > 0:
                        await self._mqtt.success(
                            self.id,
                            f"Successfully merged {merge_success_count} ingredients"
                        )
                    if merge_fail_count > 0:
                        await self._mqtt.warning(
                            self.id,
                            f"Failed to merge {merge_fail_count} ingredients"
                        )
                else:
                    rejected_count += 1
                    await self._mqtt.info(
                        self.id, 
                        f"Rejected suggestion {i+1}/{len(self._merge_suggestions)}"
                    )
            
            # 6. Complete with summary
            final_summary = [
                "## Ingredient Merger Complete",
                "",
                f"Processed **{len(self._merge_suggestions)}** merge suggestions:",
                f"- **{accepted_count}** accepted and updated in Mealie",
                f"- **{rejected_count}** rejected",
                ""
            ]
            
            await self._mqtt.update_progress(self.id, "progress", 100, "Finished")
            
            # Clear the current suggestion display
            await self._mqtt.log(self.id, "current_suggestion", "All suggestions have been processed.", reset=True)
            
            # Update the feedback with the final summary
            await self._mqtt.log(self.id, "feedback", "\n".join(final_summary), reset=True)
            
            # Log a success message
            await self._mqtt.success(
                self.id, 
                f"Ingredient merger complete! Accepted: {accepted_count}, Rejected: {rejected_count}"
            )
            
        except Exception as e:
            error_msg = f"Error in ingredient merger: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._mqtt.error(self.id, error_msg)
