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

import math
import logging
from typing import Dict, Tuple, Optional, List, Any

from core.plugin import Plugin
from core.services import MqttService

# Configure logging
logger = logging.getLogger(__name__)

class NeapolitanPizzaPlugin(Plugin):
    """Plugin for calculating Neapolitan pizza dough recipes."""
    
    def __init__(self, mqtt_service: MqttService):
        """
        Initialize the NeapolitanPizzaPlugin.
        
        Args:
            mqtt_service: Service for MQTT communication
        """
        self._mqtt = mqtt_service
        
        # Configuration
        self._number_of_balls = 2
        self._ball_weight = 315
        self._hydration = 70
        self._salt_percent = 2.8
        self._ambient_temp = 20
        self._fridge_temp = 4
        self._total_time = 26
        
        # Constants for dough calculation
        self._yeast_constant = 2.0  # Constant C in the formula IDY% = C / eq_hours
        self._min_equivalent_hours = 0.1  # Minimum equivalent hours to prevent division by zero
    
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
        return "neapolitan_pizza"
    
    @property
    def name(self) -> str:
        """Human-readable name for the plugin."""
        return "Neapolitan Pizza"
    
    @property
    def description(self) -> str:
        """Description of what the plugin does."""
        return "Calculates dough ingredients and fermentation schedule for Neapolitan-style pizza."
    
    def get_mqtt_entities(self) -> Dict[str, Any]:
        """
        Get MQTT entities configuration for Home Assistant.
        
        Returns:
            A dictionary containing the MQTT entity configuration for this plugin.
        """
        return {
            "switch": True,
            "sensors": {
                "dough_recipe": {"id": "dough_recipe", "name": "Pizza Dough Recipe"},
                "progress": {"id": "progress", "name": "Pizza Calculation Progress"}
            },
            "numbers": {
                "number_of_balls": {
                    "id": "number_of_balls",
                    "name": "Number of Balls",
                    "value": self._number_of_balls,
                    "type": "int",
                    "min": 1,
                    "max": 20,
                    "step": 1,
                    "unit": "ball(s)"
                },
                "ball_weight": {
                    "id": "ball_weight",
                    "name": "Ball Weight (g)",
                    "value": self._ball_weight,
                    "type": "int",
                    "min": 100,
                    "max": 1000,
                    "step": 5,
                    "unit": "g"
                },
                "hydration": {
                    "id": "hydration",
                    "name": "Hydration (%)",
                    "value": self._hydration,
                    "type": "int",
                    "min": 50,
                    "max": 80,
                    "step": 1,
                    "unit": "%"
                },
                "salt_percent": {
                    "id": "salt_percent",
                    "name": "Salt (% of flour)",
                    "value": self._salt_percent,
                    "type": "float",
                    "min": 0.0,
                    "max": 6.0,
                    "step": 0.1,
                    "unit": "%"
                },
                "ambient_temp": {
                    "id": "ambient_temp",
                    "name": "Ambient Temperature (°C)",
                    "value": self._ambient_temp,
                    "type": "int",
                    "min": 0,
                    "max": 40,
                    "step": 1,
                    "unit": "°C"
                },
                "fridge_temp": {
                    "id": "fridge_temp",
                    "name": "Fridge Temperature (°C)",
                    "value": self._fridge_temp,
                    "type": "int",
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "unit": "°C"
                },
                "total_time": {
                    "id": "total_time",
                    "name": "Total Proof Time (hours)",
                    "value": self._total_time,
                    "type": "int",
                    "min": 1,
                    "max": 48,
                    "step": 1,
                    "unit": "h"
                }
            }
        }
    
    def fermentation_factor(self, temp_c: float) -> float:
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
        self,
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
        self,
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
        self,
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
        eq_initial = initial_hours * self.fermentation_factor(ambient_temp)
        
        # Phase 2: refrigeration
        eq_fridge = fridge_hours * self.fermentation_factor(fridge_temp)
        
        # Phase 3: final rest (average factor to approximate gradual warming)
        avg_factor_final = (self.fermentation_factor(fridge_temp) + self.fermentation_factor(ambient_temp)) / 2.0
        eq_final = final_hours * avg_factor_final
        
        # Sum all phases
        eq_hours = eq_initial + eq_fridge + eq_final
        
        # Prevent division by zero in yeast calculation
        if eq_hours < self._min_equivalent_hours:
            eq_hours = self._min_equivalent_hours
            
        return eq_hours

    def format_recipe_output(
        self,
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

    async def execute(self) -> None:
        """
        Main function that calculates pizza dough recipe and fermentation schedule.
        
        This function:
        1. Reads user inputs from configuration
        2. Calculates dough ingredients
        3. Determines optimal fermentation schedule
        4. Calculates yeast amount based on temperature and time
        5. Formats and publishes the recipe via MQTT
        """
        logger.info("Starting Neapolitan pizza dough calculation")
        
        try:
            # Update progress
            await self._mqtt.update_progress(self.id, "progress", 0, "Starting pizza dough calculation")
            
            # 1) Read user inputs
            await self._mqtt.info(self.id, "Starting pizza dough calculation...", category="start")
            await self._mqtt.update_progress(self.id, "progress", 20, "Reading input parameters")
            num_balls = self._number_of_balls
            ball_weight = self._ball_weight
            hydration_percent = self._hydration
            salt_percent_input = self._salt_percent
            ambient_temp = self._ambient_temp
            fridge_temp = self._fridge_temp
            total_time = self._total_time
            
            logger.info(f"Calculating recipe for {num_balls} balls, {ball_weight}g each, {hydration_percent}% hydration")
            await self._mqtt.info(
                self.id, 
                f"Calculating recipe for {num_balls} balls, {ball_weight}g each, {hydration_percent}% hydration", 
                category="data"
            )
            
            # 2) Calculate base ingredients
            await self._mqtt.update_progress(self.id, "progress", 40, "Calculating base ingredients")
            ingredients = self.calculate_dough_ingredients(
                num_balls, 
                ball_weight, 
                hydration_percent, 
                salt_percent_input
            )
            
            # 3) Calculate fermentation schedule
            await self._mqtt.update_progress(self.id, "progress", 60, "Calculating fermentation schedule")
            schedule = self.calculate_fermentation_schedule(total_time, fridge_temp)
            initial_room_temp_hours, fridge_hours, final_ambient_rest_hours = schedule
            
            # 4) Calculate equivalent hours and yeast amount
            await self._mqtt.update_progress(self.id, "progress", 80, "Calculating yeast amount")
            eq_hours = self.calculate_equivalent_hours(
                initial_room_temp_hours,
                fridge_hours,
                final_ambient_rest_hours,
                ambient_temp,
                fridge_temp
            )
            
            # Calculate yeast using scientific approach: IDY% = C / eq_hours
            yeast_percent = self._yeast_constant / eq_hours
            yeast_grams = ingredients["flour"] * (yeast_percent / 100.0)
            
            logger.info(f"Calculated {yeast_grams:.2f}g yeast for {eq_hours:.2f} equivalent hours")
            await self._mqtt.info(
                self.id, 
                f"Calculated {yeast_grams:.2f}g yeast for {eq_hours:.2f} equivalent hours", 
                category="data"
            )
            
            # 5) Format recipe output
            await self._mqtt.update_progress(self.id, "progress", 90, "Formatting recipe output")
            markdown_text = self.format_recipe_output(ingredients, schedule, yeast_grams)
            
            # 6) Log via MQTT
            await self._mqtt.log(self.id, "dough_recipe", markdown_text, reset=True)
            await self._mqtt.success(self.id, "Pizza dough recipe calculated successfully")
            logger.info("Pizza dough recipe published successfully")
            await self._mqtt.update_progress(self.id, "progress", 100, "Finished")
            
        except Exception as e:
            logger.error(f"Error calculating pizza dough recipe: {str(e)}", exc_info=True)
            await self._mqtt.error(self.id, f"Error calculating recipe: {str(e)}")
