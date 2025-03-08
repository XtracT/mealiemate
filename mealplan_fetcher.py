#!/usr/bin/env python3
"""
Module: mealplan_fetcher
------------------------
This script performs the following tasks:
  1. Fetches the upcoming meal plan (today + next 6 days) from Mealie.
  2. Logs the meal plan in Markdown format via MQTT.
  3. Generates a 480x800 PNG image of the meal plan.
  4. Sends the generated image directly to a Telegram chat using credentials loaded from a .env file.

Requirements:
  - python-dotenv
  - python-telegram-bot
  - Pillow

Place your TTF font file (e.g. "January Night.ttf") in the same directory as this script.
"""

import asyncio
import os
from datetime import datetime, timedelta
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from telegram import Bot

from utils.ha_mqtt import log
import utils.mealie_api as mealie_api

# Global constant for output image name (used for logging only; image is sent in-memory)
OUTPUT_IMAGE_NAME = "weekly_meal_plan.png"

# ------------------ Load Environment Variables ------------------
load_dotenv()  # Load credentials from .env file in the current directory
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
BOT_CHAT_ID = os.getenv("TG_BOT_CHAT_ID")  # Typically a string

# ------------------ Script Configuration ------------------
SCRIPT_CONFIG = {
    "id": "mealplan_fetcher",
    "name": "Meal Plan Fetcher",
    "type": "automation",
    "switch": True,
    "sensors": {
        "mealplan": {"id": "mealplan", "name": "Formatted Meal Plan"}
    },
    "numbers": {
        "num_days": {"id": "num_days", "name": "Fetcher Days", "value": 7}
    },
    "texts": {
        "mealie_url": {
            "id": "mealie_url",
            "name": "mealie_url",
            "text": "https://mealie.domain.com"
        }
    },
    "execute_function": None  # Will be assigned the main() function below
}


def generate_markdown_table(mealplan, mealie_url):
    """
    Generates a Markdown table from the meal plan.

    Args:
      mealplan (dict): Dictionary of meal plan entries.
      mealie_url (str): Base URL of the Mealie instance.

    Returns:
      str: Markdown-formatted table.
    """
    header = "| Day        | Lunch                      | Dinner                      |"
    separator = "|-----------|---------------------------|----------------------------|"
    rows = []

    for date in sorted(mealplan.keys()):
        weekday = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        meals = mealplan[date]

        def format_meal(recipe):
            """Return a Markdown link for the given recipe."""
            if not recipe:
                return "—"
            name = recipe.get("name", "Unknown")
            slug = recipe.get("slug", "")
            if slug:
                return f"[{name}]({mealie_url}/g/home/r/{slug})"
            return name

        lunch_link = format_meal(meals.get("Lunch"))
        dinner_link = format_meal(meals.get("Dinner"))
        rows.append(f"| {weekday:<10} | {lunch_link:<25} | {dinner_link:<25} |")

    return "\n".join([header, separator] + rows)


