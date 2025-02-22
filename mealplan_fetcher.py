#!/usr/bin/env python3
"""
Module: mealplan_fetcher
------------------------
Fetches the upcoming meal plan (today + next 6 days) from Mealie and logs it in Markdown format.
"""

import asyncio
import json
from datetime import datetime, timedelta

from utils.ha_mqtt import log
import utils.mealie_api as mealie_api

SCRIPT_CONFIG = {
    "id": "mealplan_fetcher",
    "name": "Meal Plan Fetcher",
    "type": "automation",
    "switch": True,
    "sensors": {
        "mealplan": {"id": "mealplan", "name": "Formatted Meal Plan"}
    },
    "numbers": {
        "num_days": {"id": "num_days", "name": "Fetcher Days","value": 7 }
    },
    "texts": {
        "mealie_url": {
            "id": "mealie_url",
            "name": "mealie_url",
            "text": "https://mealie.domain.com"
        }
    },
    "execute_function": None  # Will be set to main()
} 


def generate_markdown_table(mealplan, mealie_url):
    """
    Generates a Markdown table from the meal plan.
    :param mealplan: Dictionary of meal plan entries
    :param mealie_url: Base URL of the Mealie instance
    :return: Markdown-formatted string
    """
    header = "| Day        | Lunch                      | Dinner                      |"
    separator = "|-----------|---------------------------|----------------------------|"
    rows = []

    for date in sorted(mealplan.keys()):
        weekday = datetime.strptime(date, "%Y-%m-%d").strftime("%A")  # Convert date to weekday name
        meals = mealplan[date]

        def format_meal(recipe):
            """Helper function to create Markdown link for a meal."""
            if not recipe:
                return "—"
            name = recipe.get("name", "Unknown")
            slug = recipe.get("slug", "")
            if slug:
                return f"[{name}]({mealie_url}/g/home/r/{slug})"
            return name  # Fallback in case no slug exists

        lunch_link = format_meal(meals.get("Lunch"))
        dinner_link = format_meal(meals.get("Dinner"))

        rows.append(f"| {weekday:<10} | {lunch_link:<25} | {dinner_link:<25} |")

    return "\n".join([header, separator] + rows)

async def main():
    """
    Main function that fetches meal plans and logs them in Markdown format.
    """
    num_days = SCRIPT_CONFIG["numbers"]["num_days"]["value"]
    mealie_url = SCRIPT_CONFIG["texts"]["mealie_url"]["text"]

    # Determine date range
    start_date = datetime.today().strftime("%Y-%m-%d")
    end_date = (datetime.today() + timedelta(days=num_days - 1)).strftime("%Y-%m-%d")

    # Fetch meal plan from Mealie
    mealplan_items = await mealie_api.get_meal_plan(start_date, end_date)
    if not mealplan_items:
        await log(SCRIPT_CONFIG["id"], "status", "❌ No meal plan data available.")
        return

    # Process meal plan data into a structured format
    mealplan = {}
    for entry in mealplan_items:
        date = entry["date"]
        meal_type = entry["entryType"].capitalize()  # "lunch" -> "Lunch"
        recipe = entry.get("recipe", {})  # Full recipe object

        if date not in mealplan:
            mealplan[date] = {}
        mealplan[date][meal_type] = recipe  # Store the full recipe dict

    # Generate Markdown table
    mealplan_markdown = generate_markdown_table(mealplan, mealie_url)

    # Log formatted meal plan
    await log(SCRIPT_CONFIG["id"], "mealplan", mealplan_markdown)
    await log(SCRIPT_CONFIG["id"], "status", "✅ Meal plan fetched and logged.")

# Assign main function to execute_function
SCRIPT_CONFIG["execute_function"] = main

if __name__ == "__main__":
    asyncio.run(main())
