#!/usr/bin/env python3
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
import argparse
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
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

# Script configuration for Home Assistant integration
SCRIPT_CONFIG = {
    "id": "meal_planner",
    "name": "Meal Planner",
    "type": "automation",
    "switch": True,
    "sensors": {
        "status": {"id": "status", "name": "Planning Progress"},
        "feedback": {"id": "feedback", "name": "Planning Feedback"}
    },
    "numbers": {
        "mealplan_length": {"id": "mealplan_length", "name": "Mealplan Days Required", "value": 7}
    },
    "texts": {
        "mealplan_message": {"id": "mealplan_message", "name": "Mealplan User Input", "text": "Generate a mealplan please."}
    },
    "execute_function": None  # Will be assigned the main() function
}

# Load environment variables
load_dotenv()

# API configuration
MEALIE_TOKEN = os.environ.get("MEALIE_TOKEN")
HA_URL = os.environ.get("HA_URL")
TOKEN = os.environ.get("HA_TOKEN")
INPUT_TEXT_ENTITY = os.environ.get("ENTITY")

# GPT configuration
MODEL_NAME = "gpt-4o"
TEMPERATURE = 0.1
DRY_RUN = False  # Set to True to skip updating Mealie

# GPT system prompt configuration
DEFAULT_CONFIG = (
    "You are a **meal planner AI** responsible for generating structured, healthy, and balanced meal plans "
    "based on the given meal catalog, user constraints, and existing plans.\n\n"
    
    "### Input You Will Receive\n"
    "- A list of available recipes with:\n"
    "  - Recipe `ID`, `name`, `description`, `tags`, and `categories`.\n"
    "- The current meal plan with assigned meals for each date.\n"
    "- User preferences and constraints (e.g., available ingredients, specific cravings).\n"
    "- The number of days to generate meals for.\n\n"
    
    "### Output Format (STRICTLY FOLLOW)\n"
    "Return a **valid JSON object** in the **EXACT format below**:\n\n"
    "{\n"
    '    "mealPlan": {\n'
    '        "YYYY-MM-DD": {\n'
    '            "Lunch": "recipe_id",\n'
    '            "Dinner": "recipe_id"\n'
    "        }\n"
    "    },\n"
    '    "feedback": "Short summary of the generated plan, highlighting improvements and suggestions."\n'
    "}\n\n"
    
    "- **DO NOT modify existing meals.** Only return missing days.\n"
    "- **DO NOT change, reorder, or rename recipe IDs.** Use them **exactly** as provided.\n"
    "- **DO NOT include unchanged days in the response.**\n\n"
    
    "### Meal Plan Rules\n"
    "**✅ Required:**\n"
    "- **Pizza:** Scheduled **once per week**, only on **Friday dinner**.\n"
    "- **Salads:** Preferably for **dinners** to keep meals light.\n"
    "- **Balanced Variety:** Ensure **protein, vegetables, and carbs** are included daily.\n"
    "- **Diversity:** Avoid repeating the **same main ingredient** two days in a row.\n"
    "- **Rotation:** Avoid selecting the same recipes as the previous two weeks when possible."
    "- **User Priorities:** Consider ingredients that are expiring soon (if provided).\n\n"
    
    "**❌ Forbidden:**\n"
    "- **No disclaimers or extra text.** Do not include 'As an AI, I...' statements.\n"
    "- **No generic placeholders.** All meals must be real recipes from the dataset.\n"
    "- **No random selections.** Each meal must be chosen based on user constraints.\n\n"
    
    "### 🔹 Special Considerations\n"
    "- **For missing meals:** Select from the meal catalog based on tags/categories.\n"
    "- **For weekends:** Lunch can be **slightly heavier** than weekdays.\n"
    "- **If input includes user requests:** Prioritize fulfilling them while maintaining balance.\n\n"
    
    "🚨 **Failure to follow these instructions will result in rejection of the output.**"
)

# Command line argument parser
parser = argparse.ArgumentParser(description="Generate meal plans with GPT")
parser.add_argument("--message", "-m", required=False, help="Input message for meal planning")
parser.add_argument("--config", "-c", default=DEFAULT_CONFIG, help="Configuration string for GPT")
args = parser.parse_args()


