# Home Assistant Cards for MealieMate Plugins

This document serves as a working file for configuring Home Assistant cards for the MealieMate project. Each plugin has a dedicated card to control the plugin and to display feedback messages. Note that progress printouts are not shown because they can exceed the 255 character limit in entity states. Feedback strings are instead logged into sensor attributes and displayed using markdown.

---

## 1. Recipe Tagger Card

**Purpose:**  
This card manages the Recipe Tagger plugin and displays feedback messages for tagging results.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
style: |
  ha-card {
    --stack-card-divider-color: transparent;
  }
cards:
  - type: custom:mushroom-template-card
    primary: Recipe Tagger
    icon: mdi:tag-multiple
    entity: switch.mealiemate_recipe_tagger
    icon_color: |-
      {% if is_state('switch.mealiemate_recipe_tagger', 'on') %}
        blue
      {% else %}
        grey
      {% endif %}
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_tagging_feedback', 'full_text') }}
```

---

## 2. Meal Planner Card

**Purpose:**  
This card is designed for the Meal Planner plugin. It provides inputs for required parameters and displays feedback messages.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
style: |
  ha-card {
    --stack-card-divider-color: transparent;
  }
cards:
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 40%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 60%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-template-card
          primary: Meal Planner
          icon: mdi:calendar-text
          entity: switch.mealiemate_meal_planner
          icon_color: |-
            {% if is_state('switch.mealiemate_meal_planner', 'on') %}
              blue
            {% else %}
              grey
            {% endif %}
        - type: custom:mushroom-number-card
          entity: number.mealiemate_mealplan_days_required
          name: Days
          icon: mdi:calendar-range
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
  - type: custom:lovelace-multiline-text-input-card
    entity: text.mealiemate_mealplan_user_input
    autosave: true
    show_success_messages: false
    title: null
    buttons:
      clear: false
      paste: false
      save: false
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_planning_feedback', 'full_text') }}
```

---

## 3. Meal Plan Fetcher Card

**Purpose:**  
This card provides functionality for the Meal Plan Fetcher plugin. It includes an input for specifying the number of days and displays the formatted meal plan.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
style: |
  ha-card {
    --stack-card-divider-color: transparent;
  }
cards:
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 40%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 60%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-template-card
          primary: Meal Plan Fetcher
          icon: mdi:food-fork-drink
          entity: switch.mealiemate_meal_plan_fetcher
          icon_color: |-
            {% if is_state('switch.mealiemate_meal_plan_fetcher', 'on') %}
              blue
            {% else %}
              grey
            {% endif %}
        - type: custom:mushroom-number-card
          entity: number.mealiemate_fetcher_days
          name: Days
          icon: mdi:calendar-range
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_formatted_meal_plan', 'full_text') }}
```

---

## 4. Shopping List Generator Card

**Purpose:**  
This card is for the Shopping List Generator plugin. It provides a number input to specify how many days the shopping list should cover and displays feedback messages.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
style: |
  ha-card {
    --stack-card-divider-color: transparent;
  }
cards:
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 40%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 60%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-template-card
          primary: Shopping List Generator
          icon: mdi:cart
          entity: switch.mealiemate_shopping_list_generator
          icon_color: |-
            {% if is_state('switch.mealiemate_shopping_list_generator', 'on') %}
              blue
            {% else %}
              grey
            {% endif %}
        - type: custom:mushroom-number-card
          entity: number.mealiemate_shopping_list_days_required
          name: Days
          icon: mdi:calendar-range
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_shopping_list_feedback', 'full_text') }}
```

---

## 5. Neapolitan Pizza Card

**Purpose:**  
This card handles the Neapolitan Pizza plugin. It allows you to input various parameters for your pizza dough and displays the resulting pizza dough recipe in full detail.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
style: |
  ha-card {
    --stack-card-divider-color: transparent;
  }
cards:
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 40%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 60%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-template-card
          primary: Neapolitan Pizza Calculator
          icon: mdi:pizza
          entity: switch.mealiemate_neapolitan_pizza
          icon_color: |-
            {% if is_state('switch.mealiemate_neapolitan_pizza', 'on') %}
              blue
            {% else %}
              grey
            {% endif %}
        - type: custom:mushroom-number-card
          entity: number.mealiemate_number_of_balls
          name: Number of Balls
          icon: mdi:food
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 50%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 50%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-number-card
          entity: number.mealiemate_ball_weight_g
          name: Ball Weight (g)
          icon: mdi:weight-gram
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
        - type: custom:mushroom-number-card
          entity: number.mealiemate_hydration
          name: Hydration (%)
          icon: mdi:water-percent
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 50%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 50%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-number-card
          entity: number.mealiemate_salt_of_flour
          name: Salt (% of Flour)
          icon: mdi:shaker-outline
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
        - type: custom:mushroom-number-card
          entity: number.mealiemate_ambient_temperature_degc
          name: Ambient Temp (°C)
          icon: mdi:thermometer
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
  - type: custom:mod-card
    card_mod:
      style:
        hui-horizontal-stack-card $: |
          div#root > :first-child > * {
            width: 50%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 50%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-number-card
          entity: number.mealiemate_fridge_temperature_degc
          name: Fridge Temp (°C)
          icon: mdi:fridge
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
        - type: custom:mushroom-number-card
          entity: number.mealiemate_total_proof_time_hours
          name: Proof Time (hours)
          icon: mdi:clock-outline
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: horizontal
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_pizza_dough_recipe', 'full_text') }}
```

---

## 6. System Status Card

**Purpose:**  
This card provides an overview of the overall system status. It displays a binary sensor for the main MealieMate status and a sensor for the fetcher status, allowing you to quickly assess system health.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
style: |
  ha-card {
    --stack-card-divider-color: transparent;
  }
cards:
  - type: custom:mushroom-template-card
    primary: MealieMate System Status
    icon: mdi:server
    icon_color: |-
      {% if is_state('binary_sensor.mealiemate_mealiemate_status', 'on') %}
        green
      {% else %}
        red
      {% endif %}
  - type: markdown
    content: |-
      {% if is_state('binary_sensor.mealiemate_mealiemate_status', 'on') %}
        System Online | Fetcher Status: {{ states('sensor.mealiemate_fetcher_status') }}
      {% else %}
        System Offline
      {% endif %}
```

---

**Additional Notes:**

- These configurations require the following custom cards from HACS:
  - [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)
  - [Stack In Card](https://github.com/custom-cards/stack-in-card)
  - [Card Mod](https://github.com/thomasloven/lovelace-card-mod)
  - [Multiline Text Input Card](https://github.com/faeibson/lovelace-multiline-text-input-card)
- The cards use a consistent style with a Mushroom template card for the main control and feedback display.
- Feedback strings are stored in the attributes of the sensors and are accessed using the `state_attr` function.
- The divider lines between stack-in-card sections have been removed using custom CSS.
- Number inputs are displayed using the mushroom-number-card with button mode for a more visual interface.
- The horizontal layout has been adjusted using card_mod to create a 40/60 split for the main controls and a 50/50 split for the pizza parameters.

This working file can be updated and refined over time as your Home Assistant dashboard evolves.