def generate_mealplan_png(mealplan):
    """
    Generates a rotated meal plan image (480x800 portrait rotated 90°) in memory.
    
    The image contains:
      - A 5-pixel top margin.
      - Centered, rounded red day label boxes (200px wide) for the next 7 days (today + 6),
        with the actual day names.
      - A thin horizontal red line across the full width, aligned with the middle of each box.
      - Two columns for meal text (Lunch and Dinner) in the remaining space.
    
    Args:
      mealplan (dict): Dictionary of meal plan entries.
    
    Returns:
      PIL.Image.Image: The final rotated image.
    """
    # ------------------ IMAGE SETTINGS ------------------
    WIDTH = 480
    HEIGHT = 800
    NUM_DAYS = 7
    TOP_MARGIN = 5  # Top margin in pixels

    # Layout settings for day labels and meals
    DAY_LABEL_HEIGHT = 40
    DAY_LABEL_V_OFFSET = -2
    MEALS_V_OFFSET = -5

    # Colors (RGB)
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    GRAY = (136, 136, 136)
    DAY_TEXT_COLOR = WHITE

    # Box settings for the centered day label box
    BOX_WIDTH = 200      # Box width (centered horizontally)
    BOX_HEIGHT = DAY_LABEL_HEIGHT
    BOX_RADIUS = 15      # Rounded edges
    LINE_HEIGHT = 4      # Thickness of the horizontal red line

    COLUMN_SEPARATOR_X = WIDTH // 2  # For splitting lunch and dinner columns

    # ------------------ Determine Day Names and Meal Texts ------------------
    # Always display the next 7 days (today + 6)
    today = datetime.today().date()
    day_names, lunches, dinners = [], [], []

    for i in range(NUM_DAYS):
        current_date = today + timedelta(days=i)
        weekday_name = current_date.strftime("%A").upper()
        day_str = current_date.strftime("%Y-%m-%d")
        if day_str in mealplan:
            lunch_recipe = mealplan[day_str].get("Lunch")
            dinner_recipe = mealplan[day_str].get("Dinner")
            lunch_name = lunch_recipe["name"] if lunch_recipe else "—"
            dinner_name = dinner_recipe["name"] if dinner_recipe else "—"
        else:
            lunch_name = "—"
            dinner_name = "—"

        day_names.append(weekday_name)
        lunches.append(lunch_name)
        dinners.append(dinner_name)

    # ------------------ Create Base Image ------------------
    img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    # ------------------ Load Fonts ------------------
    base_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(base_dir, "January Night.ttf")
    try:
        FONT_DAY = ImageFont.truetype(font_path, 38)
        FONT_MEAL = ImageFont.truetype(font_path, 28)
    except IOError:
        print("Warning: TTF font not found, falling back to PIL default.")
        FONT_DAY = ImageFont.load_default()
        FONT_MEAL = ImageFont.load_default()

    # ------------------ Helper Functions ------------------
    def wrap_text(text, font, max_width):
        """Wrap text into multiple lines that fit within max_width."""
        words = text.split()
        lines = []
        current_line = ""
        for w in words:
            test_line = (current_line + " " + w).strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = w
        lines.append(current_line)
        return lines

    def draw_lines_centered(lines, font, rect, fill, line_spacing=5, v_offset=0):
        """
        Draw lines of text centered horizontally and vertically within rect.
        
        Args:
          lines (list): List of text lines.
          font (PIL.ImageFont.ImageFont): Font for the text.
          rect (tuple): (x_left, y_top, x_right, y_bottom).
          fill (tuple): Text color.
          line_spacing (int): Pixels between lines.
          v_offset (int): Vertical offset for fine-tuning.
        """
        x_left, y_top, x_right, y_bottom = rect
        rect_w = x_right - x_left
        rect_h = y_bottom - y_top

        line_heights = []
        for ln in lines:
            bbox = draw.textbbox((0, 0), ln, font=font)
            line_heights.append(bbox[3] - bbox[1])
        total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)
        current_y = y_top + (rect_h - total_text_height) // 2 + v_offset

        for i, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            lw = bbox[2] - bbox[0]
            x_line = x_left + (rect_w - lw) // 2
            draw.text((x_line, current_y), ln, font=font, fill=fill)
            current_y += line_heights[i] + (line_spacing if i < len(lines) - 1 else 0)

    # ------------------ Layout the 7 Days Vertically ------------------
    effective_height = HEIGHT - TOP_MARGIN
    day_height_float = effective_height / NUM_DAYS
    accum_h = 0.0

    for i in range(NUM_DAYS):
        # Compute vertical boundaries for each day's row
        top = TOP_MARGIN + int(round(accum_h))
        accum_h += day_height_float
        bottom = TOP_MARGIN + int(round(accum_h))

        # Define red day label box (centered horizontally)
        box_left = (WIDTH - BOX_WIDTH) // 2
        box_right = box_left + BOX_WIDTH
        box_top = top
        box_bottom = box_top + BOX_HEIGHT

        # Draw rounded red day label box
        draw.rounded_rectangle([(box_left, box_top), (box_right, box_bottom)],
                               radius=BOX_RADIUS, fill=RED)

        # Draw horizontal red line across full width, aligned with the box's center
        line_y = box_top + (BOX_HEIGHT // 2)
        draw.rectangle([(0, line_y - (LINE_HEIGHT // 2)), (WIDTH, line_y + (LINE_HEIGHT // 2))],
                       fill=RED)

        # Draw the day label text centered in the red box
        day_name = day_names[i]
        bbox_day = draw.textbbox((0, 0), day_name, font=FONT_DAY)
        day_text_w = bbox_day[2] - bbox_day[0]
        day_text_x = (WIDTH - day_text_w) // 2
        day_text_y = box_top + (BOX_HEIGHT - bbox_day[3]) // 2 + DAY_LABEL_V_OFFSET
        draw.text((day_text_x, day_text_y), day_name, font=FONT_DAY, fill=DAY_TEXT_COLOR)

        # Define the meals area (the space below the red box)
        meals_top = box_bottom
        meals_bottom = bottom

        # Left column (Lunch)
        left_rect = (0, meals_top, COLUMN_SEPARATOR_X, meals_bottom)
        lunch_lines = wrap_text(lunches[i], FONT_MEAL, (COLUMN_SEPARATOR_X - 20))
        draw_lines_centered(lunch_lines, FONT_MEAL, left_rect, BLACK, line_spacing=5, v_offset=MEALS_V_OFFSET)

        # Right column (Dinner)
        right_rect = (COLUMN_SEPARATOR_X, meals_top, WIDTH, meals_bottom)
        dinner_lines = wrap_text(dinners[i], FONT_MEAL, (WIDTH - COLUMN_SEPARATOR_X - 20))
        draw_lines_centered(dinner_lines, FONT_MEAL, right_rect, BLACK, line_spacing=5, v_offset=MEALS_V_OFFSET)

    # Rotate 90° (clockwise) and return the image
    rotated_img = img.rotate(270, expand=True)
    print("Meal plan image generated in memory.")
    return rotated_img


async def send_telegram_image(bot_token, chat_id, image_obj, caption="Weekly Meal Plan"):
    """
    Sends an in-memory PIL Image object as a PNG file to a Telegram chat.
    
    Args:
      bot_token (str): Telegram bot token.
      chat_id (str): Telegram chat ID.
      image_obj (PIL.Image.Image): Image to send.
      caption (str): Caption for the image.
    """
    if not bot_token or not chat_id:
        print("Telegram token or chat ID not provided in .env. Skipping Telegram send.")
        return

    bot = Bot(token=bot_token)
    buffer = BytesIO()
    image_obj.save(buffer, format="PNG")
    buffer.seek(0)
    await bot.send_photo(chat_id=chat_id, photo=buffer, caption=caption)
    print("Telegram image sent!")


async def main():
    """
    Main workflow:
      1. Fetch meal plan from Mealie (7 days).
      2. Log the meal plan in Markdown format via MQTT.
      3. Generate a rotated PNG image (in memory) of the meal plan.
      4. Send the PNG image via Telegram (if credentials are provided).
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

    # Build a dictionary: { "YYYY-MM-DD": { "Lunch": recipe, "Dinner": recipe }, ... }
    mealplan = {}
    for entry in mealplan_items:
        date = entry["date"]
        meal_type = entry["entryType"].capitalize()  # "Lunch" or "Dinner"
        recipe = entry.get("recipe", {})
        if date not in mealplan:
            mealplan[date] = {}
        mealplan[date][meal_type] = recipe

    # Generate Markdown table and log via MQTT
    mealplan_markdown = generate_markdown_table(mealplan, mealie_url)
    await log(SCRIPT_CONFIG["id"], "mealplan", mealplan_markdown)
    await log(SCRIPT_CONFIG["id"], "status", "✅ Meal plan fetched and logged.")

    # Generate the PNG image (in memory)
    image_obj = generate_mealplan_png(mealplan)

    # Send the image via Telegram
    await send_telegram_image(BOT_TOKEN, BOT_CHAT_ID, image_obj, "Weekly Meal Plan")


SCRIPT_CONFIG["execute_function"] = main

if __name__ == "__main__":
    asyncio.run(main())