async def async_generate_plan_and_feedback(
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
    await ha_mqtt.gpt_decision(SCRIPT_CONFIG["id"], "Asking ChatGPT to Generate Mealplan...")
    logger.info(f"Generating meal plan for {len(days)} days with user message: {user_message[:50]}...")

    # Prepare data for GPT
    system_prompt_data = {
        "days": days,
        "recipesCatalog": recipes,
        "currentMealPlan": mealplan,
        "notes": args.config
    }

    messages = [
        {"role": "system", "content": json.dumps(system_prompt_data, indent=2)},
        {"role": "user", "content": user_message}
    ]

    # Call GPT
    result = await gpt_utils.gpt_json_chat(messages, model=MODEL_NAME, temperature=TEMPERATURE)
    
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


def build_id_to_name(recipes: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Build a mapping from recipe IDs to recipe names.
    
    Args:
        recipes: List of recipe dictionaries
        
    Returns:
        Dictionary mapping recipe IDs to names
    """
    return {r["id"]: r["name"] for r in recipes}


def generate_days_list(latest_date: str, num_days: int) -> List[str]:
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

async def main() -> None:
    """
    Main workflow:
      1. Fetch all recipes from Mealie
      2. Fetch current meal plan
      3. Determine which days need planning
      4. Generate meal plan using GPT
      5. Update Mealie with the new plan
    """
    _ = parser.parse_args()  # re-parse in case run directly

    num_days = SCRIPT_CONFIG["numbers"]["mealplan_length"]["value"]
    user_message = SCRIPT_CONFIG["texts"]["mealplan_message"]["text"]

    await ha_mqtt.info(SCRIPT_CONFIG["id"], "Starting meal planning process...", category="start")

    # 1) Fetch all recipes
    await ha_mqtt.info(SCRIPT_CONFIG["id"], "Fetching recipes from Mealie...", category="data")
    raw_recipes = await mealie_api.fetch_data("/api/recipes?full=true")
    if not raw_recipes or not isinstance(raw_recipes, dict):
        error_msg = "Could not fetch recipes from Mealie."
        await ha_mqtt.error(SCRIPT_CONFIG["id"], error_msg)
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
    await ha_mqtt.info(SCRIPT_CONFIG["id"], f"Found {len(recipes)} recipes", category="data")

    # 2) Fetch current meal plan
    await ha_mqtt.info(SCRIPT_CONFIG["id"], "Fetching current meal plan...", category="data")
    # Include past 15 days to avoid repeating recent meals
    start_date = (datetime.today() - timedelta(days=15)).strftime("%Y-%m-%d")
    end_date = (datetime.today() + timedelta(days=num_days)).strftime("%Y-%m-%d")
    
    mealplan_items = await mealie_api.get_meal_plan(start_date, end_date)
    if not mealplan_items:
        error_msg = "No meal plan data available."
        await ha_mqtt.warning(SCRIPT_CONFIG["id"], error_msg)
        logger.warning(error_msg)
        return
    
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
    await ha_mqtt.info(SCRIPT_CONFIG["id"], "Determining days that need planning...", category="progress")
    latest_date = max((x["date"] for x in mealplan_items), default=datetime.now().strftime("%Y-%m-%d"))
    days = generate_days_list(latest_date, num_days)
    
    if not days:
        await ha_mqtt.success(SCRIPT_CONFIG["id"], "No days need planning")
        return

    await ha_mqtt.info(SCRIPT_CONFIG["id"], f"Planning meals for {len(days)} days", category="progress")

    # 4) Generate plan with GPT
    plan, feedback = await async_generate_plan_and_feedback(recipes, mealplan, days, user_message)
    
    # Log feedback from GPT
    await ha_mqtt.log(SCRIPT_CONFIG["id"], "feedback", feedback)
    await ha_mqtt.gpt_decision(SCRIPT_CONFIG["id"], "GPT generated plan:")

    # Display the generated plan
    id_to_name = build_id_to_name(recipes)
    for date in sorted(plan.keys()):
        await ha_mqtt.info(SCRIPT_CONFIG["id"], f"\n{date}:", category="data")
        for meal_type in ["Lunch", "Dinner"]:
            rid = plan[date].get(meal_type)
            if rid:
                rname = id_to_name.get(rid, rid)
                await ha_mqtt.info(SCRIPT_CONFIG["id"], f"  {meal_type}: {rname}", category="data")

    # 5) Update Mealie with the new plan
    if DRY_RUN:
        await ha_mqtt.info(SCRIPT_CONFIG["id"], "DRY RUN: Skipping Mealie updates", category="skip")
        logger.info("DRY RUN mode - not updating Mealie")
    else:
        await ha_mqtt.info(SCRIPT_CONFIG["id"], "\nUpdating Mealie...", category="update")
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
                    await ha_mqtt.info(
                        SCRIPT_CONFIG["id"],
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
                    
                    ok = await mealie_api.create_mealplan_entry(payload)
                    if ok:
                        update_count += 1
                    else:
                        error_msg = f"Failed to post meal for {date} {meal_type}"
                        await ha_mqtt.error(SCRIPT_CONFIG["id"], error_msg)
                        logger.error(error_msg)
                        error_count += 1

        # Log summary of updates
        summary = f"Done! Added {update_count} meals, skipped {skip_count} existing meals"
        if error_count > 0:
            summary += f", encountered {error_count} errors"
            
        await ha_mqtt.success(SCRIPT_CONFIG["id"], summary)
        logger.info(summary)

# Assign main function to execute_function
SCRIPT_CONFIG["execute_function"] = main

if __name__ == "__main__":
    asyncio.run(main())
