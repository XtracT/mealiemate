#!/usr/bin/env python3
"""
Module: neapolitan_pizza
----------------------------
Calculates dough ingredients and a fermentation schedule for Neapolitan-style pizza,
using a "scientific" approach based on temperature-dependent fermentation rates.

The standard fermentation schedule is:
  - 4h initial rest at ambient temperature (if possible)
  - Refrigeration period (variable based on total time)
  - Final ambient rest: 2h if fridge >= 7°C, otherwise 3h

The module compensates for the fact that dough doesn't instantly reach ambient temperature
during the final rest by using the average of the fridge and ambient fermentation factors
for that period.

This calculator helps create consistent pizza dough regardless of ambient conditions
by adjusting yeast quantities based on temperature and time.
"""

import asyncio
import math
import logging
from typing import Dict, Tuple, Optional, List

import utils.ha_mqtt as ha_mqtt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Script configuration for Home Assistant integration
SCRIPT_CONFIG = {
    "id": "neapolitan_pizza",
    "name": "Neapolitan Pizza",
    "type": "automation",
    "switch": True,
    "sensors": {
        "dough_recipe": {"id": "dough_recipe", "name": "Pizza Dough Recipe"}
    },
    "numbers": {
        "number_of_balls": {"id": "number_of_balls", "name": "Number of Balls", "value": 2},
        "ball_weight": {"id": "ball_weight", "name": "Ball Weight (g)", "value": 315},
        "hydration": {"id": "hydration", "name": "Hydration (%)", "value": 70},
        "salt_percent": {"id": "salt_percent", "name": "Salt (% of flour)", "value": 2.8},
        "ambient_temp": {"id": "ambient_temp", "name": "Ambient Temperature (°C)", "value": 20},
        "fridge_temp": {"id": "fridge_temp", "name": "Fridge Temperature (°C)", "value": 4},
        "total_time": {"id": "total_time", "name": "Total Proof Time (hours)", "value": 26}
    },
    "texts": {},
    "execute_function": None,
}

# Constants for dough calculation
YEAST_CONSTANT = 2.0  # Constant C in the formula IDY% = C / eq_hours
MIN_EQUIVALENT_HOURS = 0.1  # Minimum equivalent hours to prevent division by zero

def fermentation_factor(temp_c: float) -> float:
    """
    Calculate the relative fermentation speed factor compared to 20°C.
    
    This function uses the Q10 principle, where yeast activity roughly 
    doubles every 10°C increase in temperature.
    
    Args:
        temp_c: Temperature in Celsius
        
    Returns:
        Relative fermentation speed factor
    """
    return 2 ** ((temp_c - 20) / 10.0)

def calculate_dough_ingredients(
    num_balls: int, 
    ball_weight: float, 
    hydration_percent: float, 
    salt_percent: float
) -> Dict[str, float]:
    """
    Calculate the ingredients for pizza dough based on desired parameters.
    
    Args:
        num_balls: Number of dough balls to make
        ball_weight: Weight of each dough ball in grams
        hydration_percent: Water percentage relative to flour weight
        salt_percent: Salt percentage relative to flour weight
        
    Returns:
        Dictionary with calculated ingredient amounts in grams
    """
    # Convert percentages to decimals
    hydration = hydration_percent / 100.0
    salt_decimal = salt_percent / 100.0
    
    # Calculate total dough weight
    total_dough = num_balls * ball_weight
    
    # Calculate ingredients (ignoring yeast mass in initial calculation)
    flour = total_dough / (1 + hydration + salt_decimal)
    water = flour * hydration
    salt = flour * salt_decimal
    
    return {
        "flour": flour,
        "water": water,
        "salt": salt
    }


def calculate_fermentation_schedule(
    total_time: float,
    fridge_temp: float
) -> Tuple[float, float, float]:
    """
    Calculate the fermentation schedule based on total time and fridge temperature.
    
    Args:
        total_time: Total fermentation time in hours
        fridge_temp: Refrigerator temperature in Celsius
        
    Returns:
        Tuple of (initial_room_temp_hours, fridge_hours, final_ambient_rest_hours)
    """
    # Standard values
    initial_room_temp_hours = 4.0
    
    # Determine final ambient rest based on fridge temperature
    if fridge_temp >= 7:
        final_ambient_rest_hours = 2.0
    else:
        final_ambient_rest_hours = 3.0
    
    # Calculate fridge time
    fridge_hours = total_time - (initial_room_temp_hours + final_ambient_rest_hours)
    
    # Adjust if not enough time
    if fridge_hours < 0:
        # Not enough time for standard schedule, reduce initial rest
        initial_room_temp_hours = total_time - final_ambient_rest_hours
        
        if initial_room_temp_hours < 0:
            # If still negative, use all time for final rest
            initial_room_temp_hours = 0
            fridge_hours = 0
            final_ambient_rest_hours = total_time
        else:
            fridge_hours = 0
    
    return (initial_room_temp_hours, fridge_hours, final_ambient_rest_hours)


