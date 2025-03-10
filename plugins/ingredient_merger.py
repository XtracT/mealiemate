"""
Module: ingredient_merger
------------------------
Identifies ingredients across recipes that are different but should be the same,
using GPT to analyze and suggest merges.

This module:
1. Fetches all recipes from Mealie
2. Extracts all unique ingredients across recipes
3. Uses GPT to identify ingredients that should be merged
4. Outputs the results in JSON format for future automated fixing
"""

import asyncio
import logging
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
                "feedback": {"id": "feedback", "name": "Merger Feedback"}
            }
        }
    
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
    
    async def analyze_ingredients_with_gpt(
        self,
        ingredients_by_recipe: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Use GPT to identify ingredients that should be merged.
        
        Args:
            ingredients_by_recipe: Dictionary mapping recipe slugs to their ingredients
            
        Returns:
            Dictionary with merge suggestions
        """
        # Create a flat list of all unique ingredients
        all_ingredients: Set[str] = set()
        for ingredients in ingredients_by_recipe.values():
            all_ingredients.update(ingredients)
        
        unique_ingredients = list(all_ingredients)
        logger.info(f"Found {len(unique_ingredients)} unique ingredients across all recipes")
        await self._mqtt.info(self.id, f"Found {len(unique_ingredients)} unique ingredients across all recipes")
        
        # Process ingredients in batches to avoid token limits
        results = []
        total_batches = (len(unique_ingredients) + self._batch_size - 1) // self._batch_size
        
        for i in range(0, len(unique_ingredients), self._batch_size):
            batch = unique_ingredients[i:i+self._batch_size]
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
                "2. A recommended standardized name\n"
                "3. A brief explanation of why they should be merged\n\n"
                "Return your analysis in the following JSON format:\n"
                "{\n"
                '  "merge_suggestions": [\n'
                "    {\n"
                '      "ingredients": ["ingredient1", "ingredient2", ...],\n'
                '      "recommended_name": "standardized name",\n'
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
            result = await self._gpt.gpt_json_chat(messages, model=self._model_name, temperature=self._temperature)
            
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
        final_results = []
        
        for suggestion in results:
            ingredients_to_merge = suggestion.get("ingredients", [])
            if not ingredients_to_merge:
                continue
                
            # Find recipes containing these ingredients
            recipes_with_ingredients = {}
            for recipe_slug, recipe_ingredients in ingredients_by_recipe.items():
                # Check if any of the ingredients to merge are in this recipe
                matching_ingredients = [ing for ing in ingredients_to_merge if ing in recipe_ingredients]
                if matching_ingredients:
                    recipes_with_ingredients[recipe_slug] = matching_ingredients
            
            # Add recipes to the suggestion
            suggestion["recipes"] = recipes_with_ingredients
            final_results.append(suggestion)
        
        return {"merge_suggestions": final_results}
    
    async def execute(self) -> None:
        """Execute the ingredient merger plugin."""
        try:
            # Initialize
            await self._mqtt.info(self.id, "Starting ingredient merger analysis...")
            
            # 1. Fetch all recipes
            await self._mqtt.info(self.id, "Fetching recipes from Mealie...")
            recipes = await self._mealie.get_all_recipes()
            if not recipes:
                logger.warning("No recipes found in Mealie")
                await self._mqtt.warning(self.id, "No recipes found.")
                return

            await self._mqtt.success(self.id, f"Fetched {len(recipes)} recipes.")
            logger.debug(f"Fetched {len(recipes)} recipes from Mealie")
            
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
                    
                except Exception as e:
                    logger.error(f"Error processing recipe {recipe.get('slug', 'unknown')}: {str(e)}", exc_info=True)
                    await self._mqtt.error(self.id, f"Error processing recipe: {str(e)}")
            
            # 3. Analyze ingredients with GPT
            await self._mqtt.info(self.id, "Analyzing ingredients with GPT...")
            results = await self.analyze_ingredients_with_gpt(ingredients_by_recipe)
            
            # 4. Log results
            merge_suggestions = results.get("merge_suggestions", [])
            if merge_suggestions:
                summary = f"Found {len(merge_suggestions)} sets of ingredients that should be merged"
                await self._mqtt.success(self.id, summary)
                
                # Store the full JSON results for potential future automation
                import json
                formatted_json = json.dumps(results, indent=2)
                
                # Create a concise, markdown-formatted summary for Home Assistant
                markdown_summary = ["## Ingredient Merger Results", ""]
                markdown_summary.append(f"Found **{len(merge_suggestions)}** sets of ingredients that should be merged.")
                markdown_summary.append("")
                
                for i, suggestion in enumerate(merge_suggestions):
                    ingredients = suggestion.get("ingredients", [])
                    recommended = suggestion.get("recommended_name", "")
                    reason = suggestion.get("reason", "")
                    recipes = suggestion.get("recipes", {})
                    
                    # Add a header for each merge suggestion
                    markdown_summary.append(f"### {i+1}. Merge: {', '.join(ingredients)}")
                    markdown_summary.append(f"**Recommended name:** {recommended}")
                    markdown_summary.append(f"**Reason:** {reason}")
                    
                    # Add recipe information in a clean format
                    if recipes:
                        markdown_summary.append("")
                        markdown_summary.append(f"**Found in {len(recipes)} recipes:**")
                        recipe_list = []
                        for recipe_slug, matching_ingredients in recipes.items():
                            recipe_name = recipe_slug.replace("-", " ").title()
                            ingredients_used = ", ".join(matching_ingredients)
                            recipe_list.append(f"- {recipe_name} (uses: {ingredients_used})")
                        markdown_summary.append("\n".join(recipe_list))
                    
                    # Add a separator between merge suggestions
                    markdown_summary.append("")
                    markdown_summary.append("---")
                    markdown_summary.append("")
                
                # Log the markdown summary to the feedback sensor
                await self._mqtt.log(self.id, "feedback", "\n".join(markdown_summary), reset=True)
                
                # Log a shorter summary to the status sensor
                status_summary = [f"Found {len(merge_suggestions)} sets of ingredients that should be merged."]
                for i, suggestion in enumerate(merge_suggestions):
                    ingredients = suggestion.get("ingredients", [])
                    recommended = suggestion.get("recommended_name", "")
                    status_summary.append(f"{i+1}. Merge: {', '.join(ingredients)} → {recommended}")
                
                await self._mqtt.log(self.id, "status", "\n".join(status_summary), reset=True)
            else:
                await self._mqtt.info(self.id, "No ingredients found that should be merged.")
            
            # 5. Complete
            await self._mqtt.success(self.id, "Ingredient merger analysis complete!")
            
        except Exception as e:
            error_msg = f"Error in ingredient merger: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._mqtt.error(self.id, error_msg)
