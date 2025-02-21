"""
Module: shopping_list_generator
-------------------------------
Generates a consolidated shopping list from the user's upcoming Mealie meal plan,
cleans it up via GPT, and (optionally) updates Mealie with the final list.
"""

import os
import json
import time
import argparse
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv

from ha_mqtt import log
import mealie_api
import gpt_utils

load_dotenv()

parser = argparse.ArgumentParser(description="Generate and send a shopping list to Mealie.")
parser.add_argument("--dry-run", action="store_true", help="Run in dry mode without sending data to Mealie.")
args = parser.parse_args()
DRY_RUN = args.dry_run

DEFAULT_NUM_DAYS = 8

async def shopping_list_generator():
    """
    Wrapper function to execute the main logic asynchronously.
    """
    await main()

async def get_recipe_ingredients(recipe_id):
    recipe_details = await mealie_api.get_recipe_details(recipe_id)
    if not recipe_details:
        await log(SCRIPT_CONFIG["id"], "status", f"❌ Could not fetch recipe {recipe_id}")
        return []

    return [
        {
            "name": " ".join(ing["food"]["name"].split()),
            "quantity": ing["quantity"],
            "unit": " ".join(ing["unit"]["name"].split()) if ing.get("unit") else ""
        }
        for ing in recipe_details.get("recipeIngredient", [])
        if ing.get("food") and ing["food"].get("name")
    ]

async def consolidate_ingredients(meal_plan):
    ingredient_list = []
    for meal in meal_plan:
        recipe_ingredients = await get_recipe_ingredients(meal["recipeId"])
        ingredient_list.extend(recipe_ingredients)
    await log(SCRIPT_CONFIG["id"], "status", f"✅ Collected {len(ingredient_list)} total ingredients.")
    return ingredient_list

async def clean_up_shopping_list(ingredients):
    await log(SCRIPT_CONFIG["id"], "status", "🧠 Using GPT to clean up the shopping list...")

    ingredients_sorted = sorted(ingredients, key=lambda x: x["name"].lower())
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

    messages = [{"role": "user", "content": json.dumps(prompt_content)}]

    result = await gpt_utils.gpt_json_chat(messages, model="gpt-4o", temperature=0)
    
    cleaned_list = result.get("shopping_list", [])
    feedback = result.get("feedback", [])

    await log(SCRIPT_CONFIG["id"], "status", f"✅ Shopping list went down to {len(cleaned_list)} items.")
    await log(SCRIPT_CONFIG["id"], "status", "\n🔄 **Item Merging Details:**")
    for item in cleaned_list:
        merged_str = ", ".join(item.get("merged_items", []))
        await log(SCRIPT_CONFIG["id"], "status",
                  f"📌 {item['quantity']} {item['unit']} {item['name']} ({item['category']})  <-  {merged_str}")

    if feedback:
        await log(SCRIPT_CONFIG["id"], "status", "\n⚠️ **GPT Feedback:**")
        for issue in feedback:
            await log(SCRIPT_CONFIG["id"], "status", f"🔹 {issue}")
            await log(SCRIPT_CONFIG["id"], "feedback", f"🔹 {issue}")

    return cleaned_list

async def main():
    list_name = f"Mealplan {datetime.today().strftime('%d %b')}"
    await log(SCRIPT_CONFIG["id"], "status", f"\n➡️ Working on your new shopping list: {list_name}")

    start_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (datetime.today() + timedelta(days=SCRIPT_CONFIG["parameters"]["num_days"])).strftime("%Y-%m-%d")
    
    meal_plan = await mealie_api.get_meal_plan(start_date, end_date)
    if not meal_plan:
        await log(SCRIPT_CONFIG["id"], "status", "❌ No meal plan data available.")
        return

    meal_plan_entries = [
        {"date": item["date"], "recipeId": item["recipeId"]}
        for item in meal_plan if item.get("recipeId")
    ]
    await log(SCRIPT_CONFIG["id"], "status", f"✅ Found {len(meal_plan_entries)} meal plan entries.")

    raw_ingredients = await consolidate_ingredients(meal_plan_entries)
    cleaned_list = await clean_up_shopping_list(raw_ingredients)

    if DRY_RUN:
        await log(SCRIPT_CONFIG["id"], "status", f"📝 [DRY-RUN] Would create shopping list: {list_name}")
        return

    shopping_list_id = await mealie_api.create_shopping_list(list_name)
    if shopping_list_id and cleaned_list:
        await log(SCRIPT_CONFIG["id"], "status", "\n📤 Adding items to Mealie shopping list...")
        for item in cleaned_list:
            formatted_note = f"{item['quantity']} {item['unit']} {item['name']}".strip()
            ok = await mealie_api.add_item_to_shopping_list(shopping_list_id, formatted_note)
            if not ok:
                await log(SCRIPT_CONFIG["id"], "status", f"❌ Failed to add {formatted_note}")

    await log(SCRIPT_CONFIG["id"], "status", "\n✅ Done! Your Mealie shopping list is updated.")

if __name__ == "__main__":
    asyncio.run(main())

SCRIPT_CONFIG = {
    "id": "shopping_list_generator",
    "name": "Shopping List Generator",
    "type": "automation",
    "switch": True,
    "sensors": [
        {"id": "status", "name": "Shopping List Progress"},
        {"id": "feedback", "name": "Shopping List Feedback"}
    ],
    "input_numbers": [
        {"id": "mealplan_length", "name": "Shopping list Days Required", "default_value":DEFAULT_NUM_DAYS}
    ],
    "parameters": {
        "num_days": DEFAULT_NUM_DAYS
    },
    "execute_function": main  # Return the coroutine itself, not a Task
}
