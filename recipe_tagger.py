"""
Module: recipe_tagger
---------------------
Classifies recipes in Mealie by assigning tags and categories using GPT, then updates them
in the Mealie database.
"""

import asyncio
import os
import json
from dotenv import load_dotenv

from utils.ha_mqtt import log
import utils.mealie_api as mealie_api
import utils.gpt_utils as gpt_utils

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DRY_RUN = False

SCRIPT_CONFIG = {
    "id": "recipe_tagger",
    "name": "Recipe Tagger",
    "type": "automation",
    "switch": True,
    "sensors": {
        "status" : {"id": "status", "name": "Tagging Progress"},
        "feedback" : {"id": "feedback", "name": "Tagging Feedback"}
    },
    "execute_function": None  # Return the coroutine itself, not a Task
}

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

async def recipe_tagger():
    await main()

async def classify_recipe_with_gpt(name, ingredients):
    clean_ingredients = [i.strip() for i in ingredients if i and i.strip()]
    if not clean_ingredients:
        await log(SCRIPT_CONFIG["id"], "status", f"⚠️ Recipe '{name}' has no valid ingredients, skipping classification.")
        return [], None

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

    messages = [{"role": "user", "content": prompt}]
    result = await gpt_utils.gpt_json_chat(messages, model="gpt-4o", temperature=0.1)

    # Validate GPT output
    all_valid_tags = set(
        AVAILABLE_TAGS["Main Ingredient Category"] +
        AVAILABLE_TAGS["Nutritional Profile and Dietary Preferences"] +
        AVAILABLE_TAGS["Time & Effort"]
    )
    valid_categories = set(AVAILABLE_CATEGORIES)

    raw_tags = result.get("tags", [])
    category = result.get("category", None)

    # Filter out invalid tags
    filtered_tags = [t for t in raw_tags if t in all_valid_tags]
    invalid_tags = [t for t in raw_tags if t not in all_valid_tags]

    if invalid_tags:
        await log(SCRIPT_CONFIG["id"], "status", f"⚠️ GPT returned invalid tags {invalid_tags}. Ignoring these.")
        await log(SCRIPT_CONFIG["id"], "feedback", f"⚠️ GPT returned invalid tags {invalid_tags}. Ignoring these.")


    if category not in valid_categories:
        await log(SCRIPT_CONFIG["id"], "status", f"⚠️ Invalid category '{category}' received from GPT. Ignoring.")
        await log(SCRIPT_CONFIG["id"], "feedback", f"⚠️ Invalid category '{category}' received from GPT. Ignoring.")
        category = None

    return filtered_tags, category

async def update_recipe(recipe_slug, details, new_tags, new_category, tag_mapping, category_mapping):
    existing_recipe_cats = details.get("recipeCategory", [])
    payload = {
        "tags": [],
        "recipeCategory": existing_recipe_cats
    }

    # Build tag objects
    tag_objs = []
    for t in new_tags:
        if t.lower() in tag_mapping:
            tag_objs.append(tag_mapping[t.lower()])
        else:
            new_tag = await mealie_api.create_tag(t)
            if new_tag:
                tag_objs.append(new_tag)
    payload["tags"] = tag_objs

    if new_category:
        if new_category.lower() in category_mapping:
            payload["recipeCategory"] = [category_mapping[new_category.lower()]]
        else:
            new_cat = await mealie_api.create_category(new_category)
            if new_cat:
                payload["recipeCategory"] = [new_cat]

    await log(
        SCRIPT_CONFIG["id"],
        "status",
        f"📝 Updating '{recipe_slug}' with tags: {', '.join(new_tags)} | Category: {new_category}"
    )

    if DRY_RUN:
        await log(SCRIPT_CONFIG["id"], "status",
                  f"🔹 [DRY-RUN] Would update {recipe_slug} with PATCH")
        return

    ok = await mealie_api.update_recipe_tags_categories(recipe_slug, payload)
    if ok:
        await log(SCRIPT_CONFIG["id"], "status",
                  f"✅ Successfully updated {recipe_slug} with tags: {', '.join(new_tags)} | Category: {new_category}")
    else:
        await log(SCRIPT_CONFIG["id"], "status",
                  f"❌ Error updating {recipe_slug}")

async def main():
    await log(SCRIPT_CONFIG["id"], "status", "🚀 Fetching recipes from Mealie...")
    recipes = await mealie_api.get_all_recipes()
    if not recipes:
        await log(SCRIPT_CONFIG["id"], "status", "❌ No recipes found.")
        return

    await log(SCRIPT_CONFIG["id"], "status", f"✅ Fetched {len(recipes)} recipes.")

    await log(SCRIPT_CONFIG["id"], "status", "📥 Preloading Mealie tags & categories...")
    all_tags = await mealie_api.get_tags()
    all_categories = await mealie_api.get_categories()

    tag_mapping = {t["name"].lower(): t for t in all_tags}
    category_mapping = {c["name"].lower(): c for c in all_categories}

    # Process each recipe
    for r in recipes:
        slug = r["slug"]
        details = await mealie_api.get_recipe_details(slug)
        if not details:
            continue

        ingredients = [
            ing["food"]["name"]
            for ing in details.get("recipeIngredient", [])
            if ing.get("food") and "name" in ing["food"]
        ]
        if not ingredients:
            await log(
                SCRIPT_CONFIG["id"],
                "status",
                f"⚠️ Recipe '{r['name']}' has no valid ingredients. Skipping classification."
            )
            continue

        new_tags, new_category = await classify_recipe_with_gpt(r["name"], ingredients)
        if new_tags or new_category:
            await update_recipe(slug, details, new_tags, new_category, tag_mapping, category_mapping)

    await log(SCRIPT_CONFIG["id"], "status", "🎉 Processing complete!")

# Assign main function to execute_function
SCRIPT_CONFIG["execute_function"] = main

if __name__ == "__main__":
    asyncio.run(main())
