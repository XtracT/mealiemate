"""
Module: meal_planner
--------------------
Generates structured, balanced meal plans based on existing recipes, user constraints,
and number of days requested, then updates Mealie accordingly.

This module uses OpenAI's GPT model to intelligently create meal plans that follow
specific rules (e.g., pizza on Fridays, balanced nutrition) while considering
user preferences and existing plans.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from core.plugin import Plugin
from core.services import MqttService, MealieApiService, GptService

# Configure logging
logger = logging.getLogger(__name__)

class MealPlannerPlugin(Plugin):
    """Plugin for generating meal plans using GPT."""
    
    def __init__(self, mqtt_service: MqttService, mealie_service: MealieApiService, gpt_service: GptService):
        """
        Initialize the MealPlannerPlugin.
        
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
        self._mealplan_length = 7
        self._mealplan_message = "Generate a mealplan please."
        
        # GPT system prompt configuration
        self._default_config = (
            "Generate a meal plan as JSON. Fill in missing days only, do not modify existing meals.\n\n"
            "Rules:\n"
            "- Pizza on Friday dinner only, once per week.\n"
            "- Salads are preferred for dinners.\n"
            "- Ensure daily balance of protein, vegetables, and carbs.\n"
            "- Do not repeat the same main ingredient two days in a row.\n"
            "- Avoid recipes used in the last two weeks when possible.\n"
            "- Weekend lunches can be heavier than weekdays.\n"
            "- All meals must be real recipe IDs from the catalog.\n"
            "- Prioritize user requests while maintaining balance.\n\n"
            "Output format (return only this JSON, no extra text):\n"
            "{\n"
            '    "mealPlan": {\n'
            '        "YYYY-MM-DD": {\n'
            '            "Lunch": "recipe_id",\n'
            '            "Dinner": "recipe_id"\n'
            "        }\n"
            "    },\n"
            '    "feedback": "Brief summary of choices and suggestions."\n'
            "}"
        )
    
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
        return "meal_planner"
    
    @property
    def name(self) -> str:
        """Human-readable name for the plugin."""
        return "Meal Planner"
    
    @property
    def description(self) -> str:
        """Description of what the plugin does."""
        return "Generates structured, balanced meal plans based on existing recipes."
    
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
                "feedback": {"id": "feedback", "name": "Planning Feedback"},
                "progress": {"id": "progress", "name": "Planning Progress"}
            },
            "numbers": {
                "mealplan_length": {
                    "id": "mealplan_length",
                    "name": "Mealplan Days Required",
                    "value": self._mealplan_length,
                    "type": "int",
                    "min": 1,
                    "max": 30,
                    "step": 1,
                    "unit": "days"
                }
            },
            "texts": {
                "mealplan_message": {"id": "mealplan_message", "name": "Mealplan User Input", "text": self._mealplan_message}
            }
        }
    
    async def async_generate_plan_and_feedback(
        self,
        recipes: List[Dict[str, Any]], 
        mealplan: List[Dict[str, Any]], 
        days: List[str], 
        user_message: str
    ) -> Tuple[Dict[str, Dict[str, str]], str]:
        """
        Calls GPT to generate meal plan JSON plus a feedback string.
        
        Args:
            recipes: List of recipe dictionaries with id, name, tags, etc.
            mealplan: Current meal plan entries
            days: List of days (YYYY-MM-DD format) to generate meals for
            user_message: User input message with preferences/constraints
            
        Returns:
            Tuple of (meal_plan_dict, feedback_string)
        """
        await self._mqtt.gpt_decision(self.id, "Generating meal plan with AI...")
        logger.info(f"Generating meal plan for {len(days)} days with user message: {user_message[:50]}...")

        # Prepare data for GPT
        user_content = json.dumps({
            "days": days,
            "recipesCatalog": recipes,
            "currentMealPlan": mealplan,
            "userRequest": user_message
        }, indent=2)

        messages = [
            {"role": "system", "content": self._default_config},
            {"role": "user", "content": user_content}
        ]

        # Call GPT
        result = await self._gpt.gpt_json_chat(messages, temperature=self._temperature)
        
        # Process results
        meal_plan_obj = result.get("mealPlan", {})
        feedback_str = result.get("feedback", "")
        
        if not meal_plan_obj:
            logger.warning("GPT returned empty meal plan")
            
        if not feedback_str:
            logger.warning("GPT returned empty feedback")

        # Format the plan
        plan_days = {
            day: {
                "Lunch": slots.get("Lunch", ""),
                "Dinner": slots.get("Dinner", "")
            }
            for day, slots in meal_plan_obj.items()
        }

        logger.info(f"Generated meal plan for {len(plan_days)} days")
        return plan_days, feedback_str

    def build_id_to_name(self, recipes: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Build a mapping from recipe IDs to recipe names.
        
        Args:
            recipes: List of recipe dictionaries
            
        Returns:
            Dictionary mapping recipe IDs to names
        """
        return {r["id"]: r["name"] for r in recipes}

    def generate_days_list(self, latest_date: str, num_days: int) -> List[str]:
        """
        Generate a list of days that need meal planning.
        
        Args:
            latest_date: The latest date in the current meal plan (YYYY-MM-DD)
            num_days: Number of days to plan for
            
        Returns:
            List of dates (YYYY-MM-DD format) that need planning
        """
        latest = datetime.strptime(latest_date, "%Y-%m-%d")
        today = datetime.today()
        start_date = max(latest, today) + timedelta(days=1)
        end_date = today + timedelta(days=num_days)

        if start_date > end_date:
            logger.info("No days need planning (current plan extends beyond requested days)")
            return []
            
        days_list = [
            (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((end_date - start_date).days + 1)
        ]
        
        logger.info(f"Generated {len(days_list)} days to plan: {days_list}")
        return days_list

    async def execute(self) -> None:
        """Execute the meal planner plugin."""

        # Reset sensors
        for sensor_id in self.reset_sensors:
            await self._mqtt.reset_sensor(self.id, sensor_id)

        try:
            # Get configuration from MQTT entities
            num_days = self._mealplan_length
            user_message = self._mealplan_message

            # Update progress
            await self._mqtt.update_progress(self.id, "progress", 0, "Starting meal planning")
            await self._mqtt.info(self.id, "Starting meal planning process...", category="start")

            # 1) Fetch all recipes
            await self._mqtt.info(self.id, "Fetching recipes from Mealie...", category="data")
            await self._mqtt.update_progress(self.id, "progress", 10, "Fetching recipes")
            raw_recipes = await self._mealie.fetch_data("/api/recipes?full=true")
            if not raw_recipes or not isinstance(raw_recipes, dict):
                error_msg = "Could not fetch recipes from Mealie."
                await self._mqtt.error(self.id, error_msg)
                logger.error(error_msg)
                return

            # Extract relevant recipe data for GPT
            recipes = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    # Description omitted as it doesn't add value for meal planning
                    "tags": [t["name"] for t in r.get("tags", [])],
                    "categories": [c["name"] for c in r.get("recipeCategory", [])]
                }
                for r in raw_recipes.get("items", [])
            ]
            
            logger.info(f"Fetched {len(recipes)} recipes from Mealie")
            await self._mqtt.info(self.id, f"Found {len(recipes)} recipes", category="data")
            await self._mqtt.update_progress(self.id, "progress", 25, f"Found {len(recipes)} recipes")

            # 2) Fetch current meal plan
            await self._mqtt.info(self.id, "Fetching current meal plan...", category="data")
            await self._mqtt.update_progress(self.id, "progress", 35, "Fetching current meal plan")
            # Include past 15 days to avoid repeating recent meals
            start_date = (datetime.today() - timedelta(days=15)).strftime("%Y-%m-%d")
            end_date = (datetime.today() + timedelta(days=num_days)).strftime("%Y-%m-%d")
            
            mealplan_items = await self._mealie.get_meal_plan(start_date, end_date)
            if not mealplan_items:
                await self._mqtt.info(self.id, "No existing meal plan found — starting fresh.", category="data")
                mealplan_items = []
            
            logger.info(f"Fetched {len(mealplan_items)} meal plan entries")
            
            # Simplify meal plan data for GPT
            mealplan = [
                {
                    "date": r["date"],
                    "recipeId": r["recipeId"]
                }
                for r in mealplan_items
            ]

            # 3) Determine which days need planning
            await self._mqtt.info(self.id, "Determining days that need planning...", category="progress")
            await self._mqtt.update_progress(self.id, "progress", 45, "Determining days to plan")
            latest_date = max((x["date"] for x in mealplan_items), default=datetime.now().strftime("%Y-%m-%d"))
            days = self.generate_days_list(latest_date, num_days)
            
            if not days:
                await self._mqtt.success(self.id, "No days need planning")
                await self._mqtt.update_progress(self.id, "progress", 100, "Finished - No days need planning")
                return

            await self._mqtt.info(self.id, f"Planning meals for {len(days)} days", category="progress")
            await self._mqtt.update_progress(self.id, "progress", 50, f"Planning meals for {len(days)} days")

            # 4) Generate plan with GPT
            await self._mqtt.update_progress(self.id, "progress", 60, "Generating meal plan with GPT")
            plan, feedback = await self.async_generate_plan_and_feedback(recipes, mealplan, days, user_message)
            
            # Log feedback from GPT
            await self._mqtt.log(self.id, "feedback", feedback)
            await self._mqtt.gpt_decision(self.id, "GPT generated plan:")

            # Display the generated plan
            id_to_name = self.build_id_to_name(recipes)
            for date in sorted(plan.keys()):
                await self._mqtt.info(self.id, f"\n{date}:", category="data")
                for meal_type in ["Lunch", "Dinner"]:
                    rid = plan[date].get(meal_type)
                    if rid:
                        rname = id_to_name.get(rid, rid)
                        await self._mqtt.info(self.id, f"  {meal_type}: {rname}", category="data")

            # 5) Update Mealie with the new plan
            await self._mqtt.update_progress(self.id, "progress", 75, "Updating Mealie with new plan")
            if self._dry_run:
                await self._mqtt.info(self.id, "DRY RUN: Skipping Mealie updates", category="skip")
                logger.info("DRY RUN mode - not updating Mealie")
                await self._mqtt.update_progress(self.id, "progress", 100, "Finished - Dry run mode")
            else:
                await self._mqtt.info(self.id, "\nUpdating Mealie...", category="update")
                update_count = 0
                skip_count = 0
                error_count = 0
                
                for date, slots in plan.items():
                    for meal_type, recipe_id in slots.items():
                        if not recipe_id:
                            continue
                            
                        # Check if this meal already exists
                        exists = any(
                            x["date"] == date
                            and x["entryType"] == meal_type.lower()
                            and x["recipeId"] == recipe_id
                            for x in mealplan_items
                        )
                        
                        if exists:
                            await self._mqtt.info(
                                self.id,
                                f"Skipping {meal_type} on {date}, already exists.",
                                category="skip"
                            )
                            skip_count += 1
                        else:
                            # Create new meal plan entry
                            payload = {
                                "date": date,
                                "entryType": meal_type.lower(),
                                "title": "",
                                "text": "",
                                "recipeId": recipe_id
                            }
                            
                            ok = await self._mealie.create_mealplan_entry(payload)
                            if ok:
                                update_count += 1
                            else:
                                error_msg = f"Failed to post meal for {date} {meal_type}"
                                await self._mqtt.error(self.id, error_msg)
                                logger.error(error_msg)
                                error_count += 1

                # Log summary of updates
                summary = f"Done! Added {update_count} meals, skipped {skip_count} existing meals"
                if error_count > 0:
                    summary += f", encountered {error_count} errors"
                    
                await self._mqtt.success(self.id, summary)
                logger.info(summary)
                await self._mqtt.update_progress(self.id, "progress", 100, "Finished")
                
        except Exception as e:
            error_msg = f"Error in meal planner: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._mqtt.error(self.id, error_msg)
            await self._mqtt.update_progress(self.id, "progress", 0, "Error occurred")
