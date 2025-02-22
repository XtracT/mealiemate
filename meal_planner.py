#!/usr/bin/env python3
"""
Module: meal_planner
--------------------
Generates structured, balanced meal plans based on existing recipes, user constraints,
and number of days requested, then updates Mealie accordingly.
"""

import os
import argparse
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

from ha_mqtt import log
import mealie_api
import gpt_utils

load_dotenv()

MEALIE_TOKEN = os.environ.get("MEALIE_TOKEN")
HA_URL = os.environ.get("HA_URL")
TOKEN = os.environ.get("HA_TOKEN")
INPUT_TEXT_ENTITY = os.environ.get("ENTITY")

MODEL_NAME = "gpt-4o"
TEMPERATURE = 0.1
DRY_RUN = False

DEFAULT_NUM_DAYS = 7
DEFAULT_INPUT_MESSAGE = "Generate a mealplan please."


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

parser = argparse.ArgumentParser(description="Process message with config")
parser.add_argument("--message", "-m", required=False, help="Input message")
parser.add_argument("--config", "-c", default=DEFAULT_CONFIG, help="Configuration string")
args = parser.parse_args()


async def async_generate_plan_and_feedback(recipes, mealplan, days):
    """
    Calls GPT to generate meal plan JSON plus a feedback string.
    """
    await log(SCRIPT_CONFIG["id"], "status", "Asking ChatGPT to Generate Mealplan...")


    system_prompt_data = {
        "days": days,
        "recipesCatalog": recipes,
        "currentMealPlan": mealplan,
        "notes": args.config
    }

    user_message = next(
        (item["text"] for item in SCRIPT_CONFIG["input_texts"] if item["id"] == "mealplan_message"),
        None  # Default value if not found
    )

    messages = [
        {"role": "system", "content": json.dumps(system_prompt_data, indent=2)},
        {"role": "user", "content": user_message}
    ]

    result = await gpt_utils.gpt_json_chat(messages, model=MODEL_NAME, temperature=TEMPERATURE)
    meal_plan_obj = result.get("mealPlan", {})
    feedback_str = result.get("feedback", "")

    plan_days = {
        day: {
            "Lunch": slots.get("Lunch", ""),
            "Dinner": slots.get("Dinner", "")
        }
        for day, slots in meal_plan_obj.items()
    }
    return plan_days, feedback_str


def build_id_to_name(recipes):
    return {r["id"]: r["name"] for r in recipes}

def generate_days_list(latest_date, num_days):
    latest = datetime.strptime(latest_date, "%Y-%m-%d")
    today = datetime.today()
    start_date = max(latest, today) + timedelta(days=1)
    end_date = today + timedelta(days=num_days)

    if start_date > end_date:
        return []
    return [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range((end_date - start_date).days + 1)
    ]

async def main():
    _ = parser.parse_args()  # re-parse in case run directly

    # 1) Fetch all recipes
    raw_recipes = await mealie_api.fetch_data("/api/recipes?full=true")
    if not raw_recipes or not isinstance(raw_recipes, dict):
        await log(SCRIPT_CONFIG["id"], "status", "❌ Could not fetch recipes.")
        return

    recipes = [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "tags": [t["name"] for t in r.get("tags", [])],
            "categories": [c["name"] for c in r.get("recipeCategory", [])]
        }
        for r in raw_recipes.get("items", [])
    ]

    # 2) Fetch current meal plan
    start_date = (datetime.today() - timedelta(days=31)).strftime("%Y-%m-%d")
    end_date = (datetime.today() + timedelta(days=SCRIPT_CONFIG["parameters"]["num_days"])).strftime("%Y-%m-%d")
    mealplan_items = await mealie_api.get_meal_plan(start_date, end_date)
    if not mealplan_items:
        await log(SCRIPT_CONFIG["id"], "status", "❌ No meal plan data available.")
        return

    # 3) Determine which days need planning
    latest_date = max((x["date"] for x in mealplan_items), default=datetime.now().strftime("%Y-%m-%d"))
    days = generate_days_list(latest_date, SCRIPT_CONFIG["parameters"]["num_days"])
    if not days:
        await log(SCRIPT_CONFIG["id"], "status", "✅ No days need planning")
        return

    # 4) GPT generate plan
    plan, feedback = await async_generate_plan_and_feedback(recipes, mealplan_items, days)
    await log(SCRIPT_CONFIG["id"], "feedback", feedback)
    await log(SCRIPT_CONFIG["id"], "status", "GPT generated plan:")

    id_to_name = build_id_to_name(recipes)
    for date in sorted(plan.keys()):
        await log(SCRIPT_CONFIG["id"], "status", f"\n{date}:")
        for meal_type in ["Lunch", "Dinner"]:
            rid = plan[date].get(meal_type)
            if rid:
                rname = id_to_name.get(rid, rid)
                await log(SCRIPT_CONFIG["id"], "status", f"  {meal_type}: {rname}")

    # 5) Update Mealie
    if not DRY_RUN:
        await log(SCRIPT_CONFIG["id"], "status", "\nUpdating Mealie...")
        for date, slots in plan.items():
            for meal_type, recipe_id in slots.items():
                if recipe_id:
                    exists = any(
                        x["date"] == date
                        and x["entryType"] == meal_type.lower()
                        and x["recipeId"] == recipe_id
                        for x in mealplan_items
                    )
                    if exists:
                        await log(SCRIPT_CONFIG["id"], "status",
                                  f"Skipping {meal_type} on {date}, already exists.")
                    else:
                        payload = {
                            "date": date,
                            "entryType": meal_type.lower(),
                            "title": "",
                            "text": "",
                            "recipeId": recipe_id
                        }
                        ok = await mealie_api.create_mealplan_entry(payload)
                        if not ok:
                            await log(SCRIPT_CONFIG["id"], "status",
                                      f"❌ Failed to post meal for {date} {meal_type}")

    await log(SCRIPT_CONFIG["id"], "status", "✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())


SCRIPT_CONFIG = {
    "id": "meal_planner",
    "name": "Meal Planner",
    "type": "automation",
    "switch": True,
    "sensors": [
        {"id": "status", "name": "Planning Progress"},
        {"id": "feedback", "name": "Planning Feedback"}
    ],
    "input_numbers": [
        {"id": "mealplan_length", "name": "Mealplan Days Required", "default_value":DEFAULT_NUM_DAYS}
    ],
    "input_texts": [
        {"id": "mealplan_message", "name": "Mealplan User Input", "text":DEFAULT_INPUT_MESSAGE}
    ],
    "parameters": {
        "num_days": DEFAULT_NUM_DAYS
    },
    "execute_function": main  # Return the coroutine itself, not a Task
}