def calculate_equivalent_hours(
    initial_hours: float,
    fridge_hours: float,
    final_hours: float,
    ambient_temp: float,
    fridge_temp: float
) -> float:
    """
    Calculate equivalent fermentation hours at 20°C.
    
    Args:
        initial_hours: Hours for initial room temperature rest
        fridge_hours: Hours in refrigerator
        final_hours: Hours for final ambient rest
        ambient_temp: Ambient temperature in Celsius
        fridge_temp: Refrigerator temperature in Celsius
        
    Returns:
        Equivalent fermentation hours at 20°C
    """
    # Phase 1: initial rest at ambient temperature
    eq_initial = initial_hours * fermentation_factor(ambient_temp)
    
    # Phase 2: refrigeration
    eq_fridge = fridge_hours * fermentation_factor(fridge_temp)
    
    # Phase 3: final rest (average factor to approximate gradual warming)
    avg_factor_final = (fermentation_factor(fridge_temp) + fermentation_factor(ambient_temp)) / 2.0
    eq_final = final_hours * avg_factor_final
    
    # Sum all phases
    eq_hours = eq_initial + eq_fridge + eq_final
    
    # Prevent division by zero in yeast calculation
    if eq_hours < MIN_EQUIVALENT_HOURS:
        eq_hours = MIN_EQUIVALENT_HOURS
        
    return eq_hours


def format_recipe_output(
    ingredients: Dict[str, float],
    schedule: Tuple[float, float, float],
    yeast_grams: float
) -> str:
    """
    Format the recipe and schedule into a markdown string.
    
    Args:
        ingredients: Dictionary with ingredient amounts
        schedule: Tuple of (initial_hours, fridge_hours, final_hours)
        yeast_grams: Amount of yeast in grams
        
    Returns:
        Formatted markdown string
    """
    # Round values for clarity
    flour_int = int(round(ingredients["flour"], 0))
    water_int = int(round(ingredients["water"], 0))
    salt_rounded = round(ingredients["salt"], 2)
    yeast_rounded = round(yeast_grams, 2)
    
    init_room_rounded = round(schedule[0], 2)
    fridge_rounded = round(schedule[1], 2)
    final_rest_rounded = round(schedule[2], 2)
    
    # Create markdown output
    return (
        f"**Neapolitan Pizza Dough Recipe**\n\n"
        f"- **Flour:** {flour_int} g\n"
        f"- **Water:** {water_int} g\n"
        f"- **Salt:** {salt_rounded} g\n"
        f"- **Yeast:** {yeast_rounded} g\n\n"
        f"**Fermentation Schedule**\n"
        f"- Initial Room Temp: {init_room_rounded} h\n"
        f"- Fridge: {fridge_rounded} h\n"
        f"- Final Ambient Rest: {final_rest_rounded} h\n"
    )


async def main() -> None:
    """
    Main function that calculates pizza dough recipe and fermentation schedule.
    
    This function:
    1. Reads user inputs from SCRIPT_CONFIG
    2. Calculates dough ingredients
    3. Determines optimal fermentation schedule
    4. Calculates yeast amount based on temperature and time
    5. Formats and publishes the recipe via MQTT
    """
    logger.info("Starting Neapolitan pizza dough calculation")
    
    try:
        # 1) Read user inputs
        await ha_mqtt.info(SCRIPT_CONFIG["id"], "Starting pizza dough calculation...", category="start")
        num_balls = SCRIPT_CONFIG["numbers"]["number_of_balls"]["value"]
        ball_weight = SCRIPT_CONFIG["numbers"]["ball_weight"]["value"]
        hydration_percent = SCRIPT_CONFIG["numbers"]["hydration"]["value"]
        salt_percent_input = SCRIPT_CONFIG["numbers"]["salt_percent"]["value"]
        ambient_temp = SCRIPT_CONFIG["numbers"]["ambient_temp"]["value"]
        fridge_temp = SCRIPT_CONFIG["numbers"]["fridge_temp"]["value"]
        total_time = SCRIPT_CONFIG["numbers"]["total_time"]["value"]
        
        logger.info(f"Calculating recipe for {num_balls} balls, {ball_weight}g each, {hydration_percent}% hydration")
        await ha_mqtt.info(
            SCRIPT_CONFIG["id"], 
            f"Calculating recipe for {num_balls} balls, {ball_weight}g each, {hydration_percent}% hydration", 
            category="data"
        )
        
        # 2) Calculate base ingredients
        ingredients = calculate_dough_ingredients(
            num_balls, 
            ball_weight, 
            hydration_percent, 
            salt_percent_input
        )
        
        # 3) Calculate fermentation schedule
        schedule = calculate_fermentation_schedule(total_time, fridge_temp)
        initial_room_temp_hours, fridge_hours, final_ambient_rest_hours = schedule
        
        # 4) Calculate equivalent hours and yeast amount
        eq_hours = calculate_equivalent_hours(
            initial_room_temp_hours,
            fridge_hours,
            final_ambient_rest_hours,
            ambient_temp,
            fridge_temp
        )
        
        # Calculate yeast using scientific approach: IDY% = C / eq_hours
        yeast_percent = YEAST_CONSTANT / eq_hours
        yeast_grams = ingredients["flour"] * (yeast_percent / 100.0)
        
        logger.info(f"Calculated {yeast_grams:.2f}g yeast for {eq_hours:.2f} equivalent hours")
        await ha_mqtt.info(
            SCRIPT_CONFIG["id"], 
            f"Calculated {yeast_grams:.2f}g yeast for {eq_hours:.2f} equivalent hours", 
            category="data"
        )
        
        # 5) Format recipe output
        markdown_text = format_recipe_output(ingredients, schedule, yeast_grams)
        
        # 6) Log via MQTT
        await ha_mqtt.log(SCRIPT_CONFIG["id"], "dough_recipe", markdown_text, reset=True)
        await ha_mqtt.success(SCRIPT_CONFIG["id"], "Pizza dough recipe calculated successfully")
        logger.info("Pizza dough recipe published successfully")
        
    except Exception as e:
        logger.error(f"Error calculating pizza dough recipe: {str(e)}", exc_info=True)
        await ha_mqtt.error(SCRIPT_CONFIG["id"], f"Error calculating recipe: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())

SCRIPT_CONFIG["execute_function"] = main
