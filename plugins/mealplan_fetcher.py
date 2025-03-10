"""
Module: mealplan_fetcher
------------------------
This module performs the following tasks:
  1. Fetches the upcoming meal plan (next 7 days, skipping today) from Mealie.
  2. Logs the meal plan in Markdown format via MQTT.
  3. Generates a 480x800 PNG image of the meal plan.
  4. Sends the generated image directly to a Telegram chat using credentials loaded from a .env file.

Requirements:
  - python-dotenv
  - python-telegram-bot
  - Pillow

Configuration:
  - Font files are stored in the 'fonts' directory at the project root.
  - Set environment variables in .env file (see README.md for details).
"""

import os
import logging
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from PIL import Image, ImageDraw, ImageFont
from telegram import Bot

from core.plugin import Plugin
from core.services import MqttService, MealieApiService

# Configure logging
logger = logging.getLogger(__name__)

class MealplanFetcherPlugin(Plugin):
    """Plugin for fetching and visualizing meal plans."""
    
    def __init__(self, mqtt_service: MqttService, mealie_service: MealieApiService):
        """
        Initialize the MealplanFetcherPlugin.
        
        Args:
            mqtt_service: Service for MQTT communication
            mealie_service: Service for Mealie API interaction
        """
        self._mqtt = mqtt_service
        self._mealie = mealie_service
        
        # Configuration
        self._num_days = 7
        self._mealie_url = "https://mealie.domain.com"
        
        # Global constant for output image name (used for logging only; image is sent in-memory)
        self._output_image_name = "weekly_meal_plan.png"
        
        # Load environment variables
        self._bot_token = os.getenv("TG_BOT_TOKEN")
        self._bot_chat_id = os.getenv("TG_BOT_CHAT_ID")
        
        # Image generation constants
        self._image_config = {
            "width": 480,
            "height": 800,
            "top_margin": 2,  # 2 pixels at the top
            "day_label_height": 40,  # 40 pixels for each day title
            "meal_space_height": 74,  # 74 pixels for meal space
            "day_label_v_offset": -12,
            "meals_v_offset": -5,
            "box_width": 200,
            "box_radius": 15,
            "line_height": 4,
            "colors": {
                "white": (255, 255, 255),
                "red": (255, 0, 0),
                "black": (0, 0, 0),
                "gray": (136, 136, 136)
            }
        }
    
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
        return "mealplan_fetcher"
    
    @property
    def name(self) -> str:
        """Human-readable name for the plugin."""
        return "Meal Plan Fetcher"
    
    @property
    def description(self) -> str:
        """Description of what the plugin does."""
        return "Fetches and visualizes meal plans from Mealie."
    
    def get_mqtt_entities(self) -> Dict[str, Any]:
        """
        Get MQTT entities configuration for Home Assistant.
        
        Returns:
            A dictionary containing the MQTT entity configuration for this plugin.
        """
        return {
            "switch": True,
            "sensors": {
                "mealplan": {"id": "mealplan", "name": "Formatted Meal Plan"}
            },
            "numbers": {
                "num_days": {"id": "num_days", "name": "Fetcher Days", "value": self._num_days}
            },
            "texts": {
                "mealie_url": {
                    "id": "mealie_url",
                    "name": "Mealie URL",
                    "text": self._mealie_url
                }
            }
        }
    
    def generate_markdown_table(self, mealplan: Dict[str, Dict[str, Dict]], mealie_url: str) -> str:
        """
        Generates a Markdown table from the meal plan.

        Args:
            mealplan: Dictionary of meal plan entries.
            mealie_url: Base URL of the Mealie instance.

        Returns:
            Markdown-formatted table.
        """
        header = "| Day | Lunch | Dinner |"
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
            rows.append(f"| {weekday} | {lunch_link} | {dinner_link} |")

        return "\n".join([header, separator] + rows)

    def load_font(self, font_path: str, size: int) -> ImageFont.ImageFont:
        """
        Load a font file with error handling.
        
        Args:
            font_path: Path to the font file (relative to project root)
            size: Font size
            
        Returns:
            Loaded font or default font if not found
        """
        base_dir = Path(__file__).parent.parent.absolute()
        full_font_path = base_dir / font_path
        
        try:
            return ImageFont.truetype(str(full_font_path), size)
        except IOError:
            logger.warning(f"Font file '{font_path}' not found, falling back to default font")
            return ImageFont.load_default()

    def get_meal_data(self, mealplan: Dict[str, Dict[str, Dict]], num_days: int = 7) -> Tuple[List[str], List[str], List[str]]:
        """
        Extract day names, lunch and dinner data from the meal plan.
        Skips today and fetches the following 7 days.
        
        Args:
            mealplan: Dictionary of meal plan entries
            num_days: Number of days to include
            
        Returns:
            Tuple of (day_names, lunches, dinners) lists
        """
        tomorrow = datetime.today().date() + timedelta(days=1)
        day_names, lunches, dinners = [], [], []

        for i in range(num_days):
            current_date = tomorrow + timedelta(days=i)
            weekday_name = current_date.strftime("%A").upper()
            day_str = current_date.strftime("%Y-%m-%d")
            
            if day_str in mealplan:
                lunch_recipe = mealplan[day_str].get("Lunch")
                dinner_recipe = mealplan[day_str].get("Dinner")
                lunch_name = lunch_recipe["name"] if lunch_recipe else "—"
                dinner_name = dinner_recipe["name"] if dinner_recipe else "—"
            else:
                lunch_name = dinner_name = "—"

            day_names.append(weekday_name)
            lunches.append(lunch_name)
            dinners.append(dinner_name)
            
        return day_names, lunches, dinners

    def wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
        """
        Wrap text into multiple lines that fit within max_width.
        
        Args:
            text: Text to wrap
            font: Font to use for measuring
            max_width: Maximum width in pixels
            draw: ImageDraw object for text measurement
            
        Returns:
            List of wrapped text lines
        """
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = (current_line + " " + word).strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
                
        lines.append(current_line)
        return lines

    def draw_lines_centered(
        self,
        draw: ImageDraw.ImageDraw,
        lines: List[str], 
        font: ImageFont.ImageFont, 
        rect: Tuple[int, int, int, int], 
        fill: Tuple[int, int, int], 
        line_spacing: int = 5, 
        v_offset: int = 0
    ) -> None:
        """
        Draw lines of text centered horizontally and vertically within rect.
        
        Args:
            draw: ImageDraw object
            lines: List of text lines
            font: Font to use
            rect: (x_left, y_top, x_right, y_bottom)
            fill: Text color
            line_spacing: Pixels between lines
            v_offset: Vertical offset for fine-tuning
        """
        x_left, y_top, x_right, y_bottom = rect
        rect_w = x_right - x_left
        rect_h = y_bottom - y_top

        # Calculate standard line height for consistency
        standard_line_height = draw.textbbox((0, 0), "Aj", font=font)[3] - draw.textbbox((0, 0), "Aj", font=font)[1]
            
        total_text_height = standard_line_height * len(lines) + line_spacing * (len(lines) - 1)
        current_y = y_top + (rect_h - total_text_height) // 2 + v_offset

        for i, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font)
            lw = bbox[2] - bbox[0]
            x_line = x_left + (rect_w - lw) // 2
            draw.text((x_line, current_y), ln, font=font, fill=fill)
            current_y += standard_line_height + (line_spacing if i < len(lines) - 1 else 0)

    def generate_mealplan_png(self, mealplan: Dict[str, Dict[str, Dict]]) -> Image.Image:
        """
        Generates a rotated meal plan image (480x800 portrait rotated 90°) in memory.
        
        The image contains:
          - A 2-pixel top margin.
          - Centered, rounded red day label boxes (200px wide) for the next 7 days,
            with the actual day names.
          - A thin horizontal red line across the full width, aligned with the middle of each box.
          - Two columns for meal text (Lunch and Dinner) in the remaining space.
        
        Args:
            mealplan: Dictionary of meal plan entries.
        
        Returns:
            The final rotated image.
        """
        # Extract constants from config
        WIDTH = self._image_config["width"]
        HEIGHT = self._image_config["height"]
        NUM_DAYS = self._num_days
        TOP_MARGIN = self._image_config["top_margin"]
        DAY_LABEL_HEIGHT = self._image_config["day_label_height"]
        DAY_LABEL_V_OFFSET = self._image_config["day_label_v_offset"]
        MEALS_V_OFFSET = self._image_config["meals_v_offset"]
        BOX_WIDTH = self._image_config["box_width"]
        BOX_HEIGHT = DAY_LABEL_HEIGHT
        BOX_RADIUS = self._image_config["box_radius"]
        LINE_HEIGHT = self._image_config["line_height"]
        
        # Colors
        WHITE = self._image_config["colors"]["white"]
        RED = self._image_config["colors"]["red"]
        BLACK = self._image_config["colors"]["black"]
        DAY_TEXT_COLOR = WHITE
        
        COLUMN_SEPARATOR_X = WIDTH // 2  # For splitting lunch and dinner columns

        # Get meal data
        day_names, lunches, dinners = self.get_meal_data(mealplan, NUM_DAYS)

        # Create base image
        img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
        draw = ImageDraw.Draw(img)

        # Load fonts
        FONT_DAY = self.load_font("fonts/PatrickHand-Regular.ttf", 38)
        FONT_MEAL = self.load_font("fonts/PatrickHand-Regular.ttf", 28)

        # Simple fixed layout with exact pixel measurements
        # Each day gets an equal portion of the height
        day_section_height = (HEIGHT - TOP_MARGIN) // NUM_DAYS
        
        for i in range(NUM_DAYS):
            # Calculate the top position for this day's section
            section_top = TOP_MARGIN + (i * day_section_height)
            
            # Calculate the center of the day label box
            box_center_y = section_top + (DAY_LABEL_HEIGHT // 2)
            
            # Calculate the top and bottom of the day label box
            box_top = box_center_y - (DAY_LABEL_HEIGHT // 2)
            box_bottom = box_center_y + (DAY_LABEL_HEIGHT // 2)
            
            # Define the horizontal position of the day label box (centered)
            box_left = (WIDTH - BOX_WIDTH) // 2
            box_right = box_left + BOX_WIDTH
            
            # Draw the red day label box
            draw.rounded_rectangle(
                [(box_left, box_top), (box_right, box_bottom)],
                radius=BOX_RADIUS, 
                fill=RED
            )
            
            # Draw the horizontal red line across the full width
            line_y = box_center_y
            draw.rectangle(
                [(0, line_y - (LINE_HEIGHT // 2)), (WIDTH, line_y + (LINE_HEIGHT // 2))],
                fill=RED
            )
            
            # Draw the day name text centered in the box
            day_name = day_names[i]
            bbox_day = draw.textbbox((0, 0), day_name, font=FONT_DAY)
            day_text_w = bbox_day[2] - bbox_day[0]
            day_text_h = bbox_day[3] - bbox_day[1]
            
            day_text_x = (WIDTH - day_text_w) // 2
            day_text_y = box_top + ((DAY_LABEL_HEIGHT - day_text_h) // 2) + DAY_LABEL_V_OFFSET
            
            draw.text((day_text_x, day_text_y), day_name, font=FONT_DAY, fill=DAY_TEXT_COLOR)
            
            # Calculate the meal area (below the day label box)
            meals_top = box_bottom
            
            # For all days except the last, the meal area extends to the top of the next day's section
            if i < NUM_DAYS - 1:
                meals_bottom = TOP_MARGIN + ((i + 1) * day_section_height)
            else:
                # For the last day, extend to the bottom of the image
                meals_bottom = HEIGHT
            
            # Draw the lunch (left column)
            left_rect = (0, meals_top, COLUMN_SEPARATOR_X, meals_bottom)
            lunch_lines = self.wrap_text(lunches[i], FONT_MEAL, (COLUMN_SEPARATOR_X - 20), draw)
            self.draw_lines_centered(draw, lunch_lines, FONT_MEAL, left_rect, BLACK, line_spacing=5, v_offset=MEALS_V_OFFSET)
            
            # Draw the dinner (right column)
            right_rect = (COLUMN_SEPARATOR_X, meals_top, WIDTH, meals_bottom)
            dinner_lines = self.wrap_text(dinners[i], FONT_MEAL, (WIDTH - COLUMN_SEPARATOR_X - 20), draw)
            self.draw_lines_centered(draw, dinner_lines, FONT_MEAL, right_rect, BLACK, line_spacing=5, v_offset=MEALS_V_OFFSET)

        # Rotate 90° (clockwise) and return the image
        rotated_img = img.rotate(270, expand=True)
        logger.info("Meal plan image generated in memory")
        return rotated_img

    async def send_telegram_image(
        self,
        bot_token: str, 
        chat_id: str, 
        image_obj: Image.Image, 
        caption: str = "Weekly Meal Plan"
    ) -> bool:
        """
        Sends an in-memory PIL Image object as a PNG file to a Telegram chat.
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
            image_obj: Image to send
            caption: Caption for the image
            
        Returns:
            True if successful, False otherwise
        """
        if not bot_token or not chat_id:
            logger.warning("Telegram token or chat ID not provided in .env. Skipping Telegram send.")
            return False

        try:
            bot = Bot(token=bot_token)
            buffer = BytesIO()
            image_obj.save(buffer, format="PNG")
            buffer.seek(0)
            await bot.send_photo(chat_id=chat_id, photo=buffer, caption=caption)
            logger.info("Telegram image sent successfully!")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram image: {e}")
            return False

    async def execute(self) -> None:
        """
        Main workflow:
          1. Fetch meal plan from Mealie (7 days).
          2. Log the meal plan in Markdown format via MQTT.
          3. Generate a rotated PNG image (in memory) of the meal plan.
          4. Send the PNG image via Telegram (if credentials are provided).
        """
        num_days = self._num_days
        mealie_url = self._mealie_url

        # Determine date range - skip today, get the next 7 days
        tomorrow = datetime.today().date() + timedelta(days=1)
        start_date = tomorrow.strftime("%Y-%m-%d")
        end_date = (tomorrow + timedelta(days=num_days - 1)).strftime("%Y-%m-%d")

        # Fetch meal plan from Mealie
        await self._mqtt.info(self.id, "Fetching meal plan from Mealie...", category="data")
        mealplan_items = await self._mealie.get_meal_plan(start_date, end_date)
        if not mealplan_items:
            await self._mqtt.warning(self.id, "No meal plan data available.")
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
        mealplan_markdown = self.generate_markdown_table(mealplan, mealie_url)
        await self._mqtt.log(self.id, "mealplan", mealplan_markdown, category="data")
        await self._mqtt.success(self.id, "Meal plan fetched and logged.")

        # Generate the PNG image (in memory)
        await self._mqtt.info(self.id, "Generating meal plan image...", category="progress")
        image_obj = self.generate_mealplan_png(mealplan)

        # Send the image via Telegram
        if self._bot_token and self._bot_chat_id:
            await self._mqtt.info(self.id, "Sending meal plan image to Telegram...", category="network")
            success = await self.send_telegram_image(self._bot_token, self._bot_chat_id, image_obj, "Weekly Meal Plan")
            if success:
                await self._mqtt.success(self.id, "Meal plan image sent to Telegram successfully.")
            else:
                await self._mqtt.error(self.id, "Failed to send meal plan image to Telegram.")
        else:
            await self._mqtt.warning(self.id, "Telegram credentials not provided. Skipping image send.")
