#!/usr/bin/env python3
"""
Module: neapolitan_pizza
----------------------------
Calculates dough ingredients and a fermentation schedule for Neapolitan-style pizza,
using a "scientific" approach. The schedule is:
  - 4h initial rest at ambient temperature (if possible)
  - fridge time
  - final ambient rest: 2h if fridge >= 7°C, otherwise 3h
We compensate for the fact that dough doesn't instantly jump to ambient temp during the
final rest by using the average of the fridge and ambient fermentation factors for that period.
"""

import asyncio
import math

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

def fermentation_factor(temp_c: float) -> float:
    """
    Returns a relative fermentation speed factor compared to 20°C,
    assuming yeast activity roughly doubles every 10°C.
    """
    return 2 ** ((temp_c - 20) / 10.0)

async def main():
    """
    Calculates dough ingredients and a fermentation schedule that sums to total_time.
    The schedule is:
      - 4h initial rest at ambient temperature (if possible)
      - fridge time
      - final ambient rest: 2h if fridge >= 7°C, else 3h
    We approximate final rest temperature as ramping from fridge temp to ambient temp
    by using the average of the two fermentation factors during that period.
    """
    # 1) Read user inputs
    num_balls = SCRIPT_CONFIG["numbers"]["number_of_balls"]["value"]
    ball_weight = SCRIPT_CONFIG["numbers"]["ball_weight"]["value"]
    hydration_percent = SCRIPT_CONFIG["numbers"]["hydration"]["value"]
    salt_percent_input = SCRIPT_CONFIG["numbers"]["salt_percent"]["value"]
    ambient_temp = SCRIPT_CONFIG["numbers"]["ambient_temp"]["value"]
    fridge_temp = SCRIPT_CONFIG["numbers"]["fridge_temp"]["value"]
    total_time = SCRIPT_CONFIG["numbers"]["total_time"]["value"]

    # 2) Convert percentages to decimals
    hydration = hydration_percent / 100.0
    salt_percent = salt_percent_input / 100.0

    # 3) Calculate total dough weight (g)
    total_dough = num_balls * ball_weight

    # 4) Dough formula ignoring yeast mass
    flour = total_dough / (1 + hydration + salt_percent)
    water = flour * hydration
    salt = flour * salt_percent

    # 5) Determine final ambient rest hours based on fridge_temp
    if fridge_temp >= 7:
        final_ambient_rest_hours = 2.0
    else:
        final_ambient_rest_hours = 3.0

    # 6) Initial rest = 4h if possible
    initial_room_temp_hours = 4.0

    # 7) Fridge time = total_time - (initial_room_temp_hours + final_ambient_rest_hours)
    fridge_hours = total_time - (initial_room_temp_hours + final_ambient_rest_hours)
    if fridge_hours < 0:
        # Not enough time for 4h initial + final rest
        # We'll reduce the initial rest to keep final rest intact
        initial_room_temp_hours = total_time - final_ambient_rest_hours
        if initial_room_temp_hours < 0:
            # If even that is negative, use all time for final rest
            initial_room_temp_hours = 0
            fridge_hours = 0
            final_ambient_rest_hours = total_time
        else:
            fridge_hours = total_time - (initial_room_temp_hours + final_ambient_rest_hours)

    # 8) Calculate equivalent hours (eq_hours)
    #    - Initial rest: full ambient_temp
    #    - Fridge: full fridge_temp
    #    - Final rest: average factor between fridge_temp and ambient_temp
    #      to approximate gradual warming.

    # Phase 1: initial rest
    eq_initial = initial_room_temp_hours * fermentation_factor(ambient_temp)

    # Phase 2: fridge
    eq_fridge = fridge_hours * fermentation_factor(fridge_temp)

    # Phase 3: final rest
    # average factor = (fermentation_factor(fridge_temp) + fermentation_factor(ambient_temp)) / 2
    avg_factor_final = (
        fermentation_factor(fridge_temp) + fermentation_factor(ambient_temp)
    ) / 2.0
    eq_final = final_ambient_rest_hours * avg_factor_final

    eq_hours = eq_initial + eq_fridge + eq_final

    # Avoid extremely small eq_hours
    if eq_hours < 0.1:
        eq_hours = 0.1

    # 9) Yeast calculation using scientific approach
    #    IDY% = C / eq_hours
    C = 2.0
    yeast_percent = C / eq_hours  # e.g., 0.2 => 0.2% IDY
    yeast_grams = flour * (yeast_percent / 100.0)

    # 10) Round values for clarity
    flour_int = int(round(flour, 0))
    water_int = int(round(water, 0))
    salt_rounded = round(salt, 2)
    yeast_grams_rounded = round(yeast_grams, 2)
    init_room_rounded = round(initial_room_temp_hours, 2)
    fridge_rounded = round(fridge_hours, 2)
    final_rest_rounded = round(final_ambient_rest_hours, 2)
    total_sum = round(init_room_rounded + fridge_rounded + final_rest_rounded, 2)

    # 11) Prepare the output text
    markdown_text = (
        f"**Neapolitan Pizza Dough Recipe**\n\n"
        f"- **Flour:** {flour_int} g\n"
        f"- **Water:** {water_int} g\n"
        f"- **Salt:** {salt_rounded} g\n"
        f"- **Yeast:** {yeast_grams_rounded} g\n\n"
        f"**Fermentation Schedule**\n"
        f"- Initial Room Temp: {init_room_rounded} h\n"
        f"- Fridge: {fridge_rounded} h\n"
        f"- Final Ambient Rest: {final_rest_rounded} h \n"
    )

    # 12) Log via MQTT and print to stdout
    from utils.ha_mqtt import log
    await log(SCRIPT_CONFIG["id"], "dough_recipe", markdown_text, reset=True)

if __name__ == "__main__":
    asyncio.run(main())

SCRIPT_CONFIG["execute_function"] = main
