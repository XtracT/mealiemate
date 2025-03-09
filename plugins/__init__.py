"""
Plugins package for MealieMate.

This package contains all the plugins that provide functionality to the MealieMate application.
Each plugin implements the Plugin interface defined in the core package.
"""

from plugins.recipe_tagger import RecipeTaggerPlugin
from plugins.meal_planner import MealPlannerPlugin
from plugins.shopping_list_generator import ShoppingListGeneratorPlugin
from plugins.mealplan_fetcher import MealplanFetcherPlugin
from plugins.neapolitan_pizza import NeapolitanPizzaPlugin

__all__ = [
    'RecipeTaggerPlugin',
    'MealPlannerPlugin',
    'ShoppingListGeneratorPlugin',
    'MealplanFetcherPlugin',
    'NeapolitanPizzaPlugin'
]
