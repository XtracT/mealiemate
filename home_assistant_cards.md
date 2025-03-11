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
      {% if states('sensor.mealiemate_tagging_progress') | int == 100 %}
        green
      {% elif states('sensor.mealiemate_tagging_progress') | int > 0 %}
        blue
      {% else %}
        grey
      {% endif %}
  - type: custom:mod-card
    card_mod:
      style: |
        ha-card {
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-width: 0;
        }
    card:
      type: custom:bar-card
      entity: sensor.mealiemate_tagging_progress
      severity:
        - color: grey
          value: 0
        - color: blue
          value: 1
        - color: green
          value: 100
      max: 100
      min: 0
      height: 25px
      positions:
        icon: "off"
        indicator: "off"
        name: "off"
        value: inside
      card_mod:
        style: |
          bar-card-contentbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 10px;
          }
          bar-card-contentbar::before {
            content: '{{state_attr("sensor.mealiemate_tagging_progress", "activity")}}';
            color: white;
          }
          #bar-card-contentbar::after {
            content: '{{states("sensor.mealiemate_tagging_progress")}}%';
            color: white;
          }
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_tagging_feedback', 'full_text') }}
```

---

## 2. Ingredient Merger Card

**Purpose:**  
This card manages the Ingredient Merger plugin and displays feedback messages for ingredient merging suggestions. It also provides an interactive interface for accepting or rejecting merge suggestions.


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
    primary: Ingredient Merger
    icon: mdi:food-variant
    entity: switch.mealiemate_ingredient_merger
    icon_color: |-
      {% if is_state('switch.mealiemate_ingredient_merger', 'on') %}
        blue
      {% else %}
        grey
      {% endif %}
  - type: custom:mod-card
    card_mod:
      style: |
        ha-card {
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-width: 0;
        }
    card:
      type: custom:bar-card
      entity: sensor.mealiemate_merger_progress
      severity:
        - color: grey
          value: 0
        - color: blue
          value: 1
        - color: green
          value: 100
      max: 100
      min: 0
      height: 25px
      positions:
        icon: "off"
        indicator: "off"
        name: "off"
        value: inside
      card_mod:
        style: |
          bar-card-contentbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 10px;
          }
          bar-card-contentbar::before {
            content: '{{state_attr("sensor.mealiemate_merger_progress", "activity")}}';
            color: white;
          }
          #bar-card-contentbar::after {
            content: '{{states("sensor.mealiemate_merger_progress")}}%';
            color: white;
          }
  - type: markdown
    content: >
      {{ state_attr('sensor.mealiemate_current_merge_suggestion', 'full_text')
      }}
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: button.mealiemate_accept_merge
        name: Accept
        icon: mdi:check-circle
        icon_color: green
        tap_action:
          action: toggle
      - type: custom:mushroom-entity-card
        entity: button.mealiemate_reject_merge
        name: Reject
        icon: mdi:close-circle
        icon_color: red
        tap_action:
          action: toggle
```

---

## 3. Meal Planner Card

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
            {% if states('sensor.mealiemate_planning_progress') | int == 100 %}
              green
            {% elif states('sensor.mealiemate_planning_progress') | int > 0 %}
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
  - type: custom:mod-card
    card_mod:
      style: |
        ha-card {
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-width: 0;
        }
    card:
      type: custom:bar-card
      entity: sensor.mealiemate_planning_progress
      severity:
        - color: grey
          value: 0
        - color: blue
          value: 1
        - color: green
          value: 100
      max: 100
      min: 0
      height: 25px
      positions:
        icon: "off"
        indicator: "off"
        name: "off"
        value: inside
      card_mod:
        style: |
          bar-card-contentbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 10px;
          }
          bar-card-contentbar::before {
            content: '{{state_attr("sensor.mealiemate_planning_progress", "activity")}}';
            color: white;
          }
          #bar-card-contentbar::after {
            content: '{{states("sensor.mealiemate_planning_progress")}}%';
            color: white;
          }
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

## 4. Meal Plan Fetcher Card

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
            {% if states('sensor.mealiemate_fetcher_progress') | int == 100 %}
              green
            {% elif states('sensor.mealiemate_fetcher_progress') | int > 0 %}
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
  - type: custom:mod-card
    card_mod:
      style: |
        ha-card {
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-width: 0;
        }
    card:
      type: custom:bar-card
      entity: sensor.mealiemate_fetcher_progress
      severity:
        - color: grey
          value: 0
        - color: blue
          value: 1
        - color: green
          value: 100
      max: 100
      min: 0
      height: 25px
      positions:
        icon: "off"
        indicator: "off"
        name: "off"
        value: inside
      card_mod:
        style: |
          bar-card-contentbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 10px;
          }
          bar-card-contentbar::before {
            content: '{{state_attr("sensor.mealiemate_fetcher_progress", "activity")}}';
            color: white;
          }
          #bar-card-contentbar::after {
            content: '{{states("sensor.mealiemate_fetcher_progress")}}%';
            color: white;
          }
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_formatted_meal_plan', 'full_text') }}
```

---

## 5. Shopping List Generator Card

**Purpose:**  
This card is for the Shopping List Generator plugin. It provides a number input to specify how many days the shopping list should cover and displays feedback messages. To change if the shopping list should be generated from today or tomorrow's meals, double tap or hold the icon. 

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
            width: 65%;
            flex: auto; 
          }
          div#root > :last-child > * {
            width: 35%;
            flex: auto; 
          }
    card:
      type: horizontal-stack
      cards:
        - type: custom:mushroom-template-card
          primary: Shopping List Generator
          secondary: |-
            {% if is_state('switch.mealiemate_include_today', 'on') %}
              Including today
            {% else %}
              Starting tomorrow
            {% endif %}
          icon: mdi:cart
          entity: switch.mealiemate_shopping_list_generator
          icon_color: >-
            {% if states('sensor.mealiemate_shopping_list_progress') | int ==
            100 %}
              green
            {% elif states('sensor.mealiemate_shopping_list_progress') | int > 0
            %}
              blue
            {% else %}
              grey
            {% endif %}
          hold_action:
            action: call-service
            service: switch.toggle
            target:
              entity_id: switch.mealiemate_include_today
            data: {}
          double_tap_action:
            action: call-service
            service: switch.toggle
            target:
              entity_id: switch.mealiemate_include_today
            data: {}
        - type: custom:mushroom-number-card
          entity: number.mealiemate_shopping_list_days_required
          name: Days
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill_container: true
          layout: horizontal
  - type: custom:mod-card
    card_mod:
      style: |
        ha-card {
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-width: 0;
        }
    card:
      type: custom:bar-card
      entity: sensor.mealiemate_shopping_list_progress
      severity:
        - color: grey
          value: 0
        - color: blue
          value: 1
        - color: green
          value: 100
      max: 100
      min: 0
      height: 25px
      positions:
        icon: "off"
        indicator: "off"
        name: "off"
        value: inside
      card_mod:
        style: |
          bar-card-contentbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 10px;
          }
          bar-card-contentbar::before {
            content: '{{state_attr("sensor.mealiemate_shopping_list_progress", "activity")}}';
            color: white;
          }
          #bar-card-contentbar::after {
            content: '{{states("sensor.mealiemate_shopping_list_progress")}}%';
            color: white;
          }
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_shopping_list_feedback', 'full_text') }}
```

---

## 6. Neapolitan Pizza Card

**Purpose:**  
This card handles the Neapolitan Pizza plugin. It allows you to input various parameters for your pizza dough and displays the resulting pizza dough recipe in full detail.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
card_mod:
  style: |
    ha-card {
      --stack-card-divider-color: transparent !important;
      --stack-card-padding: 0;
    }
cards:
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
          fill: true
          layout: vertical
        - type: custom:mushroom-number-card
          entity: number.mealiemate_number_of_balls
          name: Number of Balls
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: vertical
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
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: vertical
        - type: custom:mushroom-number-card
          entity: number.mealiemate_hydration
          name: Hydration (%)
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: vertical
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
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: vertical
        - type: custom:mushroom-number-card
          entity: number.mealiemate_ambient_temperature_degc
          name: Ambient Temp (°C)
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: vertical
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
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: vertical
        - type: custom:mushroom-number-card
          entity: number.mealiemate_total_proof_time_hours
          name: Proof Time (hours)
          icon_type: none
          display_mode: buttons
          secondary_info: none
          fill: true
          layout: vertical
  - type: markdown
    content: |
      {{ state_attr('sensor.mealiemate_pizza_dough_recipe', 'full_text') }}
```

---

## 7. System Status Card

**Purpose:**  
This card provides an overview of the overall system status. It displays a binary sensor for the main MealieMate status and a sensor for the fetcher status, allowing you to quickly assess system health.

**YAML:**
```yaml
type: custom:stack-in-card
mode: vertical
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
visibility:
  - condition: state
    entity: binary_sensor.mealiemate_mealiemate_status
    state_not: "on"
```

---

**Additional Notes:**

- These configurations require the following custom cards from HACS:
  - [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)
  - [Stack In Card](https://github.com/custom-cards/stack-in-card)
  - [Card Mod](https://github.com/thomasloven/lovelace-card-mod)
  - [Multiline Text Input Card](https://github.com/faeibson/lovelace-multiline-text-input-card)
  - [Bar Card](https://github.com/custom-cards/bar-card) - For progress indicators
- The cards use a consistent style with a Mushroom template card for the main control and feedback display.
- Feedback strings are stored in the attributes of the sensors and are accessed using the `state_attr` function.
- The divider lines between stack-in-card sections have been removed using custom CSS.
- Number inputs are displayed using the mushroom-number-card with button mode for a more visual interface.
- The horizontal layout has been adjusted using card_mod to create a 40/60 split for the main controls and a 50/50 split for the pizza parameters.
